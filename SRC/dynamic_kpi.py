"""
Universal Dynamic KPI Engine for DataFlow AI.

Purpose:
- Work with ANY structured/tabular dataset.
- Select a small set of meaningful KPI cards automatically.
- Compute KPI values from the actual dataframe.
- Use dataset intelligence metadata when available, but remain safe when metadata is incomplete.
- Avoid domain-specific branches such as HR/Sales/Marketing.

Expected output:
{
    "success": True,
    "kpis": [
        {
            "key": "...",
            "label": "...",
            "value": ...,
            "format": "number|decimal|percent|currency|date|text",
            "aggregation": "...",
            "column": "...",
            "reason": "..."
        }
    ],
    "summary": {...}
}
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Semantic vocabulary
# ---------------------------------------------------------------------------

_AMOUNT_WORDS = {
    "amount", "revenue", "sales", "income", "profit", "loss", "cost",
    "expense", "spend", "salary", "wage", "price", "value", "budget",
    "payment", "payments", "fee", "fees", "margin", "turnover",
    "transaction_value", "order_value", "deal_value", "contract_value",
}

_QUANTITY_WORDS = {
    "quantity", "qty", "units", "unit", "volume", "count", "number",
    "orders", "order_count", "transactions", "transaction_count",
    "tickets", "ticket_count", "items", "item_count", "employees",
    "employee_count", "headcount", "customers", "customer_count",
    "visits", "sessions", "impressions", "clicks", "conversions",
}

_RATE_WORDS = {
    "rate", "ratio", "percent", "percentage", "pct", "margin", "ctr",
    "cvr", "conversion_rate", "growth", "growth_rate", "retention",
    "churn", "utilization", "occupancy", "accuracy", "completion",
    "satisfaction", "score", "rating", "roas", "roi",
}

_CONTINUOUS_WORDS = {
    "age", "temperature", "height", "weight", "distance", "duration",
    "time", "tenure", "experience", "balance", "days", "hours",
    "minutes", "leave", "utilization", "rating", "score",
    "percentage", "percent", "rate",
}

_IDENTIFIER_WORDS = {
    "id", "identifier", "code", "uuid", "key", "number", "no",
}

_DATE_WORDS = {
    "date", "time", "timestamp", "datetime", "created", "updated",
    "modified", "joined", "joining", "start", "end", "deadline",
    "dob", "birth", "purchase", "transaction", "invoice",
}

_CURRENCY_SYMBOLS = ("₹", "$", "€", "£", "¥")

_MAX_KPIS = 6


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def _normalize_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _tokens(column: Any) -> List[str]:
    normalized = _normalize_name(column)
    return [part for part in normalized.split("_") if part]


def _safe_number(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _json_safe(value: Any) -> Any:
    """Convert pandas/numpy/date values into JSON-safe Python values."""
    if value is None:
        return None

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()

    if isinstance(value, bool):
        return value

    number = _safe_number(value)
    if number is not None:
        if float(number).is_integer():
            return int(number)
        return round(number, 6)

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    return str(value)


def _pretty_label(column: Any, aggregation: Optional[str] = None) -> str:
    text = re.sub(r"[_\-]+", " ", str(column).strip())
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        text = "Metric"

    words = text.split()
    text = " ".join(word.capitalize() for word in words)

    if aggregation == "sum":
        return f"Total {text}"
    if aggregation == "mean":
        return f"Average {text}"
    if aggregation == "median":
        return f"Median {text}"
    if aggregation == "count":
        return f"{text} Count"
    if aggregation == "nunique":
        return f"Unique {text}"

    return text


def _column_meta(
    column: Any,
    series: pd.Series,
    intelligence: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge dataframe facts with optional intelligence metadata."""
    meta: Dict[str, Any] = {}

    columns_meta = (intelligence or {}).get("columns", [])
    if isinstance(columns_meta, list):
        for item in columns_meta:
            if not isinstance(item, dict):
                continue
            if str(item.get("name")) == str(column):
                meta.update(item)
                break

    role = str(meta.get("role") or "").lower()
    dtype = str(meta.get("dtype") or "").lower()

    return {
        "role": role,
        "dtype": dtype,
        "name": str(column),
        "normalized": _normalize_name(column),
        "tokens": _tokens(column),
        "series": series,
    }


