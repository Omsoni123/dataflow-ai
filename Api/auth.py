import os
import uuid
import hashlib
import hmac
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from SRC.database import get_connection


router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not configured. Add JWT_SECRET to your .env file.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "")

RESET_OTP_EXPIRATION_MINUTES = 10
RESET_OTP_MAX_ATTEMPTS = 5

PBKDF2_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}$"
        f"{salt.hex()}${password_hash.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
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
        return hmac.compare_digest(calculated_hash.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def hash_reset_otp(email: str, otp: str) -> str:
    message = f"{email.lower().strip()}:{otp}".encode("utf-8")
    return hmac.new(
        JWT_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def generate_reset_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send_password_reset_otp(recipient_email: str, otp: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError(
            "SMTP email is not configured. Add SMTP_USER and SMTP_PASSWORD to the environment."
        )

    message = EmailMessage()
    message["Subject"] = "DataFlow AI Password Reset OTP"
    message["From"] = SMTP_FROM
    message["To"] = recipient_email
    message.set_content(
        f"""Hello,

We received a request to reset your DataFlow AI password.

Your password reset OTP is:

{otp}

This OTP expires in {RESET_OTP_EXPIRATION_MINUTES} minutes.

If you did not request a password reset, you can safely ignore this email.

Do not share this OTP with anyone.

— DataFlow AI
"""
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)


def create_users_table():
    with get_connection() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                ai_questions_used INTEGER NOT NULL DEFAULT 0,
                subscription_status TEXT NOT NULL DEFAULT 'inactive',
                razorpay_subscription_id TEXT,
                reset_otp_hash TEXT,
                reset_otp_expires_at TEXT,
                reset_otp_attempts INTEGER NOT NULL DEFAULT 0
            )
        """))

        for column_definition in [
            "plan TEXT NOT NULL DEFAULT 'free'",
            "ai_questions_used INTEGER NOT NULL DEFAULT 0",
            "subscription_status TEXT NOT NULL DEFAULT 'inactive'",
            "razorpay_subscription_id TEXT",
            "reset_otp_hash TEXT",
            "reset_otp_expires_at TEXT",
            "reset_otp_attempts INTEGER NOT NULL DEFAULT 0",
        ]:
            column_name = column_definition.split()[0]
            connection.execute(text(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column_name} "
                f"{column_definition[len(column_name):].strip()}"
            ))

        connection.commit()


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


def create_access_token(user_id: str, email: str, name: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
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
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

        return {"user_id": user_id, "email": email, "name": name}

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")


@router.post("/signup")
def signup(request: SignupRequest):
    create_users_table()
    name = request.name.strip()
    email = str(request.email).strip().lower()
    password = request.password

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Name must contain at least 2 characters.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must contain at least 8 characters.")

    with get_connection() as connection:
        existing_user = connection.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()

    if existing_user:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    with get_connection() as connection:
        connection.execute(
            text("""
                INSERT INTO users (
                    user_id, name, email, password_hash, created_at
                )
                VALUES (
                    :user_id, :name, :email, :password_hash, :created_at
                )
            """),
            {
                "user_id": user_id,
                "name": name,
                "email": email,
                "password_hash": password_hash,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        connection.commit()

    access_token = create_access_token(user_id, email, name)

    return {
        "message": "Account created successfully.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"user_id": user_id, "name": name, "email": email},
    }


@router.post("/login")
def login(request: LoginRequest):
    create_users_table()
    email = str(request.email).strip().lower()

    with get_connection() as connection:
        user = connection.execute(
            text("""
                SELECT user_id, name, email, password_hash
                FROM users
                WHERE email = :email
            """),
            {"email": email},
        ).fetchone()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user_id, name, stored_email, stored_password_hash = user

    if not verify_password(request.password, stored_password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    access_token = create_access_token(user_id, stored_email, name)

    return {
        "message": "Login successful.",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"user_id": user_id, "name": name, "email": stored_email},
    }


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    create_users_table()

    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must contain at least 8 characters.")

    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password.",
        )

    with get_connection() as connection:
        user = connection.execute(
            text("SELECT password_hash FROM users WHERE user_id = :user_id"),
            {"user_id": current_user["user_id"]},
        ).fetchone()

        if user is None:
            raise HTTPException(status_code=404, detail="User account not found.")

        if not verify_password(request.current_password, user[0]):
            raise HTTPException(status_code=401, detail="Current password is incorrect.")

        connection.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash,
                    reset_otp_hash = NULL,
                    reset_otp_expires_at = NULL,
                    reset_otp_attempts = 0
                WHERE user_id = :user_id
            """),
            {
                "password_hash": hash_password(request.new_password),
                "user_id": current_user["user_id"],
            },
        )
        connection.commit()

    return {"message": "Password changed successfully. Please log in again."}


