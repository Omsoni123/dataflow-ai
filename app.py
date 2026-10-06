import os
import tempfile
import hashlib
import hmac
import secrets
from datetime import datetime

import streamlit as st
from sqlalchemy import text

from SRC.data_cleaning import process_data
from SRC.database import store_dataset, get_connection
from SRC.analysis import calculate_kpis
from SRC.groq_service import ask_dataset


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="DataFlow AI",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# AUTHENTICATION
# =========================================================

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )
    return salt.hex() + "$" + digest.hex()


def verify_password(password, stored_hash):
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            120_000,
        )

        return hmac.compare_digest(digest.hex(), digest_hex)

    except Exception:
        return False


def ensure_users_table():
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


def create_user(name, email, password):
    name = name.strip()
    email = email.strip().lower()

    with get_connection() as connection:

        existing = connection.execute(
            text(
                "SELECT user_id FROM users WHERE email = :email"
            ),
            {"email": email},
        ).fetchone()

        if existing:
            return False, "An account with this email already exists."

        user_id = secrets.token_urlsafe(18)

        connection.execute(
            text(
                """
                INSERT INTO users
                (user_id, name, email, password_hash, created_at)
                VALUES
                (:user_id, :name, :email, :password_hash, :created_at)
                """
            ),
            {
                "user_id": user_id,
                "name": name,
                "email": email,
                "password_hash": hash_password(password),
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        connection.commit()

    return True, {
        "user_id": user_id,
        "name": name,
        "email": email,
    }


def authenticate_user(email, password):
    email = email.strip().lower()

    with get_connection() as connection:
        user = connection.execute(
            text(
                """
                SELECT user_id, name, email, password_hash
                FROM users
                WHERE email = :email
                """
            ),
            {"email": email},
        ).fetchone()

    if not user:
        return None

    if not verify_password(password, user[3]):
        return None

    return {
        "user_id": user[0],
        "name": user[1],
        "email": user[2],
    }


# Create users table once.
ensure_users_table()


# =========================================================
# SESSION STATE
# =========================================================

session_defaults = {
    "authenticated": False,
    "user": None,
    "auth_page": "login",
    "dataset_id": None,
    "file_name": None,
    "kpis": None,
    "messages": [],
}

for key, value in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# UI / CSS
# =========================================================

st.markdown(
    """
    <style>

    @import url(
        'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
    );

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(
                circle at 82% 5%,
                rgba(139, 44, 255, 0.20),
                transparent 30%
            ),
            radial-gradient(
                circle at 10% 90%,
                rgba(197, 44, 255, 0.10),
                transparent 28%
            ),
            #090611;
        color: #ffffff;
    }

    section[data-testid="stSidebar"] {
        background: rgba(12, 7, 22, 0.97);
        border-right: 1px solid rgba(255,255,255,0.07);
    }

    .hero-title {
        font-size: 44px;
        line-height: 1.08;
        font-weight: 800;
        margin-top: 8px;
        background: linear-gradient(90deg, #ffffff, #d9a7ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
        color: #a79db5;
        font-size: 16px;
        margin: 10px 0 28px;
    }

    .metric-card {
        background: linear-gradient(
            145deg,
            rgba(42,22,67,0.88),
            rgba(18,10,30,0.96)
        );
        border: 1px solid rgba(187,102,255,0.20);
        border-radius: 20px;
        padding: 21px;
        min-height: 118px;
        box-shadow: 0 14px 45px rgba(0,0,0,0.25);
    }

    .metric-label {
        color: #9f93ad;
        font-size: 12px;
        letter-spacing: 0.08em;
        font-weight: 600;
    }

    .metric-value {
        color: #ffffff;
        font-size: 27px;
        font-weight: 800;
        margin-top: 9px;
    }

    .panel {
        background: linear-gradient(
            145deg,
            rgba(42,22,67,0.82),
            rgba(18,10,30,0.96)
        );
        border: 1px solid rgba(187,102,255,0.20);
        border-radius: 22px;
        padding: 30px;
        box-shadow: 0 14px 45px rgba(0,0,0,0.25);
    }

    .ai-box {
        background: linear-gradient(
            145deg,
            rgba(45,17,70,0.90),
            rgba(18,10,30,0.96)
        );
        border: 1px solid rgba(191,87,255,0.30);
        border-radius: 22px;
        padding: 25px;
        margin-top: 22px;
        margin-bottom: 10px;
    }

    .auth-wrap {
        max-width: 470px;
        margin: 8vh auto 0;
    }

    .auth-brand {
        text-align: center;
        font-size: 38px;
        font-weight: 800;
        background: linear-gradient(90deg,#ffffff,#d9a7ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .auth-tag {
        text-align: center;
        color: #a79db5;
        margin: 8px 0 28px;
    }

    .auth-card {
        background: linear-gradient(
            145deg,
            rgba(42,22,67,0.88),
            rgba(18,10,30,0.98)
        );
        border: 1px solid rgba(187,102,255,0.22);
        border-radius: 22px;
        padding: 30px;
        box-shadow: 0 18px 60px rgba(0,0,0,0.35);
    }

    .stButton > button {
        border-radius: 12px;
        border: 1px solid rgba(210,100,255,0.35);
        background: linear-gradient(90deg,#8b2cff,#c52cff);
        color: white;
        font-weight: 700;
        min-height: 44px;
    }

    [data-testid="stChatMessage"] {
        border-radius: 16px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# LOGIN / SIGNUP PAGE
# =========================================================

if not st.session_state.authenticated:

    st.markdown('<div class="auth-wrap">', unsafe_allow_html=True)

    st.markdown(
        '<div class="auth-brand">✦ DataFlow AI</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="auth-tag">Intelligence for your data.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="auth-card">',
        unsafe_allow_html=True,
    )

    if st.session_state.auth_page == "login":

        st.markdown("### Welcome back")
        st.caption("Sign in to your analytics workspace.")

        with st.form("login_form"):

            email = st.text_input(
                "Email",
                placeholder="you@example.com",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="••••••••",
            )

            submitted = st.form_submit_button(
                "Sign In",
                use_container_width=True,
            )

        if submitted:

            if not email or not password:
                st.error("Please enter your email and password.")

            else:
                user = authenticate_user(
                    email,
                    password,
                )

                if user:

                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.rerun()

                else:
                    st.error("Invalid email or password.")

        if st.button(
            "Create an account",
            use_container_width=True,
        ):
            st.session_state.auth_page = "signup"
            st.rerun()

    else:

        st.markdown("### Create your account")
        st.caption("Start your private analytics workspace.")

        with st.form("signup_form"):

            name = st.text_input(
                "Full name",
                placeholder="Your name",
            )

            email = st.text_input(
                "Email",
                placeholder="you@example.com",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="At least 8 characters",
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

        if submitted:

            if not name or not email or not password:
                st.error("Please complete all fields.")

            elif len(password) < 8:
                st.error("Password must be at least 8 characters.")

            elif password != confirm_password:
                st.error("Passwords do not match.")

            else:

                success, result = create_user(
                    name,
                    email,
                    password,
                )

                if success:

                    st.success(
                        "Account created successfully. Please sign in."
                    )

                    st.session_state.auth_page = "login"

                else:
                    st.error(result)

        if st.button(
            "Back to Sign In",
            use_container_width=True,
        ):
            st.session_state.auth_page = "login"
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)

    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ✦ DataFlow AI")
    st.caption("AI-powered analytics workspace")

    st.markdown("---")

    user = st.session_state.user

    st.markdown(f"**{user['name']}**")
    st.caption(user["email"])

    st.markdown("---")

    st.markdown("### Dataset")

    if st.session_state.dataset_id:

        st.success("● Dataset connected")

        st.caption(
            f"File: {st.session_state.file_name}"
        )

        if st.button(
            "↻ Upload New Dataset",
            use_container_width=True,
        ):

            st.session_state.dataset_id = None
            st.session_state.file_name = None
            st.session_state.kpis = None
            st.session_state.messages = []

            st.rerun()

    else:

        st.info("No dataset connected")

    st.markdown("---")

    if st.button(
        "Log out",
        use_container_width=True,
    ):

        for key, value in session_defaults.items():
            st.session_state[key] = value

        st.rerun()


# =========================================================
# MAIN HEADER
# =========================================================

st.markdown(
    '<div class="hero-title">Your data, understood by AI.</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero-subtitle">'
    'Upload your dataset and ask questions naturally. '
    'No SQL required.'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# DATASET UPLOAD
# =========================================================

if st.session_state.dataset_id is None:

    st.markdown(
        """
        <div class="panel" style="text-align:center;">
            <h2>✦ Start with your data</h2>
            <p style="color:#a79db5;">
                Upload a CSV dataset to build your analytics workspace.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Upload dataset",
        type=["csv"],
        label_visibility="collapsed",
    )

    if uploaded_file:

        with st.spinner("Understanding your dataset..."):

            temp_path = os.path.join(
                tempfile.gettempdir(),
                uploaded_file.name,
            )

            with open(temp_path, "wb") as file:
                file.write(
                    uploaded_file.getbuffer()
                )

            data = process_data(temp_path)

            dataset_info = store_dataset(
                data,
                uploaded_file.name,
            )

            kpis = calculate_kpis(data)

            st.session_state.dataset_id = (
                dataset_info["dataset_id"]
            )

            st.session_state.file_name = (
                uploaded_file.name
            )

            st.session_state.kpis = kpis

            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": (
                        f"Your dataset **{uploaded_file.name}** "
                        "is ready. Ask me anything about your data."
                    ),
                }
            ]

            st.rerun()


