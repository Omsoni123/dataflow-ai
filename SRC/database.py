import os
import uuid
import json
import re
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


# --------------------------------------------------
# ENVIRONMENT
# --------------------------------------------------

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env")


# Render may provide postgres://
# SQLAlchemy expects postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql+psycopg2://",
        1
    )


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


def get_connection():
    """Create and return a PostgreSQL database connection."""
    return engine.connect()


# --------------------------------------------------
# CREATE METADATA TABLE
# --------------------------------------------------

def create_metadata_table():
    """Create the datasets metadata table if it does not exist."""

    with get_connection() as connection:

        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                user_id TEXT,
                file_name TEXT NOT NULL,
                table_name TEXT NOT NULL UNIQUE,
                uploaded_at TEXT NOT NULL,
                row_count INTEGER,
                column_count INTEGER,
                schema TEXT
            )
        """))

        # --------------------------------------------------
        # MIGRATION FOR EXISTING DATABASES
        # --------------------------------------------------
        # If the datasets table already existed before user
        # ownership was added, this safely adds the column.
        # Existing rows will simply have user_id = NULL.

        connection.execute(text("""
            ALTER TABLE datasets
            ADD COLUMN IF NOT EXISTS user_id TEXT
        """))

        # Helpful index for finding a user's latest dataset
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_datasets_user_uploaded
            ON datasets (user_id, uploaded_at DESC)
        """))

        connection.commit()


# --------------------------------------------------
# GENERATE DATASET ID
# --------------------------------------------------

def generate_dataset_id():
    """Generate a unique dataset ID."""

    return str(uuid.uuid4())


# --------------------------------------------------
# GENERATE TABLE NAME
# --------------------------------------------------

def generate_table_name(dataset_id):
    """Generate a safe PostgreSQL table name."""

    short_id = dataset_id.replace("-", "")[:12]

    return f"dataset_{short_id}"


# --------------------------------------------------
# CLEAN COLUMN NAMES FOR DATABASE
# --------------------------------------------------

def sanitize_column_name(column_name):
    """Convert a column name into a database-safe name."""

    column_name = str(column_name).strip().lower()

    column_name = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        column_name
    )

    column_name = re.sub(
        r"_+",
        "_",
        column_name
    )

    if column_name and column_name[0].isdigit():
        column_name = f"column_{column_name}"

    return column_name


# --------------------------------------------------
# PREPARE DATAFRAME
# --------------------------------------------------

def prepare_dataframe(df):
    """Prepare dataframe before storing it in PostgreSQL."""

    df = df.copy()

    new_columns = []
    used_names = set()

    for column in df.columns:

        clean_name = sanitize_column_name(column)

        original_name = clean_name
        counter = 1

        while clean_name in used_names:

            clean_name = f"{original_name}_{counter}"

            counter += 1

        used_names.add(clean_name)

        new_columns.append(clean_name)

    df.columns = new_columns

    return df


# --------------------------------------------------
# CREATE DATASET TABLE
# --------------------------------------------------

def create_dataset_table(df, table_name):
    """Create a unique PostgreSQL table for the uploaded dataset."""

    df.to_sql(
        table_name,
        engine,
        if_exists="fail",
        index=False
    )


# --------------------------------------------------
# SAVE DATASET METADATA
# --------------------------------------------------

def save_dataset_metadata(
    dataset_id,
    user_id,
    file_name,
    table_name,
    df
):
    """Save dataset information and ownership metadata."""

    schema = {
        str(column): str(dtype)
        for column, dtype in df.dtypes.items()
    }

    with get_connection() as connection:

        connection.execute(
            text("""
                INSERT INTO datasets (
                    dataset_id,
                    user_id,
                    file_name,
                    table_name,
                    uploaded_at,
                    row_count,
                    column_count,
                    schema
                )
                VALUES (
                    :dataset_id,
                    :user_id,
                    :file_name,
                    :table_name,
                    :uploaded_at,
                    :row_count,
                    :column_count,
                    :schema
                )
            """),
            {
                "dataset_id": dataset_id,
                "user_id": user_id,
                "file_name": file_name,
                "table_name": table_name,
                "uploaded_at": datetime.now().isoformat(),
                "row_count": len(df),
                "column_count": len(df.columns),
                "schema": json.dumps(schema)
            }
        )

        connection.commit()


# --------------------------------------------------
# STORE COMPLETE DATASET
# --------------------------------------------------

def store_dataset(df, file_name, user_id):
    """
    Store a processed dataset in its own PostgreSQL table
    and save its metadata with user ownership.
    """

    create_metadata_table()

    # Generate unique identifiers
    dataset_id = generate_dataset_id()

    table_name = generate_table_name(dataset_id)

    # Prepare dataframe
    df = prepare_dataframe(df)

    # Create dataset table
    create_dataset_table(
        df,
        table_name
    )

    # Save metadata
    save_dataset_metadata(
        dataset_id,
        user_id,
        file_name,
        table_name,
        df
    )

    return {
        "dataset_id": dataset_id,
        "table_name": table_name,
        "row_count": len(df),
        "column_count": len(df.columns)
    }


# --------------------------------------------------
# GET DATASET METADATA
# --------------------------------------------------

