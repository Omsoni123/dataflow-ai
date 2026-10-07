import pandas as pd

from SRC.cleaning_decisions import CleaningDecision
from SRC.data_cleaning_engine import apply_cleaning_decisions


df = pd.read_csv("C:/Users/Om Soni/OneDrive/Desktop/Sales_analytical_api/Data/hr_employees_raw.csv")


print("\n================ ORIGINAL DATASET ================\n")

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")
print(f"Missing values: {df.isna().sum().sum()}")
print(f"Duplicate rows: {df.duplicated().sum()}")


# ============================================================
# TEST — COLUMN-SPECIFIC DROP ROWS
# ============================================================

decision = CleaningDecision(
    missing_values="keep",
    duplicate_rows="keep",
    columns=[
        {
            "column": "annual_salary",
            "action": "drop_rows"
        }
    ]
)


cleaned_df, cleaning_summary = apply_cleaning_decisions(
    df,
    decision
)


print("\n================ COLUMN DROP TEST ================\n")

print(
    f"Rows after cleaning: "
    f"{cleaning_summary['after']['row_count']}"
)

print(
    f"Missing values after cleaning: "
    f"{cleaning_summary['after']['missing_value_count']}"
)

print(
    f"Duplicate rows after cleaning: "
    f"{cleaning_summary['after']['duplicate_row_count']}"
)


print("\n================ CHANGES ================\n")

print(
    f"Rows removed: "
    f"{cleaning_summary['changes']['rows_removed']}"
)

print(
    f"Duplicate rows removed: "
    f"{cleaning_summary['changes']['duplicate_rows_removed']}"
)

print(
    f"Global missing rows removed: "
    f"{cleaning_summary['changes']['global_missing_rows_removed']}"
)

print(
    f"Column-specific rows removed: "
    f"{cleaning_summary['changes']['column_specific_rows_removed']}"
)

print(
    f"Filled values: "
    f"{cleaning_summary['changes']['filled_values']}"
)


print("\n================ TEST COMPLETE ================\n")