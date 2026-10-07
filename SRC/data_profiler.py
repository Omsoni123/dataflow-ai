import re

import pandas as pd


# ============================================================
# SMART NUMERIC DETECTION
# ============================================================

def detect_numeric_like_columns(df: pd.DataFrame) -> list:
    """
    Detect columns that contain numeric values even when
    pandas originally loaded them as strings.
    """

    numeric_columns = []

    for column in df.columns:
        series = df[column]

        # Already numeric
        if pd.api.types.is_numeric_dtype(series):
            numeric_columns.append(str(column))
            continue

        # Only inspect text/object columns
        if not (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
        ):
            continue

        non_null = series.dropna()

        if non_null.empty:
            continue

        try:
            cleaned = (
                non_null.astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("$", "", regex=False)
                .str.replace("₹", "", regex=False)
                .str.replace("€", "", regex=False)
                .str.replace("£", "", regex=False)
                .str.strip()
            )

            converted = pd.to_numeric(
                cleaned,
                errors="coerce"
            )

            valid_ratio = converted.notna().mean()

            if valid_ratio >= 0.80:
                numeric_columns.append(str(column))

        except Exception:
            continue

    return numeric_columns


# ============================================================
# DATE VALUE NORMALIZATION
# ============================================================

def normalize_date_value(value: str) -> str:
    """
    Normalize common messy date strings before parsing.

    Examples:

    Tuesday, 01 April 2014
    ->
    01 April 2014

    Friday, 29 March 2019
    ->
    29 March 2019
    """

    value = str(value).strip()

    # Remove weekday names at the beginning
    value = re.sub(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+",
        "",
        value,
        flags=re.IGNORECASE
    )

    return value.strip()


# ============================================================
# SMART DATE DETECTION
# ============================================================

def detect_date_like_columns(
    df: pd.DataFrame,
    numeric_columns: list
) -> list:
    """
    Detect columns containing date-like values.

    Handles mixed formats such as:

    16/11/2015
    Tuesday, 01 April 2014
    07-24-2022
    22.11.15
    03-Mar-2017
    Aug 21, 2019
    2014-10-29
    2021/06/09
    """

    date_columns = []

    date_name_keywords = [
        "date",
        "datetime",
        "timestamp",
        "joined",
        "joining",
        "created",
        "updated",
        "birth",
        "dob",
        "start",
        "end",
    ]

    for column in df.columns:
        column_name = str(column)
        column_lower = column_name.lower()

        # Numeric columns should never be treated as dates
        if column_name in numeric_columns:
            continue

        series = df[column]

        # Already datetime
        if pd.api.types.is_datetime64_any_dtype(series):
            date_columns.append(column_name)
            continue

        # Only inspect text/object columns
        if not (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
        ):
            continue

        non_null = series.dropna()

        if non_null.empty:
            continue

        try:
            normalized_values = (
                non_null
                .astype(str)
                .apply(normalize_date_value)
            )

            parsed = pd.to_datetime(
                normalized_values,
                errors="coerce",
                format="mixed"
            )

            valid_ratio = parsed.notna().mean()

            # Strong evidence from actual values
            if valid_ratio >= 0.80:
                date_columns.append(column_name)
                continue

            # Column name strongly suggests date.
            # Allow a slightly lower threshold for messy
            # real-world date columns.
            has_date_name = any(
                keyword in column_lower
                for keyword in date_name_keywords
            )

            if has_date_name and valid_ratio >= 0.60:
                date_columns.append(column_name)

        except Exception:
            continue

    return date_columns


# ============================================================
# PROFILE DATA
# ============================================================

def profile_data(df: pd.DataFrame) -> dict:
    """
    Inspect a dataset without modifying it.

    Returns a JSON-serializable data quality and
    structural profile.
    """

    if df is None or df.empty:
        raise ValueError("Dataset is empty.")

    # ---------------------------------------------------------
    # Basic information
    # ---------------------------------------------------------

    row_count = int(len(df))
    column_count = int(len(df.columns))

    # ---------------------------------------------------------
    # Missing values
    # ---------------------------------------------------------

    missing_values_by_column = {}

    for column in df.columns:
        missing_count = int(
            df[column].isna().sum()
        )

        if missing_count > 0:
            missing_values_by_column[str(column)] = missing_count

    total_missing_values = int(
        df.isna().sum().sum()
    )

    # ---------------------------------------------------------
    # Duplicate rows
    # ---------------------------------------------------------

    duplicate_row_count = int(
        df.duplicated().sum()
    )

    # ---------------------------------------------------------
    # Smart type inference
    # ---------------------------------------------------------

    numeric_columns = detect_numeric_like_columns(df)

    date_columns = detect_date_like_columns(
        df,
        numeric_columns
    )

    # ---------------------------------------------------------
    # Boolean detection
    # ---------------------------------------------------------

    boolean_columns = [
        str(column)
        for column in df.select_dtypes(
            include="bool"
        ).columns
    ]

    # ---------------------------------------------------------
    # Text columns
    # ---------------------------------------------------------

    text_columns = []

    for column in df.columns:
        column_name = str(column)

        if column_name in numeric_columns:
            continue

        if column_name in date_columns:
            continue

        if column_name in boolean_columns:
            continue

        if (
            pd.api.types.is_object_dtype(df[column])
            or pd.api.types.is_string_dtype(df[column])
        ):
            text_columns.append(column_name)

    # ---------------------------------------------------------
    # Column-level profile
    # ---------------------------------------------------------

    columns = []

    for column in df.columns:
        series = df[column]
        column_name = str(column)

        # Every column gets ONE primary type
        if column_name in date_columns:
            detected_type = "date"

        elif column_name in numeric_columns:
            detected_type = "numeric"

        elif column_name in boolean_columns:
            detected_type = "boolean"

        else:
            detected_type = "text"

        columns.append(
            {
                "name": column_name,
                "dtype": detected_type,
                "missing": int(
                    series.isna().sum()
                ),
                "unique_values": int(
                    series.nunique(
                        dropna=True
                    )
                ),
            }
        )

    # ---------------------------------------------------------
    # Final profile
    # ---------------------------------------------------------

    return {
        "row_count": row_count,
        "column_count": column_count,

        "columns": columns,

        "missing_value_count": total_missing_values,

        "missing_values_by_column": (
            missing_values_by_column
        ),

        "duplicate_row_count": duplicate_row_count,

        "numeric_columns": numeric_columns,

        "text_columns": text_columns,

        "date_columns": date_columns,

        "boolean_columns": boolean_columns,
    }