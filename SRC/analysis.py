import pandas as pd


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

    "order_id": [
        "order_id",
        "orderid",
        "transaction_id",
        "transactionid",
        "invoice_id",
        "invoice_no",
        "order_number"
    ],

    "customer_id": [
        "customer_id",
        "customerid",
        "client_id",
        "clientid",
        "buyer_id",
        "customer_number"
    ],

    "category": [
        "category",
        "product_category",
        "product_type",
        "item_category"
    ],

    "region": [
        "region",
        "state",
        "location",
        "territory",
        "area"
    ],

    "product": [
        "product",
        "product_name",
        "item",
        "item_name",
        "product_title"
    ],

    "order_date": [
        "order_date",
        "date",
        "transaction_date",
        "purchase_date",
        "sales_date",
        "invoice_date"
    ],

    "discount": [
    "discount",
    "discount_rate",
    "discount_percent",
    "discount_percentage",
    "discount_pct"
],
}

def detect_columns(df):
    """Detect the semantic meaning of dataset columns."""

    detected_columns = {}

    # Normalize actual column names
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


def calculate_kpis(df):
    """Calculate available overall sales KPIs."""

    columns = detect_columns(df)

    result = {}

    if "sales" in columns:
        total_sales = df[columns["sales"]].sum()
        result["total_sales"] = total_sales
    else:
        total_sales = None

    if "profit" in columns:
        total_profit = df[columns["profit"]].sum()
        result["total_profit"] = total_profit
    else:
        total_profit = None

    if total_sales not in [None, 0] and total_profit is not None:
        result["profit_margin"] = total_profit / total_sales
    else:
        result["profit_margin"] = None

    if "quantity" in columns:
        result["total_units"] = df[columns["quantity"]].sum()

    if "order_id" in columns:
        result["total_orders"] = df[columns["order_id"]].nunique()

    if "customer_id" in columns:
        result["total_customers"] = df[columns["customer_id"]].nunique()

    return result

def category_analysis(df):
    """Analyze sales and profit by category when available."""

    columns = detect_columns(df)

    if "category" not in columns:
        return {
            "available": False,
            "message": "No category column detected in this dataset."
        }

    category_column = columns["category"]

    aggregation = {}

    if "sales" in columns:
        aggregation[columns["sales"]] = "sum"

    if "profit" in columns:
        aggregation[columns["profit"]] = "sum"

    if not aggregation:
        return {
            "available": False,
            "message": "No sales or profit column detected."
        }

    category_summary = (
        df.groupby(category_column)
        .agg(aggregation)
        .reset_index()
    )

    rename_map = {
        category_column: "Category"
    }

    if "sales" in columns:
        rename_map[columns["sales"]] = "Sales"

    if "profit" in columns:
        rename_map[columns["profit"]] = "Profit"

    category_summary.rename(
        columns=rename_map,
        inplace=True
    )

    result = {
        "available": True,
        "category_summary": category_summary
    }

    if "Sales" in category_summary.columns:

        max_sales = category_summary.loc[
            category_summary["Sales"].idxmax()
        ]

        result["max_sales_category"] = max_sales
        result["highest_sales_category"] = max_sales["Category"]

    if "Profit" in category_summary.columns:

        max_profit = category_summary.loc[
            category_summary["Profit"].idxmax()
        ]

        result["max_profit_category"] = max_profit
        result["highest_profit_category"] = max_profit["Category"]

    return result


def regional_analysis(df):
    """Analyze sales and profit by region when available."""

    columns = detect_columns(df)

    if "region" not in columns:
        return {
            "available": False,
            "message": "No region column detected in this dataset."
        }

    region_column = columns["region"]

    aggregation = {}

    if "sales" in columns:
        aggregation[columns["sales"]] = "sum"

    if "profit" in columns:
        aggregation[columns["profit"]] = "sum"

    if not aggregation:
        return {
            "available": False,
            "message": "No sales or profit column detected."
        }

    regional_summary = (
        df.groupby(region_column)
        .agg(aggregation)
        .reset_index()
    )

    rename_map = {
        region_column: "Region"
    }

    if "sales" in columns:
        rename_map[columns["sales"]] = "Sales"

    if "profit" in columns:
        rename_map[columns["profit"]] = "Profit"

    regional_summary.rename(
        columns=rename_map,
        inplace=True
    )

    result = {
        "available": True,
        "regional_summary": regional_summary
    }

    if "Sales" in regional_summary.columns:

        max_sales = regional_summary.loc[
            regional_summary["Sales"].idxmax()
        ]

        result["highest_sales_region"] = max_sales["Region"]

    if "Profit" in regional_summary.columns:

        max_profit = regional_summary.loc[
            regional_summary["Profit"].idxmax()
        ]

        result["highest_profit_region"] = max_profit["Region"]

    return result

