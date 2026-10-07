import pandas as pd

from SRC.cleaning_decisions import CleaningDecision


def apply_cleaning_decisions(
    df: pd.DataFrame,
    decision: CleaningDecision
):
    """
    Apply user-selected cleaning decisions to a DataFrame.

    Returns:
        cleaned_df
        cleaning_summary

    The original DataFrame is never modified.
    """

    if df is None or df.empty:
        raise ValueError("Dataset is empty.")

    # ========================================================
    # BEFORE CLEANING
    # ========================================================

    original_row_count = int(len(df))
    original_column_count = int(len(df.columns))
    original_missing_count = int(
        df.isna().sum().sum()
    )
    original_duplicate_count = int(
        df.duplicated().sum()
    )

    # Work on a copy
    cleaned_df = df.copy()

    # Track actions
    duplicate_rows_removed = 0
    column_rows_removed = {}
    filled_values = {}

    # ========================================================
    # 1. DUPLICATE ROWS
    # ========================================================

    if decision.duplicate_rows == "drop":

        before_duplicates = int(
            cleaned_df.duplicated().sum()
        )

        cleaned_df = cleaned_df.drop_duplicates(
            keep="first"
        )

        duplicate_rows_removed = before_duplicates

    # ========================================================
    # 2. TRACK EXPLICIT COLUMN DECISIONS
    # ========================================================

    explicit_columns = {
        column_decision.column
        for column_decision in decision.columns
    }

    # ========================================================
    # 3. COLUMN-SPECIFIC DECISIONS
    # ========================================================

    for column_decision in decision.columns:

        column = column_decision.column
        action = column_decision.action
        fill_value = column_decision.fill_value

        if column not in cleaned_df.columns:
            raise ValueError(
                f"Column '{column}' does not exist in the dataset."
            )

        # ----------------------------------------------------
        # KEEP
        # ----------------------------------------------------

        if action == "keep":
            continue

        # ----------------------------------------------------
        # DROP ROWS
        # ----------------------------------------------------

        if action == "drop_rows":

            rows_before = len(cleaned_df)

            cleaned_df = cleaned_df.dropna(
                subset=[column]
            )

            rows_after = len(cleaned_df)

            column_rows_removed[column] = int(
                rows_before - rows_after
            )

        # ----------------------------------------------------
        # FILL
        # ----------------------------------------------------

        elif action == "fill":

            if fill_value is None:
                raise ValueError(
                    f"Fill value is required for column '{column}'."
                )

            missing_before = int(
                cleaned_df[column].isna().sum()
            )

            cleaned_df[column] = (
                cleaned_df[column].fillna(
                    fill_value
                )
            )

            filled_values[column] = {
                "count": missing_before,
                "fill_value": fill_value
            }

    # ========================================================
    # 4. GLOBAL MISSING-VALUE DECISION
    # ========================================================

    if decision.missing_values == "drop_rows":

        columns_without_explicit_decision = [
            column
            for column in cleaned_df.columns
            if column not in explicit_columns
        ]

        if columns_without_explicit_decision:

            rows_before = len(cleaned_df)

            cleaned_df = cleaned_df.dropna(
                subset=columns_without_explicit_decision
            )

            rows_after = len(cleaned_df)

            global_rows_removed = (
                rows_before - rows_after
            )

        else:
            global_rows_removed = 0

    else:
        global_rows_removed = 0

    # ========================================================
    # 5. GLOBAL KEEP
    # ========================================================

    if decision.missing_values == "keep":
        pass

    # ========================================================
    # 6. GLOBAL FILL
    # ========================================================

    elif decision.missing_values == "fill":
        # Intentionally conservative.
        # We do not guess fill values globally.
        pass

    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    if cleaned_df.empty:
        raise ValueError(
            "Cleaning decisions removed all rows from the dataset."
        )

    cleaned_df = cleaned_df.reset_index(
        drop=True
    )

    # ========================================================
    # AFTER CLEANING
    # ========================================================

    final_row_count = int(len(cleaned_df))
    final_column_count = int(len(cleaned_df.columns))

    final_missing_count = int(
        cleaned_df.isna().sum().sum()
    )

    final_duplicate_count = int(
        cleaned_df.duplicated().sum()
    )

    # ========================================================
    # CLEANING SUMMARY
    # ========================================================

    total_rows_removed = (
        original_row_count - final_row_count
    )

    cleaning_summary = {
        "before": {
            "row_count": original_row_count,
            "column_count": original_column_count,
            "missing_value_count": original_missing_count,
            "duplicate_row_count": original_duplicate_count,
        },

        "after": {
            "row_count": final_row_count,
            "column_count": final_column_count,
            "missing_value_count": final_missing_count,
            "duplicate_row_count": final_duplicate_count,
        },

        "changes": {
            "rows_removed": int(
                total_rows_removed
            ),
            "duplicate_rows_removed": int(
                duplicate_rows_removed
            ),
            "global_missing_rows_removed": int(
                global_rows_removed
            ),
            "column_specific_rows_removed": (
                column_rows_removed
            ),
            "filled_values": filled_values,
        }
    }

    return cleaned_df, cleaning_summary