def _contains_token(meta: Dict[str, Any], vocabulary: Iterable[str]) -> bool:
    normalized = meta["normalized"]
    tokens = set(meta["tokens"])

    for word in vocabulary:
        normalized_word = _normalize_name(word)

        if normalized_word in tokens:
            return True

        if normalized == normalized_word:
            return True

        # Support useful compound names such as conversion_rate or total_revenue.
        if normalized_word and normalized_word in normalized:
            return True

    return False


def _is_identifier(meta: Dict[str, Any]) -> bool:
    role = meta["role"]
    if role in {"identifier", "id"}:
        return True

    tokens = set(meta["tokens"])
    normalized = meta["normalized"]

    if "id" in tokens or normalized.endswith("_id"):
        return True

    if any(token in tokens for token in {"uuid", "guid", "identifier"}):
        return True

    return False


def _is_date_like(meta: Dict[str, Any]) -> bool:
    role = meta["role"]
    dtype = meta["dtype"]

    if role in {"datetime", "date", "timestamp"}:
        return True

    if "datetime" in dtype or "date" in dtype or "timestamp" in dtype:
        return True

    return _contains_token(meta, _DATE_WORDS)


def _coerce_numeric(series: pd.Series) -> Optional[pd.Series]:
    if pd.api.types.is_bool_dtype(series):
        return None

    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce")
    else:
        # Be conservative with text. Do not turn arbitrary IDs into numbers.
        cleaned = (
            series.astype("string")
            .str.strip()
            .str.replace(",", "", regex=False)
            .str.replace(r"^[₹$€£¥]\s*", "", regex=True)
        )
        numeric = pd.to_numeric(cleaned, errors="coerce")

    valid = numeric.notna().sum()
    non_empty = series.notna().sum()

    if non_empty == 0:
        return None

    # Numeric-like strings are accepted only when almost all non-empty values
    # are numeric. This keeps names/codes from becoming fake metrics.
    if valid / non_empty < 0.90:
        return None

    return numeric


def _looks_like_ratio_metric(meta: Dict[str, Any]) -> bool:
    """Metrics such as ROAS/ROI are ratios, not percentage-point values."""
    return _contains_token(meta, {"roas", "roi", "ratio"})


def _looks_like_percentage_metric(meta: Dict[str, Any]) -> bool:
    return _contains_token(
        meta,
        {
            "percent", "percentage", "pct", "rate", "margin",
            "ctr", "cvr", "conversion_rate", "growth", "retention",
            "churn", "utilization", "occupancy", "accuracy",
            "completion", "satisfaction",
        },
    )


def _looks_like_per_entity_amount(meta: Dict[str, Any]) -> bool:
    """Amounts that are usually measurements per entity rather than totals."""
    return _contains_token(
        meta,
        {
            "salary", "wage", "price", "unit_price", "hourly_rate",
            "monthly_salary", "annual_salary", "base_salary",
            "average_price", "ticket_price",
        },
    )


def _looks_like_rate(meta: Dict[str, Any], series: pd.Series) -> bool:
    if _contains_token(meta, _RATE_WORDS):
        return True

    numeric = _coerce_numeric(series)
    if numeric is None:
        return False

    clean = numeric.dropna()
    if clean.empty:
        return False

    # Only infer a percentage/rate from values when the column name gives
    # reasonably strong semantic evidence. Avoid guessing on arbitrary 0-100
    # numeric columns such as age.
    if _contains_token(meta, {"ratio", "fraction"}):
        return True

    return False


