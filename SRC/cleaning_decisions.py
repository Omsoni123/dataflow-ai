from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# COLUMN CLEANING DECISION
# ============================================================

class ColumnCleaningDecision(BaseModel):
    """
    Defines what should happen to missing values
    in a specific column.
    """

    column: str

    action: Literal[
        "keep",
        "drop_rows",
        "fill"
    ] = "keep"

    fill_value: Optional[str] = None


# ============================================================
# DATASET CLEANING DECISION
# ============================================================

class CleaningDecision(BaseModel):
    """
    User-controlled cleaning instructions for a dataset.
    """

    missing_values: Literal[
        "keep",
        "drop_rows",
        "fill"
    ] = "keep"

    duplicate_rows: Literal[
        "keep",
        "drop"
    ] = "keep"

    columns: list[ColumnCleaningDecision] = Field(
        default_factory=list
    )