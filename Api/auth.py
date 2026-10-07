# ============================================================
# DATAFLOW AI - AUTHENTICATION & ACCOUNT SECURITY
# ============================================================

import os
import json
import uuid
import secrets
import hashlib
import hmac
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from SRC.database import get_connection


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not configured. "
        "Add JWT_SECRET to your .env file."
    )


JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


# ============================================================
# PASSWORD RESET CONFIGURATION
# ============================================================

RESET_OTP_EXPIRATION_MINUTES = 10
RESET_OTP_MAX_ATTEMPTS = 5


# ============================================================
# RESEND EMAIL CONFIGURATION
# ============================================================

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

RESEND_FROM_EMAIL = os.getenv(
    "RESEND_FROM_EMAIL",
    "onboarding@resend.dev",
)


# ============================================================
# JWT IMPORT
# ============================================================

try:
    from jose import jwt
except ImportError:
    raise RuntimeError(
        "python-jose is required. "
        "Install it with: pip install python-jose[cryptography]"
    )


# ============================================================
# PASSWORD HASHING
# ============================================================

try:
    from passlib.context import CryptContext
except ImportError:
    raise RuntimeError(
        "passlib is required. "
        "Install it with: pip install passlib[bcrypt]"
    )


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ============================================================
# DATABASE SETUP
# ============================================================