# =========================================================
# DATASET WORKSPACE
# =========================================================

else:

    kpis = st.session_state.kpis

    st.markdown("### Overview")

    total_sales = kpis.get("total_sales", 0)
    total_profit = kpis.get("total_profit", 0)
    total_units = kpis.get("total_units", 0)
    total_orders = kpis.get("total_orders", 0)

    columns = st.columns(4)

    cards = [
        (
            "TOTAL SALES",
            f"₹{total_sales / 10000000:.2f} Cr",
        ),
        (
            "TOTAL PROFIT",
            f"₹{total_profit / 10000000:.2f} Cr",
        ),
        (
            "UNITS SOLD",
            f"{total_units:,}",
        ),
        (
            "ORDERS",
            f"{total_orders:,}",
        ),
    ]

    for column, (label, value) in zip(
        columns,
        cards,
    ):

        with column:

            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">
                        {label}
                    </div>
                    <div class="metric-value">
                        {value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


    # =====================================================
    # AI ANALYST
    # =====================================================

    st.markdown(
        """
        <div class="ai-box">
            <h2>✦ AI Analyst</h2>
            <p style="color:#a79db5;">
                Ask questions about your dataset in natural language.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])


    question = st.chat_input(
        "Ask your data anything..."
    )


    if question:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": question,
            }
        )

        with st.chat_message("user"):
            st.markdown(question)


        with st.chat_message("assistant"):

            with st.spinner(
                "Analyzing your data..."
            ):

                try:

                    response = ask_dataset(
                        st.session_state.dataset_id,
                        question,
                    )

                    answer = response["answer"]

                    st.markdown(answer)

                    with st.expander(
                        "View analysis details"
                    ):

                        st.code(
                            response["sql"],
                            language="sql",
                        )

                        st.dataframe(
                            response["result"],
                            use_container_width=True,
                        )

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": answer,
                        }
                    )

                except Exception:

                    error_message = (
                        "Sorry, I couldn't analyze that request. "
                        "Please try rephrasing your question."
                    )

                    st.error(error_message)

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": error_message,
                        }
                    )
