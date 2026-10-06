import os
import uuid
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from SRC.database import get_connection


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

security = HTTPBearer()

# --------------------------------------------------
# JWT CONFIGURATION
# --------------------------------------------------

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not configured. Add JWT_SECRET to your .env file."
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


# --------------------------------------------------
# PASSWORD SECURITY
# --------------------------------------------------

PBKDF2_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    """
    Securely hash a password using PBKDF2-HMAC-SHA256.
    """

    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )

    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}$"
        f"{salt.hex()}${password_hash.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against the stored PBKDF2 hash.
    """

    try:
        algorithm, iterations, salt_hex, hash_hex = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        salt = bytes.fromhex(salt_hex)

        calculated_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )

        return hmac.compare_digest(
            calculated_hash.hex(),
            hash_hex,
        )

    except (ValueError, TypeError):
        return False


# --------------------------------------------------
# DATABASE TABLE
# --------------------------------------------------

def create_users_table():
    """
    Create the users table if it doesn't already exist.
    """

    with get_connection() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )

        connection.commit()


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# --------------------------------------------------
# JWT
# --------------------------------------------------

def create_access_token(user_id: str, email: str, name: str) -> str:
    """
    Create a JWT containing the authenticated user's identity.
    """

    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Validate JWT and return the authenticated user's identity.
    """

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")
        email = payload.get("email")
        name = payload.get("name")

        if not user_id or not email:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token.",
            )

        return {
            "user_id": user_id,
            "email": email,
            "name": name,
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Authentication token has expired.",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
        )


# --------------------------------------------------
# SIGN UP
# --------------------------------------------------

@router.post("/signup")
def signup(request: SignupRequest):
    """
    Create a new DataFlow AI account.
    """

    create_users_table()

    name = request.name.strip()
    email = str(request.email).strip().lower()
    password = request.password

    if len(name) < 2:
        raise HTTPException(
            status_code=400,
            detail="Name must contain at least 2 characters.",
        )

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters.",
        )

    # Check whether account already exists
    with get_connection() as connection:
        existing_user = connection.execute(
            text(
                """
                SELECT user_id
                FROM users
                WHERE email = :email
                """
            ),
            {"email": email},
        ).fetchone()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    with get_connection() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    user_id,
                    name,
                    email,
                    password_hash,
                    created_at
                )
                VALUES (
                    :user_id,
                    :name,
                    :email,
                    :password_hash,
                    :created_at
                )
                """
            ),
            {
                "user_id": user_id,
                "name": name,
                "email": email,
                "password_hash": password_hash,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        connection.commit()

    access_token = create_access_token(
        user_id=user_id,
        email=email,
        name=name,
    )

    return {
        "message": "Account created successfully.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "name": name,
            "email": email,
        },
    }


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@router.post("/login")
def login(request: LoginRequest):
    """
    Authenticate an existing DataFlow AI user.
    """

    create_users_table()

    email = str(request.email).strip().lower()

    with get_connection() as connection:
        user = connection.execute(
            text(
                """
                SELECT
                    user_id,
                    name,
                    email,
                    password_hash
                FROM users
                WHERE email = :email
                """
            ),
            {"email": email},
        ).fetchone()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    user_id, name, stored_email, stored_password_hash = user

    if not verify_password(
        request.password,
        stored_password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    access_token = create_access_token(
        user_id=user_id,
        email=stored_email,
        name=name,
    )

    return {
        "message": "Login successful.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "name": name,
            "email": stored_email,
        },
    }


# --------------------------------------------------
# CURRENT USER
# --------------------------------------------------

@router.get("/me")
def get_me(
    current_user: dict = Depends(get_current_user),
):
    """
    Return the currently authenticated user.
    """

    return {
        "user": current_user,
    }