@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    create_users_table()
    email = str(request.email).strip().lower()
    otp = generate_reset_otp()
    otp_hash = hash_reset_otp(email, otp)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=RESET_OTP_EXPIRATION_MINUTES
    )

    with get_connection() as connection:
        user = connection.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()

        if user is not None:
            connection.execute(
                text("""
                    UPDATE users
                    SET reset_otp_hash = :otp_hash,
                        reset_otp_expires_at = :expires_at,
                        reset_otp_attempts = 0
                    WHERE email = :email
                """),
                {
                    "otp_hash": otp_hash,
                    "expires_at": expires_at.isoformat(),
                    "email": email,
                },
            )
            connection.commit()

    if user is not None:
        try:
            send_password_reset_otp(email, otp)
        except Exception as error:
            with get_connection() as connection:
                connection.execute(
                    text("""
                        UPDATE users
                        SET reset_otp_hash = NULL,
                            reset_otp_expires_at = NULL,
                            reset_otp_attempts = 0
                        WHERE email = :email
                    """),
                    {"email": email},
                )
                connection.commit()

            raise HTTPException(
                status_code=500,
                detail=f"Unable to send password reset email: {str(error)}",
            )

    return {
        "message": "If an account with that email exists, a password reset OTP has been sent."
    }


@router.post("/verify-reset-otp")
def verify_reset_otp(request: VerifyResetOTPRequest):
    create_users_table()
    email = str(request.email).strip().lower()
    otp = request.otp.strip()

    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must contain at least 8 characters.")

    if not otp.isdigit() or len(otp) != 6:
        raise HTTPException(status_code=400, detail="OTP must be a 6-digit number.")

    with get_connection() as connection:
        user = connection.execute(
            text("""
                SELECT user_id, reset_otp_hash, reset_otp_expires_at, reset_otp_attempts
                FROM users
                WHERE email = :email
            """),
            {"email": email},
        ).fetchone()

        if user is None:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

        user_id, stored_otp_hash, expires_at_raw, attempts = user

        if not stored_otp_hash or not expires_at_raw:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

        if attempts >= RESET_OTP_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect OTP attempts. Please request a new OTP.",
            )

        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

        if datetime.now(timezone.utc) >= expires_at:
            connection.execute(
                text("""
                    UPDATE users
                    SET reset_otp_hash = NULL,
                        reset_otp_expires_at = NULL,
                        reset_otp_attempts = 0
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id},
            )
            connection.commit()
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new OTP.")

        expected_hash = hash_reset_otp(email, otp)

        if not hmac.compare_digest(expected_hash, stored_otp_hash):
            connection.execute(
                text("""
                    UPDATE users
                    SET reset_otp_attempts = reset_otp_attempts + 1
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id},
            )
            connection.commit()
            raise HTTPException(status_code=400, detail="Invalid or expired OTP.")

        connection.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash,
                    reset_otp_hash = NULL,
                    reset_otp_expires_at = NULL,
                    reset_otp_attempts = 0
                WHERE user_id = :user_id
            """),
            {
                "password_hash": hash_password(request.new_password),
                "user_id": user_id,
            },
        )
        connection.commit()

    return {
        "message": "Password reset successfully. Please log in with your new password."
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}