def get_dataset_metadata(dataset_id):
    """Get metadata for a specific dataset."""

    with get_connection() as connection:

        result = connection.execute(
            text("""
                SELECT
                    dataset_id,
                    user_id,
                    file_name,
                    table_name,
                    uploaded_at,
                    row_count,
                    column_count,
                    schema
                FROM datasets
                WHERE dataset_id = :dataset_id
            """),
            {
                "dataset_id": dataset_id
            }
        )

        row = result.fetchone()

    if row is None:
        return None

    return {
        "dataset_id": row[0],
        "user_id": row[1],
        "file_name": row[2],
        "table_name": row[3],
        "uploaded_at": row[4],
        "row_count": row[5],
        "column_count": row[6],
        "schema": json.loads(row[7])
    }


# --------------------------------------------------
# GET USER'S LATEST DATASET
# --------------------------------------------------

def get_latest_dataset_for_user(user_id):
    """
    Get the most recently uploaded dataset belonging
    to the authenticated user.
    """

    with get_connection() as connection:

        result = connection.execute(
            text("""
                SELECT
                    dataset_id,
                    user_id,
                    file_name,
                    table_name,
                    uploaded_at,
                    row_count,
                    column_count,
                    schema
                FROM datasets
                WHERE user_id = :user_id
                ORDER BY uploaded_at DESC
                LIMIT 1
            """),
            {
                "user_id": user_id
            }
        )

        row = result.fetchone()

    if row is None:
        return None

    return {
        "dataset_id": row[0],
        "user_id": row[1],
        "file_name": row[2],
        "table_name": row[3],
        "uploaded_at": row[4],
        "row_count": row[5],
        "column_count": row[6],
        "schema": json.loads(row[7])
    }


# --------------------------------------------------
# LOAD DATASET
# --------------------------------------------------

def load_dataset(dataset_id):
    """Load a stored dataset using its dataset ID."""

    metadata = get_dataset_metadata(dataset_id)

    if metadata is None:
        raise ValueError(
            f"Dataset not found: {dataset_id}"
        )

    table_name = metadata["table_name"]

    query = text(
        f'SELECT * FROM "{table_name}"'
    )

    with get_connection() as connection:

        df = pd.read_sql_query(
            query,
            connection
        )

    return df


# --------------------------------------------------
# GET DATASET SCHEMA
# --------------------------------------------------

def get_dataset_schema(dataset_id):
    """Return the schema of a stored dataset."""

    metadata = get_dataset_metadata(dataset_id)

    if metadata is None:
        raise ValueError(
            f"Dataset not found: {dataset_id}"
        )

    return metadata["schema"]


# --------------------------------------------------
# QUERY DATASET
# --------------------------------------------------

def query_dataset(dataset_id, query):
    """
    Execute a validated SQL query against a specific dataset.
    """

    # ----------------------------------------------
    # Validate SQL first
    # ----------------------------------------------

    is_valid, message = validate_sql(
        dataset_id,
        query
    )

    if not is_valid:
        raise ValueError(message)

    # ----------------------------------------------
    # Execute query
    # ----------------------------------------------

    with get_connection() as connection:

        result = pd.read_sql_query(
            text(query),
            connection
        )

    return result


# --------------------------------------------------
# SQL VALIDATION
# --------------------------------------------------

FORBIDDEN_SQL_KEYWORDS = {
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA"
}


def validate_sql(dataset_id, query):
    """
    Validate SQL before execution.

    Security rules:

    1. Only SELECT statements are allowed.
    2. Multiple SQL statements are blocked.
    3. Dangerous SQL operations are blocked.
    4. Query must reference the requested dataset table.
    5. SQL syntax and referenced columns are checked by PostgreSQL.
    """

    # ----------------------------------------------
    # Get dataset metadata
    # ----------------------------------------------

    metadata = get_dataset_metadata(dataset_id)

    if metadata is None:
        return False, "Dataset not found."

    table_name = metadata["table_name"]

    # ----------------------------------------------
    # Basic query validation
    # ----------------------------------------------

    query = query.strip()

    if not query:
        return False, "SQL query is empty."

    # ----------------------------------------------
    # Only SELECT allowed
    # ----------------------------------------------

    if not query.upper().startswith("SELECT"):
        return False, "Only SELECT statements are allowed."

    # ----------------------------------------------
    # Multiple statements
    # ----------------------------------------------

    statements = [
        statement.strip()
        for statement in query.split(";")
        if statement.strip()
    ]

    if len(statements) > 1:
        return False, "Multiple SQL statements are not allowed."

    # ----------------------------------------------
    # Forbidden operations
    # ----------------------------------------------

    upper_query = query.upper()

    for keyword in FORBIDDEN_SQL_KEYWORDS:

        if keyword in upper_query:

            return False, (
                f"Forbidden SQL operation detected: {keyword}"
            )

    # ----------------------------------------------
    # Correct dataset table
    # ----------------------------------------------

    if table_name.lower() not in query.lower():

        return False, (
            "Query does not reference the requested dataset."
        )

    # ----------------------------------------------
    # Validate SQL using PostgreSQL
    # ----------------------------------------------

    try:

        with get_connection() as connection:

            explain_query = text(
                f"EXPLAIN {query}"
            )

            connection.execute(
                explain_query
            )

    except SQLAlchemyError as error:

        error_message = str(error)

        if "column" in error_message.lower():

            return False, (
                f"Invalid column or SQL reference: "
                f"{error_message}"
            )

        if "relation" in error_message.lower():

            return False, (
                f"Invalid table reference: "
                f"{error_message}"
            )

        return False, (
            f"Invalid SQL query: "
            f"{error_message}"
        )

    # ----------------------------------------------
    # Validation successful
    # ----------------------------------------------

    return True, "SQL validation passed."