def _looks_like_amount(meta: Dict[str, Any]) -> bool:
    return _contains_token(meta, _AMOUNT_WORDS)


def _looks_like_quantity(meta: Dict[str, Any]) -> bool:
    return _contains_token(meta, _QUANTITY_WORDS)


def _looks_like_continuous(meta: Dict[str, Any]) -> bool:
    return _contains_token(meta, _CONTINUOUS_WORDS)


def _looks_like_currency(meta: Dict[str, Any]) -> bool:
    normalized = meta["normalized"]

    if any(symbol in str(meta["name"]) for symbol in _CURRENCY_SYMBOLS):
        return True

    return _looks_like_amount(meta) or any(
        token in normalized
        for token in {
            "salary", "revenue", "sales", "profit", "cost", "expense",
            "spend", "price", "payment", "budget", "income",
        }
    )


def _format_for_metric(
    meta: Dict[str, Any],
    aggregation: str,
) -> str:
    if _looks_like_ratio_metric(meta):
        return "decimal"

    if _looks_like_percentage_metric(meta):
        return "percent"

    if _looks_like_currency(meta):
        return "currency"

    if aggregation in {"count", "nunique"}:
        return "number"

    if pd.api.types.is_integer_dtype(meta["series"]):
        return "number"

    return "decimal"


def _score_numeric_column(meta: Dict[str, Any]) -> Tuple[float, str]:
    """
    Score how useful a numeric column is as a headline KPI.

    This is deliberately domain-neutral.
    """
    series = meta["series"]
    normalized = meta["normalized"]

    if _is_identifier(meta):
        return -100.0, "Identifier-like field"

    if _is_date_like(meta):
        return -100.0, "Date/time field"

    numeric = _coerce_numeric(series)
    if numeric is None:
        return -100.0, "Not numeric enough"

    non_null = numeric.dropna()
    if non_null.empty:
        return -100.0, "No usable numeric values"

    score = 0.0
    reasons: List[str] = []

    unique_ratio = non_null.nunique() / max(len(non_null), 1)

    if _looks_like_rate(meta, series):
        score += 40
        reasons.append("rate/percentage semantic")

    if _looks_like_amount(meta):
        score += 35
        reasons.append("amount/value semantic")

    if _looks_like_quantity(meta):
        score += 28
        reasons.append("quantity/count semantic")

    if _looks_like_continuous(meta):
        score += 18
        reasons.append("continuous metric semantic")

    role = meta["role"]
    if role in {"metric", "measure", "numeric"}:
        score += 18
        reasons.append("numeric metric role")

    if role in {"categorical", "text"}:
        score -= 20
        reasons.append("categorical/text role")

    # A field with only one unique value is not useful as a KPI.
    if non_null.nunique() <= 1:
        score -= 50
        reasons.append("constant field")

    # Very high-cardinality values can be identifiers even when not named "id".
    if unique_ratio > 0.995 and not (
        _looks_like_amount(meta)
        or _looks_like_rate(meta, series)
        or _looks_like_quantity(meta)
    ):
        score -= 20
        reasons.append("near-unique values")

    # Penalize common personal/technical fields that are technically numeric.
    if normalized in {
        "phone", "mobile", "postal_code", "zip_code", "pincode",
        "account_number", "employee_number",
    }:
        score -= 80
        reasons.append("technical identifier")

    return score, "; ".join(reasons) or "usable numeric metric"