def create_users_table():
    """
    Create the users table if it does not exist.

    Also performs safe migrations for existing databases.
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
                    created_at TEXT NOT NULL,

                    plan TEXT NOT NULL DEFAULT 'free',

                    ai_questions_used INTEGER
                        NOT NULL DEFAULT 0,

                    subscription_status TEXT
                        NOT NULL DEFAULT 'inactive',

                    razorpay_subscription_id TEXT,

                    reset_otp_hash TEXT,

                    reset_otp_expires_at TEXT,

                    reset_otp_attempts INTEGER
                        NOT NULL DEFAULT 0
                )
                """
            )
        )

        # ----------------------------------------------------
        # Safe migrations for existing users table
        # ----------------------------------------------------

        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS plan
                TEXT NOT NULL DEFAULT 'free'
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS ai_questions_used
                INTEGER NOT NULL DEFAULT 0
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS subscription_status
                TEXT NOT NULL DEFAULT 'inactive'
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS razorpay_subscription_id
                TEXT
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS reset_otp_hash
                TEXT
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS reset_otp_expires_at
                TEXT
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS reset_otp_attempts
                INTEGER NOT NULL DEFAULT 0
                """
            )
        )

        connection.commit()


# ============================================================
# INITIALIZE DATABASE
# ============================================================

create_users_table()


# ============================================================
# PASSWORD HELPERS
# ============================================================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    """

    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a password against its bcrypt hash.
    """

    try:
        return pwd_context.verify(
            plain_password,
            hashed_password,
        )
    except Exception:
        return False


# ============================================================
# JWT HELPERS
# ============================================================

def create_access_token(user_id: str) -> str:
    """
    Create a JWT access token.
    """

    expire = datetime.now(timezone.utc) + timedelta(
        hours=JWT_EXPIRATION_HOURS
    )

    payload = {
        "sub": user_id,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


# ============================================================
# USER LOOKUP
# ============================================================

def get_user_by_email(email: str):
    """
    Get user by email.
    """

    with get_connection() as connection:

        result = connection.execute(
            text(
                """
                SELECT
                    user_id,
                    name,
                    email,
                    password_hash,
                    created_at,
                    plan,
                    ai_questions_used,
                    subscription_status,
                    razorpay_subscription_id,
                    reset_otp_hash,
                    reset_otp_expires_at,
                    reset_otp_attempts
                FROM users
                WHERE LOWER(email) = LOWER(:email)
                LIMIT 1
                """
            ),
            {
                "email": email.strip(),
            },
        ).fetchone()

    return result


def get_user_by_id(user_id: str):
    """
    Get user by ID.
    """

    with get_connection() as connection:

        result = connection.execute(
            text(
                """
                SELECT
                    user_id,
                    name,
                    email,
                    password_hash,
                    created_at,
                    plan,
                    ai_questions_used,
                    subscription_status,
                    razorpay_subscription_id,
                    reset_otp_hash,
                    reset_otp_expires_at,
                    reset_otp_attempts
                FROM users
                WHERE user_id = :user_id
                LIMIT 1
                """
            ),
            {
                "user_id": user_id,
            },
        ).fetchone()

    return result


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user(
    authorization: str = Header(default=None),
):
    """
    Authenticate the current request using Bearer JWT.
    """

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication format.",
        )

    token = authorization.replace(
        "Bearer ",
        "",
        1,
    ).strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication token is missing.",
        )

    try:

        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token.",
            )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        )

    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User account no longer exists.",
        )

    return {
        "user_id": user[0],
        "name": user[1],
        "email": user[2],
        "created_at": user[4],
        "plan": user[5],
        "ai_questions_used": user[6],
        "subscription_status": user[7],
        "razorpay_subscription_id": user[8],
    }


# ============================================================
# REQUEST MODELS
# ============================================================

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


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_password(password: str):
    """
    Basic password security validation.
    """

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )

    if len(password) > 128:
        raise HTTPException(
            status_code=400,
            detail="Password must be 128 characters or fewer.",
        )


# ============================================================
# SIGNUP
# ============================================================

@router.post("/signup")
def signup(request: SignupRequest):

    name = request.name.strip()
    email = request.email.strip().lower()
    password = request.password

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Name is required.",
        )

    validate_password(password)

    existing_user = get_user_by_email(email)

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    user_id = str(uuid.uuid4())

    password_hash = hash_password(password)

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with get_connection() as connection:

        connection.execute(
            text(
                """
                INSERT INTO users (
                    user_id,
                    name,
                    email,
                    password_hash,
                    created_at,
                    plan,
                    ai_questions_used,
                    subscription_status
                )
                VALUES (
                    :user_id,
                    :name,
                    :email,
                    :password_hash,
                    :created_at,
                    'free',
                    0,
                    'inactive'
                )
                """
            ),
            {
                "user_id": user_id,
                "name": name,
                "email": email,
                "password_hash": password_hash,
                "created_at": created_at,
            },
        )

        connection.commit()

    token = create_access_token(user_id)

    return {
        "success": True,
        "message": "Account created successfully.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "name": name,
            "email": email,
            "plan": "free",
            "ai_questions_used": 0,
            "subscription_status": "inactive",
        },
    }


# ============================================================
# LOGIN
# ============================================================

@router.post("/login")
def login(request: LoginRequest):

    email = request.email.strip().lower()

    user = get_user_by_email(email)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    password_hash = user[3]

    if not verify_password(
        request.password,
        password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    token = create_access_token(user[0])

    return {
        "success": True,
        "message": "Login successful.",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user[0],
            "name": user[1],
            "email": user[2],
            "created_at": user[4],
            "plan": user[5],
            "ai_questions_used": user[6],
            "subscription_status": user[7],
            "razorpay_subscription_id": user[8],
        },
    }


# ============================================================
# CURRENT USER
# ============================================================

@router.get("/me")
def get_me(
    current_user: dict = Depends(get_current_user),
):

    return {
        "success": True,
        "user": current_user,
    }


# ============================================================
# CHANGE PASSWORD
# ============================================================

@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):

    validate_password(request.new_password)

    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from your current password.",
        )

    user = get_user_by_id(
        current_user["user_id"]
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User account not found.",
        )

    if not verify_password(
        request.current_password,
        user[3],
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect.",
        )

    new_password_hash = hash_password(
        request.new_password
    )

    with get_connection() as connection:

        connection.execute(
            text(
                """
                UPDATE users
                SET password_hash = :password_hash
                WHERE user_id = :user_id
                """
            ),
            {
                "password_hash": new_password_hash,
                "user_id": current_user["user_id"],
            },
        )

        connection.commit()

    return {
        "success": True,
        "message": "Password changed successfully.",
    }


# ============================================================
# RESET OTP HELPERS
# ============================================================

def generate_reset_otp() -> str:
    """
    Generate a secure 6-digit OTP.
    """

    return f"{secrets.randbelow(1_000_000):06d}"


def hash_reset_otp(
    otp: str,
) -> str:
    """
    Hash reset OTP using HMAC-SHA256.

    The JWT secret is used as the server-side secret.
    """

    return hmac.new(
        JWT_SECRET.encode("utf-8"),
        otp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ============================================================
# RESEND EMAIL
# ============================================================

def send_password_reset_otp(
    recipient_email: str,
    otp: str,
) -> None:
    """
    Send password-reset OTP using Resend HTTPS API.

    No SMTP connection is used.
    """

    if not RESEND_API_KEY:
        raise RuntimeError(
            "RESEND_API_KEY is not configured."
        )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>DataFlow AI Password Reset</title>
    </head>

    <body style="
        margin:0;
        padding:40px 20px;
        background:#07050d;
        font-family:Arial,Helvetica,sans-serif;
        color:#ffffff;
    ">

        <div style="
            max-width:520px;
            margin:0 auto;
            background:#111018;
            border:1px solid #292633;
            border-radius:20px;
            padding:32px;
        ">

            <div style="
                width:48px;
                height:48px;
                line-height:48px;
                text-align:center;
                border-radius:12px;
                background:#8b5cf6;
                color:#ffffff;
                font-size:22px;
                font-weight:bold;
                margin-bottom:24px;
            ">
                D
            </div>

            <h2 style="
                margin:0 0 12px 0;
                color:#ffffff;
            ">
                Reset your DataFlow AI password
            </h2>

            <p style="
                color:#b8b3c7;
                line-height:1.6;
            ">
                We received a request to reset your DataFlow AI password.
                Use the verification code below.
            </p>

            <div style="
                margin:28px 0;
                padding:20px;
                text-align:center;
                border-radius:14px;
                background:#1a1723;
                border:1px solid #352e43;
                color:#a855f7;
                font-size:32px;
                font-weight:bold;
                letter-spacing:8px;
            ">
                {otp}
            </div>

            <p style="
                color:#8f899d;
                font-size:14px;
                line-height:1.6;
            ">
                This verification code expires in
                <strong style="color:#ffffff;">
                    10 minutes
                </strong>.
            </p>

            <p style="
                color:#8f899d;
                font-size:14px;
                line-height:1.6;
            ">
                If you did not request this password reset,
                you can safely ignore this email.
            </p>

            <hr style="
                border:0;
                border-top:1px solid #292633;
                margin:28px 0;
            ">

            <p style="
                margin:0;
                color:#6f6979;
                font-size:12px;
            ">
                DataFlow AI
            </p>

        </div>

    </body>
    </html>
    """

    payload = {
        "from": RESEND_FROM_EMAIL,
        "to": [recipient_email],
        "subject": "DataFlow AI Password Reset Code",
        "html": html,
    }

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=20,
        ) as response:

            response_body = (
                response
                .read()
                .decode("utf-8")
            )

            if not (
                200
                <= response.status
                < 300
            ):
                raise RuntimeError(
                    f"Email service returned HTTP {response.status}."
                )

            try:
                response_data = json.loads(
                    response_body
                )
            except json.JSONDecodeError:
                response_data = {}

            if not response_data.get("id"):
                raise RuntimeError(
                    "Email service did not return an email ID."
                )

    except urllib.error.HTTPError as error:

        try:
            error_body = (
                error
                .read()
                .decode("utf-8")
            )
        except Exception:
            error_body = ""

        raise RuntimeError(
            f"Email sending failed with HTTP "
            f"{error.code}. "
            f"{error_body[:500]}"
        ) from error

    except urllib.error.URLError as error:

        raise RuntimeError(
            f"Unable to reach email service: "
            f"{error.reason}"
        ) from error

    except TimeoutError as error:

        raise RuntimeError(
            "Email service request timed out."
        ) from error


