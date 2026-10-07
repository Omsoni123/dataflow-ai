import pandas as pd

from SRC.cleaning_decisions import CleaningDecision
from SRC.data_cleaning_engine import apply_cleaning_decisions


# ============================================================
# LOAD TEST DATASET
# ============================================================

df = pd.read_csv("C:/Users/Om Soni/OneDrive/Desktop/Sales_analytical_api/Data/hr_employees_raw.csv")

print("\n================ BEFORE CLEANING ================\n")

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")
print(f"Missing values: {df.isna().sum().sum()}")
print(f"Duplicate rows: {df.duplicated().sum()}")


# ============================================================
# USER CLEANING DECISION
# ============================================================

decision = CleaningDecision(
    missing_values="drop_rows",
    duplicate_rows="drop",
    columns=[
        {
            "column": "annual_salary",
            "action": "fill",
            "fill_value": "0"
        },
        {
            "column": "joining_date",
            "action": "keep"
        }
    ]
)


# ============================================================
# APPLY CLEANING
# ============================================================

cleaned_df = apply_cleaning_decisions(
    df,
    decision
)


# ============================================================
# RESULTS
# ============================================================

print("\n================ AFTER CLEANING ================\n")

print(f"Rows: {len(cleaned_df)}")
print(f"Columns: {len(cleaned_df.columns)}")
print(f"Missing values: {cleaned_df.isna().sum().sum()}")
print(f"Duplicate rows: {cleaned_df.duplicated().sum()}")


print("\n================ CLEANING COMPLETE ================\n")