def _choose_aggregation(meta: Dict[str, Any]) -> str:
    """Choose a meaningful aggregation using semantic precedence.

    The order matters: continuous measurements such as age, balances,
    durations and leave days should normally be averaged even though some
    of their names also describe a quantity. Additive measures such as
    revenue, spend, units and counts are summed.
    """
    series = meta["series"]
    normalized = meta["normalized"]

    if _looks_like_rate(meta, series):
        return "mean"

    if _looks_like_per_entity_amount(meta):
        return "mean"

    if _looks_like_amount(meta):
        return "sum"

    # Explicit total/count/quantity naming is stronger than a generic
    # continuous word. This remains domain-neutral.
    explicit_additive = {
        "count", "total", "quantity", "qty", "units", "unit_count",
        "order_count", "transaction_count", "ticket_count", "item_count",
        "employee_count", "customer_count", "visits", "sessions",
        "impressions", "clicks", "conversions", "volume",
    }
    if any(token in explicit_additive for token in meta["tokens"]):
        return "sum"

    if _looks_like_continuous(meta):
        return "mean"

    if _looks_like_quantity(meta):
        return "sum"

    if meta["role"] in {"metric", "measure", "numeric"}:
        return "mean"

    return "mean"


def _compute_aggregation(series: pd.Series, aggregation: str) -> Any:
    numeric = _coerce_numeric(series)

    if aggregation == "count":
        return int(series.notna().sum())

    if aggregation == "nunique":
        return int(series.dropna().nunique())

    if numeric is None:
        return None

    clean = numeric.dropna()
    if clean.empty:
        return None

    if aggregation == "sum":
        return clean.sum()

    if aggregation == "mean":
        return clean.mean()

    if aggregation == "median":
        return clean.median()

    if aggregation == "min":
        return clean.min()

    if aggregation == "max":
        return clean.max()

    return clean.mean()