# ============================================================
# FORGOT PASSWORD
# ============================================================

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
):

    email = request.email.strip().lower()

    user = get_user_by_email(email)

    # --------------------------------------------------------
    # Always return the same response for unknown emails.
    # This prevents account enumeration.
    # --------------------------------------------------------

    if not user:
        return {
            "success": True,
            "message": (
                "If an account exists for this email, "
                "a password reset code has been sent."
            ),
        }

    otp = generate_reset_otp()

    otp_hash = hash_reset_otp(otp)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=RESET_OTP_EXPIRATION_MINUTES
        )
    ).isoformat()

    with get_connection() as connection:

        connection.execute(
            text(
                """
                UPDATE users
                SET
                    reset_otp_hash = :otp_hash,
                    reset_otp_expires_at = :expires_at,
                    reset_otp_attempts = 0
                WHERE user_id = :user_id
                """
            ),
            {
                "otp_hash": otp_hash,
                "expires_at": expires_at,
                "user_id": user[0],
            },
        )

        connection.commit()

    try:

        send_password_reset_otp(
            recipient_email=email,
            otp=otp,
        )

    except Exception as error:

        # ----------------------------------------------------
        # If email delivery fails, invalidate the OTP.
        # ----------------------------------------------------

        with get_connection() as connection:

            connection.execute(
                text(
                    """
                    UPDATE users
                    SET
                        reset_otp_hash = NULL,
                        reset_otp_expires_at = NULL,
                        reset_otp_attempts = 0
                    WHERE user_id = :user_id
                    """
                ),
                {
                    "user_id": user[0],
                },
            )

            connection.commit()

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to send the password reset email. "
                "Please try again later."
            ),
        ) from error

    return {
        "success": True,
        "message": (
            "If an account exists for this email, "
            "a password reset code has been sent."
        ),
    }