def product_analysis(df):
    """Analyze sales and profit by product when available."""

    columns = detect_columns(df)

    if "product" not in columns:
        return {
            "available": False,
            "message": "No product column detected in this dataset."
        }

    product_column = columns["product"]

    aggregation = {}

    if "sales" in columns:
        aggregation[columns["sales"]] = "sum"

    if "profit" in columns:
        aggregation[columns["profit"]] = "sum"

    if not aggregation:
        return {
            "available": False,
            "message": "No sales or profit column detected."
        }

    product_summary = (
        df.groupby(product_column)
        .agg(aggregation)
        .reset_index()
    )

    rename_map = {
        product_column: "Product"
    }

    if "sales" in columns:
        rename_map[columns["sales"]] = "Sales"

    if "profit" in columns:
        rename_map[columns["profit"]] = "Profit"

    product_summary.rename(
        columns=rename_map,
        inplace=True
    )

    result = {
        "available": True,
        "product_summary": product_summary
    }

    if "Sales" in product_summary.columns:
        result["top_sales_products"] = (
            product_summary
            .sort_values("Sales", ascending=False)
            .head(10)
        )

    if "Profit" in product_summary.columns:
        result["top_profit_products"] = (
            product_summary
            .sort_values("Profit", ascending=False)
            .head(10)
        )

    return result


def monthly_analysis(df):
    """Analyze sales and profit by month when available."""

    columns = detect_columns(df)

    if "order_date" not in columns:
        return {
            "available": False,
            "message": "No date column detected in this dataset."
        }

    date_column = columns["order_date"]

    data = df.copy()

    data[date_column] = pd.to_datetime(
        data[date_column],
        errors="coerce"
    )

    data = data.dropna(subset=[date_column])

    data["Year_Month"] = (
        data[date_column]
        .dt.to_period("M")
        .astype(str)
    )

    aggregation = {}

    if "sales" in columns:
        aggregation[columns["sales"]] = "sum"

    if "profit" in columns:
        aggregation[columns["profit"]] = "sum"

    if not aggregation:
        return {
            "available": False,
            "message": "No sales or profit column detected."
        }

    monthly_summary = (
        data.groupby("Year_Month")
        .agg(aggregation)
        .reset_index()
        .sort_values("Year_Month")
    )

    rename_map = {}

    if "sales" in columns:
        rename_map[columns["sales"]] = "Sales"

    if "profit" in columns:
        rename_map[columns["profit"]] = "Profit"

    monthly_summary.rename(
        columns=rename_map,
        inplace=True
    )

    return {
        "available": True,
        "monthly_summary": monthly_summary
    }


def discount_analysis(df):
    """Analyze discount and profit when available."""

    columns = detect_columns(df)

    if "discount" not in columns:
        return {
            "available": False,
            "message": "No discount column detected in this dataset."
        }

    if "profit" not in columns:
        return {
            "available": False,
            "message": "No profit column detected in this dataset."
        }

    discount_column = columns["discount"]
    profit_column = columns["profit"]

    discount_summary = (
        df.groupby(discount_column)[profit_column]
        .agg(["sum", "mean"])
        .reset_index()
    )

    discount_summary.rename(
        columns={
            discount_column: "Discount",
            "sum": "Total_Profit",
            "mean": "Average_Profit"
        },
        inplace=True
    )

    return {
        "available": True,
        "discount_summary": discount_summary
    }

## -------------------------
# TESTING
# -------------------------

if __name__ == "__main__":

    df = pd.read_csv(
        "C:/Users/Om Soni/OneDrive/Desktop/Sales_analytical_api/Data/sales.csv"
    )

    # -------------------------
    # KPI ANALYSIS
    # -------------------------

    kpi_result = calculate_kpis(df)

    print("\n===== SALES KPIs =====")
    print(kpi_result)


    # -------------------------
    # CATEGORY ANALYSIS
    # -------------------------

    category_result = category_analysis(df)

    print("\n===== CATEGORY ANALYSIS =====")

    if category_result["available"]:

        print(category_result["category_summary"])

        print("\nHighest Sales Category:")
        print(category_result["highest_sales_category"])

        if "highest_profit_category" in category_result:
            print("\nHighest Profit Category:")
            print(category_result["highest_profit_category"])

    else:
        print(category_result["message"])


    # -------------------------
    # REGIONAL ANALYSIS
    # -------------------------

    regional_result = regional_analysis(df)

    print("\n===== REGIONAL ANALYSIS =====")

    if regional_result["available"]:

        print(regional_result["regional_summary"])

        print("\nHighest Sales Region:")
        print(regional_result["highest_sales_region"])

        if "highest_profit_region" in regional_result:
            print("\nHighest Profit Region:")
            print(regional_result["highest_profit_region"])

    else:
        print(regional_result["message"])


    # -------------------------
    # PRODUCT ANALYSIS
    # -------------------------

    product_result = product_analysis(df)

    print("\n===== PRODUCT ANALYSIS =====")

    if product_result["available"]:

        if "top_sales_products" in product_result:
            print("\nTop 10 Products by Sales:")
            print(product_result["top_sales_products"])

        if "top_profit_products" in product_result:
            print("\nTop 10 Products by Profit:")
            print(product_result["top_profit_products"])

    else:
        print(product_result["message"])


    # -------------------------
    # MONTHLY ANALYSIS
    # -------------------------

    monthly_result = monthly_analysis(df)

    print("\n===== MONTHLY ANALYSIS =====")

    if monthly_result["available"]:
        print(monthly_result["monthly_summary"])
    else:
        print(monthly_result["message"])


    # -------------------------
    # DISCOUNT ANALYSIS
    # -------------------------

    discount_result = discount_analysis(df)

    print("\n===== DISCOUNT ANALYSIS =====")

    if discount_result["available"]:
        print(discount_result["discount_summary"])
    else:
        print(discount_result["message"])