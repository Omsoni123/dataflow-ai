import pandas as pd


# --------------------------------------------------
# COLUMN ALIASES
# --------------------------------------------------

COLUMN_ALIASES = {

    "sales": [
        "sales",
        "sale",
        "revenue",
        "total_sales",
        "sales_amount",
        "revenue_amount",
        "net_sales",
        "net_revenue"
    ],

    "profit": [
        "profit",
        "net_profit",
        "gross_profit",
        "profit_amount",
        "net_income"
    ],

    "quantity": [
        "quantity",
        "qty",
        "units",
        "units_sold",
        "unit_sold"
    ],

    "cost": [
        "cost",
        "total_cost",
        "cost_amount",
        "product_cost"
    ],

    "discount": [
        "discount",
        "discount_rate",
        "discount_percent",
        "discount_percentage",
        "discount_pct"
    ],

    "order_id": [
        "order_id",
        "orderid",
        "transaction_id",
        "transactionid",
        "invoice_id",
        "invoice_no",
        "order_number"
    ],

    "order_date": [
        "order_date",
        "date",
        "transaction_date",
        "purchase_date",
        "sales_date",
        "invoice_date"
    ]
}


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

def load_data(file_path):
    """Load CSV data."""

    return pd.read_csv(file_path)


# --------------------------------------------------
# DETECT COLUMNS
# --------------------------------------------------

def detect_columns(df):
    """Detect semantic meaning of dataset columns."""

    detected_columns = {}

    normalized_columns = {
        str(column).strip().lower().replace(" ", "_"): column
        for column in df.columns
    }

    for semantic_name, aliases in COLUMN_ALIASES.items():

        for alias in aliases:

            if alias in normalized_columns:
                detected_columns[semantic_name] = normalized_columns[alias]
                break

    return detected_columns


# --------------------------------------------------
# VALIDATE DATA
# --------------------------------------------------

def validate_data(df):
    """Run dynamic data-quality checks."""

    errors = []

    columns = detect_columns(df)

    # -----------------------------
    # Missing values
    # -----------------------------

    missing_values = df.isnull().sum().sum()

    if missing_values > 0:
        errors.append(
            f"Missing values found: {missing_values}"
        )

    # -----------------------------
    # Duplicate records
    # -----------------------------

    duplicate_rows = df.duplicated().sum()

    if duplicate_rows > 0:
        errors.append(
            f"Duplicate rows found: {duplicate_rows}"
        )

    # -----------------------------
    # Duplicate IDs
    # -----------------------------

    if "order_id" in columns:

        order_column = columns["order_id"]

        duplicate_orders = df[order_column].duplicated().sum()

        if duplicate_orders > 0:
            errors.append(
                f"Duplicate order IDs found: {duplicate_orders}"
            )

    # -----------------------------
    # Invalid quantity
    # -----------------------------

    if "quantity" in columns:

        quantity_column = columns["quantity"]

        if (df[quantity_column] <= 0).any():
            errors.append(
                "Invalid quantity found"
            )

    # -----------------------------
    # Negative sales
    # -----------------------------

    if "sales" in columns:

        sales_column = columns["sales"]

        if (df[sales_column] < 0).any():
            errors.append(
                "Negative sales/revenue found"
            )

    # -----------------------------
    # Negative profit
    # -----------------------------

    if "profit" in columns:

        profit_column = columns["profit"]

        # NOTE:
        # Negative profit can be legitimate.
        # Therefore we DO NOT treat it as an error.
        pass

    # -----------------------------
    # Negative cost
    # -----------------------------

    if "cost" in columns:

        cost_column = columns["cost"]

        if (df[cost_column] < 0).any():
            errors.append(
                "Negative cost found"
            )

    # -----------------------------
    # Invalid discount
    # -----------------------------

    if "discount" in columns:

        discount_column = columns["discount"]

        if (
            (df[discount_column] < 0)
            | (df[discount_column] > 1)
        ).any():

            errors.append(
                "Invalid discount found"
            )

    # -----------------------------
    # Result
    # -----------------------------

    if errors:
        return False, errors

    return True, ["Data validation passed"]


# --------------------------------------------------
# CLEAN DATA
# --------------------------------------------------

def clean_data(df):
    """Clean and prepare dataset dynamically."""

    df = df.copy()

    columns = detect_columns(df)

    # -----------------------------
    # Standardize column names
    # -----------------------------

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    # Re-detect after cleaning names
    columns = detect_columns(df)

    # -----------------------------
    # Convert date
    # -----------------------------

    if "order_date" in columns:

        date_column = columns["order_date"]

        df[date_column] = pd.to_datetime(
            df[date_column],
            errors="coerce"
        )

    # -----------------------------
    # Remove duplicate IDs
    # -----------------------------

    if "order_id" in columns:

        order_column = columns["order_id"]

        df = df.drop_duplicates(
            subset=order_column
        )

    else:

        # If no ID exists,
        # remove completely duplicated rows
        df = df.drop_duplicates()

    # -----------------------------
    # Sort by date
    # -----------------------------

    if "order_date" in columns:

        date_column = columns["order_date"]

        df = df.sort_values(
            by=date_column
        )

    return df


# --------------------------------------------------
# COMPLETE PIPELINE
# --------------------------------------------------

def process_data(file_path):
    """Run complete automated data-processing pipeline."""

    print("\n==============================")
    print("DATA PROCESSING PIPELINE")
    print("==============================")

    # -----------------------------
    # Load
    # -----------------------------

    print("\nLoading data...")

    df = load_data(file_path)

    print(
        f"Loaded {len(df):,} records"
    )

    print(
        f"Detected {len(df.columns)} columns"
    )

    # -----------------------------
    # Detect columns
    # -----------------------------

    columns = detect_columns(df)

    print("\nDetected columns:")

    for semantic_name, actual_column in columns.items():

        print(
            f"  {semantic_name} → {actual_column}"
        )

    # -----------------------------
    # Validate
    # -----------------------------

    print("\nValidating data...")

    is_valid, messages = validate_data(df)

    for message in messages:
        print(message)

    if not is_valid:

        raise ValueError(
            "Data validation failed"
        )

    # -----------------------------
    # Clean
    # -----------------------------

    print("\nCleaning data...")

    df = clean_data(df)

    print(
        f"Final records: {len(df):,}"
    )

    print("\nData processing completed successfully.")

    return df