# ============================================================
# VERIFY RESET OTP + SET NEW PASSWORD
# ============================================================

@router.post("/verify-reset-otp")
def verify_reset_otp(
    request: VerifyResetOTPRequest,
):

    email = request.email.strip().lower()
    otp = request.otp.strip()

    if not otp.isdigit() or len(otp) != 6:
        raise HTTPException(
            status_code=400,
            detail="Invalid verification code.",
        )

    validate_password(
        request.new_password
    )

    user = get_user_by_email(email)

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code.",
        )

    stored_hash = user[9]
    expires_at_raw = user[10]
    attempts = user[11] or 0

    if not stored_hash or not expires_at_raw:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code.",
        )

    # --------------------------------------------------------
    # Attempt limit
    # --------------------------------------------------------

    if attempts >= RESET_OTP_MAX_ATTEMPTS:

        with get_connection() as connection:

            connection.execute(
                text(
                    """
                    UPDATE users
                    SET
                        reset_otp_hash = NULL,
                        reset_otp_expires_at = NULL,
                        reset_otp_attempts = 0
                    WHERE user_id = :user_id
                    """
                ),
                {
                    "user_id": user[0],
                },
            )

            connection.commit()

        raise HTTPException(
            status_code=400,
            detail=(
                "Too many incorrect attempts. "
                "Please request a new verification code."
            ),
        )

    # --------------------------------------------------------
    # Expiration check
    # --------------------------------------------------------

    try:

        expires_at = datetime.fromisoformat(
            expires_at_raw
        )

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code.",
        )

    if datetime.now(timezone.utc) > expires_at:

        with get_connection() as connection:

            connection.execute(
                text(
                    """
                    UPDATE users
                    SET
                        reset_otp_hash = NULL,
                        reset_otp_expires_at = NULL,
                        reset_otp_attempts = 0
                    WHERE user_id = :user_id
                    """
                ),
                {
                    "user_id": user[0],
                },
            )

            connection.commit()

        raise HTTPException(
            status_code=400,
            detail=(
                "Verification code has expired. "
                "Please request a new code."
            ),
        )

    # --------------------------------------------------------
    # Verify OTP
    # --------------------------------------------------------

    provided_hash = hash_reset_otp(otp)

    if not hmac.compare_digest(
        provided_hash,
        stored_hash,
    ):

        new_attempt_count = attempts + 1

        with get_connection() as connection:

            connection.execute(
                text(
                    """
                    UPDATE users
                    SET reset_otp_attempts = :attempts
                    WHERE user_id = :user_id
                    """
                ),
                {
                    "attempts": new_attempt_count,
                    "user_id": user[0],
                },
            )

            connection.commit()

        remaining = max(
            0,
            RESET_OTP_MAX_ATTEMPTS
            - new_attempt_count,
        )

        if remaining == 0:

            with get_connection() as connection:

                connection.execute(
                    text(
                        """
                        UPDATE users
                        SET
                            reset_otp_hash = NULL,
                            reset_otp_expires_at = NULL,
                            reset_otp_attempts = 0
                        WHERE user_id = :user_id
                        """
                    ),
                    {
                        "user_id": user[0],
                    },
                )

                connection.commit()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Too many incorrect attempts. "
                    "Please request a new verification code."
                ),
            )

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid verification code. "
                f"{remaining} attempt(s) remaining."
            ),
        )

    # --------------------------------------------------------
    # OTP is valid -> update password
    # --------------------------------------------------------

    new_password_hash = hash_password(
        request.new_password
    )

    with get_connection() as connection:

        connection.execute(
            text(
                """
                UPDATE users
                SET
                    password_hash = :password_hash,
                    reset_otp_hash = NULL,
                    reset_otp_expires_at = NULL,
                    reset_otp_attempts = 0
                WHERE user_id = :user_id
                """
            ),
            {
                "password_hash": new_password_hash,
                "user_id": user[0],
            },
        )

        connection.commit()

    return {
        "success": True,
        "message": (
            "Password reset successfully. "
            "Please log in with your new password."
        ),
    }


# ============================================================
# END OF AUTHENTICATION MODULE
# ============================================================