def _build_numeric_candidates(
    df: pd.DataFrame,
    intelligence: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for column in df.columns:
        meta = _column_meta(column, df[column], intelligence)
        score, reason = _score_numeric_column(meta)

        if score <= -50:
            continue

        aggregation = _choose_aggregation(meta)
        value = _compute_aggregation(meta["series"], aggregation)

        if value is None:
            continue

        # Small preference for semantic metrics, while keeping the engine
        # universal and data-driven.
        candidates.append(
            {
                "kind": "numeric",
                "column": str(column),
                "aggregation": aggregation,
                "value": _json_safe(value),
                "format": _format_for_metric(meta, aggregation),
                "score": round(score, 3),
                "reason": reason,
                "normalized": meta["normalized"],
            }
        )

    return sorted(
        candidates,
        key=lambda item: (-item["score"], item["column"].lower()),
    )


def _build_count_candidates(
    df: pd.DataFrame,
    intelligence: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for column in df.columns:
        meta = _column_meta(column, df[column], intelligence)

        if not _is_identifier(meta):
            continue

        non_null = df[column].dropna()
        unique_count = int(non_null.nunique())
        if unique_count <= 1:
            continue

        coverage = unique_count / max(len(df), 1)
        # Prefer identifiers representing the dataset's main entities. A key
        # that is almost unique per row is usually more useful than a parent
        # or grouping identifier with much lower cardinality.
        score = 14.0 + (18.0 * min(coverage, 1.0))

        candidates.append(
            {
                "kind": "unique_count",
                "column": str(column),
                "aggregation": "nunique",
                "value": unique_count,
                "format": "number",
                "score": round(score, 3),
                "reason": "identifier-like field with useful entity coverage",
                "normalized": meta["normalized"],
            }
        )

    return sorted(
        candidates,
        key=lambda item: (-item["score"], item["column"].lower()),
    )


def _build_category_count_candidates(
    df: pd.DataFrame,
    intelligence: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find useful low-cardinality dimensions for datasets without many measures."""
    candidates: List[Dict[str, Any]] = []

    for column in df.columns:
        meta = _column_meta(column, df[column], intelligence)

        if _is_identifier(meta) or _is_date_like(meta):
            continue

        role = meta["role"]
        if role not in {"categorical", "category", "text", ""}:
            continue

        non_null = df[column].dropna()
        unique_count = int(non_null.nunique())
        if unique_count < 2 or unique_count > 50:
            continue

        coverage = non_null.nunique() / max(len(non_null), 1)
        score = 8.0 + min(unique_count, 20) / 4.0
        if coverage < 0.5:
            score += 2.0

        candidates.append(
            {
                "kind": "category_count",
                "column": str(column),
                "aggregation": "nunique",
                "value": unique_count,
                "format": "number",
                "score": round(score, 3),
                "reason": "categorical dimension with useful cardinality",
                "normalized": meta["normalized"],
            }
        )

    return sorted(
        candidates,
        key=lambda item: (-item["score"], item["column"].lower()),
    )


def _build_row_count_candidate(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        "kind": "row_count",
        "column": None,
        "aggregation": "count_rows",
        "value": int(len(df)),
        "format": "number",
        "score": 32.0,
        "reason": "universal dataset volume KPI",
        "normalized": "__rows__",
    }


def _build_date_range_candidate(
    df: pd.DataFrame,
    intelligence: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    date_candidates: List[Tuple[str, pd.Series]] = []

    for column in df.columns:
        meta = _column_meta(column, df[column], intelligence)

        if not _is_date_like(meta):
            continue

        parsed = pd.to_datetime(df[column], errors="coerce")
        if parsed.notna().sum() < 2:
            continue

        date_candidates.append((str(column), parsed))

    if not date_candidates:
        return None

    # Prefer the field with the largest valid date coverage.
    column, parsed = max(
        date_candidates,
        key=lambda item: int(item[1].notna().sum()),
    )

    valid = parsed.dropna()
    if valid.empty:
        return None

    start = valid.min()
    end = valid.max()

    return {
        "kind": "date_range",
        "column": column,
        "aggregation": "date_range",
        "value": {
            "start": _json_safe(start),
            "end": _json_safe(end),
        },
        "format": "date",
        "score": 9.0,
        "reason": "available time coverage in the dataset",
        "normalized": _normalize_name(column),
    }


def _deduplicate_semantic_metrics(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Avoid cards that are effectively duplicates.

    Examples:
    - do not show both a generic row count and a numeric order_count sum
      when they are identical.
    - do not show multiple aggregations of the same column.
    """
    output: List[Dict[str, Any]] = []
    seen_keys = set()

    for item in candidates:
        value = item.get("value")

        if item["kind"] == "numeric":
            key = (
                item["normalized"],
                item["aggregation"],
            )

            if key in seen_keys:
                continue

            # A numeric count field equal to total rows adds little value.
            if (
                item["aggregation"] == "sum"
                and item["normalized"] in {
                    "count", "row_count", "record_count", "records",
                }
                and value == len(candidates)
            ):
                continue

            seen_keys.add(key)

        output.append(item)

    return output


def _select_headline_candidates(
    df: pd.DataFrame,
    intelligence: Optional[Dict[str, Any]],
    max_kpis: int,
) -> List[Dict[str, Any]]:
    numeric = _build_numeric_candidates(df, intelligence)
    unique_counts = _build_count_candidates(df, intelligence)
    category_counts = _build_category_count_candidates(df, intelligence)

    all_candidates: List[Dict[str, Any]] = [
        _build_row_count_candidate(df),
        *numeric,
        *unique_counts,
        *category_counts,
    ]

    # Date coverage is useful, but it should not displace meaningful business
    # metrics when the dataset already has enough strong numeric KPIs.
    date_range = _build_date_range_candidate(df, intelligence)
    if date_range is not None:
        all_candidates.append(date_range)

    all_candidates = sorted(
        all_candidates,
        key=lambda item: (-float(item.get("score", 0)), item.get("column") or ""),
    )

    selected: List[Dict[str, Any]] = []
    seen_columns = set()

    # Always keep row count as the universal first card.
    row_candidate = next(
        (item for item in all_candidates if item["kind"] == "row_count"),
        None,
    )
    if row_candidate is not None:
        selected.append(row_candidate)

    unique_count_added = False
    category_count_added = 0

    for item in all_candidates:
        if len(selected) >= max_kpis:
            break

        if item["kind"] == "row_count":
            continue

        if item["kind"] == "unique_count":
            if unique_count_added:
                continue
            unique_count_added = True

        if item["kind"] == "category_count":
            if category_count_added >= 1:
                continue
            category_count_added += 1

        column = item.get("column")
        if column is not None and column in seen_columns:
            continue

        # Avoid weak/meaningless candidates unless the dataset is very small.
        if float(item.get("score", 0)) < 10:
            continue

        if column is not None:
            seen_columns.add(column)

        selected.append(item)

    # If the dataset has no meaningful metrics, row count remains a valid KPI.
    return selected[:max_kpis]


def _candidate_to_public_kpi(item: Dict[str, Any]) -> Dict[str, Any]:
    kind = item["kind"]

    if kind == "row_count":
        return {
            "key": "row_count",
            "label": "Total Rows",
            "value": _json_safe(item["value"]),
            "format": "number",
            "aggregation": "count_rows",
            "column": None,
            "reason": item["reason"],
        }

    if kind == "date_range":
        column = item["column"]
        return {
            "key": f"{_normalize_name(column)}_date_range",
            "label": f"{column} Range",
            "value": _json_safe(item["value"]),
            "format": "date",
            "aggregation": "date_range",
            "column": column,
            "reason": item["reason"],
        }

    if kind in {"unique_count", "category_count"}:
        column = item["column"]
        label = (
            _pretty_label(column, "nunique")
            if kind == "unique_count"
            else f"{_pretty_label(column)} Categories"
        )
        return {
            "key": f"unique_{_normalize_name(column)}",
            "label": label,
            "value": _json_safe(item["value"]),
            "format": "number",
            "aggregation": "nunique",
            "column": column,
            "reason": item["reason"],
        }

    column = item["column"]
    aggregation = item["aggregation"]

    return {
        "key": f"{_normalize_name(column)}_{aggregation}",
        "label": _pretty_label(column, aggregation),
        "value": _json_safe(item["value"]),
        "format": item["format"],
        "aggregation": aggregation,
        "column": column,
        "reason": item["reason"],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_dynamic_kpis(
    df: pd.DataFrame,
    intelligence: Optional[Dict[str, Any]] = None,
    max_kpis: int = _MAX_KPIS,
) -> Dict[str, Any]:
    """
    Generate actual KPI cards for an arbitrary dataframe.

    Parameters
    ----------
    df:
        Cleaned/analysis-ready pandas DataFrame.
    intelligence:
        Optional output from SRC.dataset_intelligence.analyze_dataset().
        The engine still works without it.
    max_kpis:
        Maximum number of headline KPI cards.

    Returns
    -------
    dict
        JSON-safe KPI payload.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("generate_dynamic_kpis expects a pandas DataFrame.")

    if max_kpis < 1:
        raise ValueError("max_kpis must be at least 1.")

    if df.empty:
        return {
            "success": False,
            "message": "Cannot generate KPIs from an empty dataset.",
            "kpis": [],
            "summary": {
                "row_count": 0,
                "column_count": int(len(df.columns)),
                "kpi_count": 0,
            },
        }

    selected = _select_headline_candidates(
        df=df,
        intelligence=intelligence,
        max_kpis=min(int(max_kpis), 10),
    )

    kpis = [_candidate_to_public_kpi(item) for item in selected]

    return {
        "success": True,
        "message": "Dynamic KPIs generated successfully.",
        "kpis": kpis,
        "summary": {
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "numeric_column_count": int(
                sum(
                    _coerce_numeric(df[column]) is not None
                    for column in df.columns
                )
            ),
            "kpi_count": int(len(kpis)),
        },
    }


# Short alias for future endpoint/service usage.
get_dynamic_kpis = generate_dynamic_kpis
