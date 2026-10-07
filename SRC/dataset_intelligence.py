"""


DataFlow AI - Universal Dataset Intelligence


Purpose:


    Understand ANY structured pandas DataFrame without assuming that it


    belongs to sales, HR, marketing, finance, etc.


Design:


    1. Profile column semantics using names + values + dtypes.


    2. Classify columns into reusable analytical roles.


    3. Generate deterministic, data-supported metric candidates.


    4. Infer an optional dataset domain only when evidence is strong.


    5. Always fall back to general_analytics for unknown datasets.


This module does NOT calculate industry-specific dashboards.


It provides a universal semantic layer that future dashboard/KPI engines


can consume.


"""


from __future__ import annotations


import math


import re


from typing import Any


import pandas as pd


# ============================================================


# SEMANTIC VOCABULARY


# ============================================================


SEMANTIC_HINTS: dict[str, set[str]] = {


    "identifier": {


        "id",


        "key",


        "code",


        "uuid",


        "identifier",


        "number",


        "no",


        "ref",


        "reference",


    },


    "person": {


        "name",


        "employee",


        "staff",


        "student",


        "patient",


        "customer",


        "client",


        "user",


        "member",


        "contact",


        "candidate",


    },


    "amount": {


        "amount",


        "value",


        "price",


        "cost",


        "salary",


        "revenue",


        "sales",


        "profit",


        "income",


        "expense",


        "spend",


        "budget",


        "balance",


        "payment",


        "fee",


        "revenue",


        "total",


    },


    "quantity": {


        "quantity",


        "qty",


        "count",


        "units",


        "volume",


        "number_of",


        "headcount",


        "hours",


        "days",


        "score",


        "rating",


        "points",


    },


    "percentage": {


        "percent",


        "percentage",


        "pct",


        "rate",


        "margin",


        "ratio",


        "share",


        "conversion",


        "ctr",


        "roas",


    },


    "date": {


        "date",


        "time",


        "timestamp",


        "created",


        "updated",


        "modified",


        "joined",


        "joining",


        "start",


        "end",


        "birth",


        "dob",


        "month",


        "year",


        "day",


    },


    "location": {


        "country",


        "state",


        "city",


        "region",


        "area",


        "location",


        "territory",


        "zone",


        "address",


        "zip",


        "zipcode",


        "postal",


    },


    "category": {


        "category",


        "type",


        "class",


        "segment",


        "department",


        "division",


        "group",


        "status",


        "channel",


        "source",


        "platform",


        "gender",


        "level",


        "priority",


    },


    "product": {


        "product",


        "item",


        "sku",


        "model",


        "service",


        "plan",


        "course",


        "asset",


    },


}


DOMAIN_HINTS: dict[str, set[str]] = {


    "sales": {


        "sales",


        "revenue",


        "order",


        "orders",


        "quantity",


        "unit_price",


        "product",


        "customer",


        "discount",


        "profit",


    },


    "human_resources": {


        "employee",


        "staff",


        "salary",


        "department",


        "joining_date",


        "hire_date",


        "leave",


        "attrition",


        "performance",


        "designation",


    },


    "marketing": {


        "campaign",


        "impressions",


        "clicks",


        "ctr",


        "conversion",


        "conversions",


        "spend",


        "roas",


        "lead",


        "leads",


    },


    "finance": {


        "revenue",


        "expense",


        "income",


        "profit",


        "cost",


        "asset",


        "liability",


        "equity",


        "cash",


        "balance",


        "transaction",


    },


    "inventory": {


        "inventory",


        "stock",


        "warehouse",


        "sku",


        "quantity",


        "available",


        "reorder",


        "supplier",


    },


    "operations": {


        "operation",


        "process",


        "production",


        "output",


        "downtime",


        "cycle",


        "efficiency",


        "defect",


        "quality",


    },


    "education": {


        "student",


        "course",


        "subject",


        "grade",


        "marks",


        "score",


        "teacher",


        "attendance",


        "classroom",


    },


    "healthcare": {


        "patient",


        "diagnosis",


        "treatment",


        "doctor",


        "hospital",


        "medicine",


        "symptom",


        "admission",


    },


    "logistics": {


        "shipment",


        "delivery",


        "carrier",


        "warehouse",


        "tracking",


        "dispatch",


        "shipping",


        "route",


        "transport",


    },


}


# ============================================================


# HELPERS


# ============================================================


def _normalize_name(value: Any) -> str:


    text = str(value).strip().lower()


    text = re.sub(r"[^a-z0-9]+", "_", text)


    text = re.sub(r"_+", "_", text).strip("_")


    return text


def _tokens(value: Any) -> set[str]:


    normalized = _normalize_name(value)


    return set(normalized.split("_")) if normalized else set()


def _json_safe(value: Any) -> Any:


    if value is None:


        return None


    if isinstance(value, (pd.Timestamp,)):


        return value.isoformat()


    if hasattr(value, "item"):


        try:


            value = value.item()


        except Exception:


            pass


    if isinstance(value, float):


        if math.isnan(value) or math.isinf(value):


            return None


    if isinstance(value, (str, int, float, bool)):


        return value


    return str(value)


def _name_matches(column_name: str, vocabulary: set[str]) -> int:


    normalized = _normalize_name(column_name)


    tokens = _tokens(column_name)


    score = 0


    if normalized in vocabulary:


        score += 4


    for word in vocabulary:


        if word in tokens:


            score += 2


        elif word in normalized:


            score += 1


    return score


def _is_boolean_series(series: pd.Series) -> bool:


    if pd.api.types.is_bool_dtype(series):


        return True


    non_null = series.dropna()


    if non_null.empty:


        return False


    values = {


        str(value).strip().lower()


        for value in non_null.head(500).unique()


    }


    return values.issubset(


        {


            "true",


            "false",


            "yes",


            "no",


            "y",


            "n",


            "0",


            "1",


        }


    ) and len(values) <= 2


def _try_datetime(series: pd.Series, column_name: str) -> tuple[bool, pd.Series]:


    if pd.api.types.is_datetime64_any_dtype(series):


        return True, pd.to_datetime(series, errors="coerce")


    name_score = _name_matches(column_name, SEMANTIC_HINTS["date"])


    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):


        return False, series


    non_null = series.dropna()


    if non_null.empty:


        return False, series


    sample = non_null.head(500)


    # Conservative parsing: a column must either strongly look like a date


    # by name or have a high successful parsing ratio.


    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")


    parse_ratio = float(parsed.notna().mean())


    is_date = (


        name_score >= 2 and parse_ratio >= 0.70


    ) or parse_ratio >= 0.90


    if not is_date:


        return False, series


    return True, pd.to_datetime(series, errors="coerce", format="mixed")


def _try_numeric(series: pd.Series) -> tuple[bool, pd.Series, float]:
    """Safely detect and convert numeric-like string columns."""
    if pd.api.types.is_numeric_dtype(series):
        converted = pd.to_numeric(series, errors="coerce")
        return True, converted, 1.0
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return False, series, 0.0
    non_null = series.dropna()
    if non_null.empty:
        return False, series, 0.0
    cleaned = (non_null.astype(str).str.strip()
        .str.replace(r"[₹$€£]", "", regex=True)
        .str.replace(r"(?i)^rs\.?\s*", "", regex=True)
        .str.replace(r"(?i)\s*(inr|usd|eur|gbp)$", "", regex=True)
        .str.replace(",", "", regex=False).str.replace("%", "", regex=False)
        .str.replace(r"\s+", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True))
    converted_non_null = pd.to_numeric(cleaned, errors="coerce")
    parse_ratio = float(converted_non_null.notna().mean())
    converted = pd.to_numeric(series.astype(str).str.strip()
        .str.replace(r"[₹$€£]", "", regex=True)
        .str.replace(r"(?i)^rs\.?\s*", "", regex=True)
        .str.replace(r"(?i)\s*(inr|usd|eur|gbp)$", "", regex=True)
        .str.replace(",", "", regex=False).str.replace("%", "", regex=False)
        .str.replace(r"\s+", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True), errors="coerce")
    name_signal = max(_name_matches(str(series.name), SEMANTIC_HINTS["amount"]),
                      _name_matches(str(series.name), SEMANTIC_HINTS["quantity"]),
                      _name_matches(str(series.name), SEMANTIC_HINTS["percentage"]))
    threshold = 0.80 if name_signal >= 2 else 0.90
    return parse_ratio >= threshold, converted, parse_ratio


def _looks_like_identifier(series: pd.Series, column_name: str) -> bool:

    non_null = series.dropna()


    if non_null.empty:

        return False


    unique_ratio = non_null.nunique(dropna=True) / len(non_null)

    normalized = _normalize_name(column_name)

    tokens = _tokens(column_name)


    # Strong identifier names.

    strong_exact = {

        "id",

        "key",

        "uuid",

        "identifier",

        "code",

    }


    if normalized in strong_exact and unique_ratio >= 0.30:

        return True


    # Strong suffixes are reliable for entity identifiers.

    strong_suffixes = (

        "_id",

        "_key",

        "_uuid",

        "_code",

        "_no",

    )


    if normalized.endswith(strong_suffixes) and unique_ratio >= 0.30:

        return True


    # "number" is ambiguous by itself, so require an entity token.

    entity_tokens = {

        "order",

        "customer",

        "client",

        "employee",

        "staff",

        "student",

        "patient",

        "invoice",

        "transaction",

        "shipment",

        "product",

        "account",

        "member",

        "user",

        "ticket",

        "record",

    }


    if "number" in tokens and tokens.intersection(entity_tokens):

        if unique_ratio >= 0.30:

            return True


    # UUID-like values.

    sample = non_null.astype(str).head(100)


    if not sample.empty:

        uuid_ratio = sample.str.match(

            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"

            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

        ).mean()


        if uuid_ratio >= 0.80:

            return True


    return False


def infer_column_role(


    df: pd.DataFrame,


    column_name: str,


) -> dict[str, Any]:


    series = df[column_name]


    missing = int(series.isna().sum())


    non_null = series.dropna()


    unique_values = int(series.nunique(dropna=True))


    if non_null.empty:


        return {


            "role": "empty",


            "dtype": str(series.dtype),


            "semantic_tags": [],


            "confidence": 1.0,


            "missing": missing,


            "unique_values": unique_values,


        }


    if _is_boolean_series(series):


        return {


            "role": "boolean",


            "dtype": str(series.dtype),


            "semantic_tags": ["boolean"],


            "confidence": 0.98,


            "missing": missing,


            "unique_values": unique_values,


        }


    is_date, parsed_dates = _try_datetime(series, column_name)


    if is_date:


        return {


            "role": "datetime",


            "dtype": "datetime",


            "semantic_tags": ["date", "time"],


            "confidence": 0.95,


            "missing": missing,


            "unique_values": unique_values,


            "date_min": _json_safe(parsed_dates.min()),


            "date_max": _json_safe(parsed_dates.max()),


        }


    # Protect identifiers before numeric conversion. Numeric-looking IDs must

    # never become business metrics.

    if _looks_like_identifier(series, column_name):

        return {

            "role": "identifier",

            "dtype": str(series.dtype),

            "semantic_tags": ["identifier"],

            "confidence": 0.88,

            "missing": missing,

            "unique_values": unique_values,

        }


    # Handle real numeric columns and numeric-like strings consistently.

    is_numeric, numeric_series, numeric_parse_ratio = _try_numeric(series)


    if is_numeric:

        tags = []


        if _name_matches(column_name, SEMANTIC_HINTS["amount"]) >= 2:

            tags.append("measure")


        if _name_matches(column_name, {"salary", "wage", "compensation", "pay"}) >= 2:

            tags.append("amount")


        if _name_matches(column_name, SEMANTIC_HINTS["quantity"]) >= 2:

            tags.append("quantity")


        if _name_matches(column_name, {"score", "rating"}) >= 2:

            tags.append("rating")


        if _name_matches(column_name, SEMANTIC_HINTS["percentage"]) >= 2:

            tags.append("rate")


        valid_numeric = numeric_series.dropna()


        if not valid_numeric.empty:

            return {

                "role": "numeric",

                "dtype": "numeric",

                "semantic_tags": sorted(set(tags)),

                "confidence": round(

                    min(0.97, 0.86 + numeric_parse_ratio * 0.10),

                    3,

                ),

                "missing": missing,

                "unique_values": unique_values,

                "unique_ratio": round(

                    unique_values / max(len(non_null), 1),

                    4,

                ),

                "min": _json_safe(valid_numeric.min()),

                "max": _json_safe(valid_numeric.max()),

                "mean": _json_safe(valid_numeric.mean()),

                "median": _json_safe(valid_numeric.median()),

            }


    unique_ratio = unique_values / max(len(non_null), 1)


    category_score = _name_matches(


        column_name,


        SEMANTIC_HINTS["category"],


    )


    if unique_values <= 50 and unique_ratio <= 0.50:


        role = "categorical"


        confidence = 0.90


    elif category_score >= 2 and unique_ratio <= 0.80:


        role = "categorical"


        confidence = 0.82


    else:


        role = "text"


        confidence = 0.85


    return {


        "role": role,


        "dtype": str(series.dtype),


        "semantic_tags": [],


        "confidence": confidence,


        "missing": missing,


        "unique_values": unique_values,


        "unique_ratio": round(unique_ratio, 4),


    }


# ============================================================


# DOMAIN INFERENCE


# ============================================================


def infer_dataset_domain(
    df: pd.DataFrame,
    column_roles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Infer the most likely dataset domain from the structure of the data.

    Important design rule:
        Domain detection is OPTIONAL metadata. It must never restrict
        the universal analytics engine to a fixed industry.

    The engine therefore:
      1. Scores every configured domain using column-name evidence.
      2. Uses semantic column roles as supporting evidence.
      3. Rewards evidence spread across multiple columns.
      4. Penalizes weak one-column matches.
      5. Falls back to ``general_analytics`` when the evidence is weak
         or when the dataset belongs to a domain we do not explicitly know.

    Adding a new domain is therefore a vocabulary/configuration change,
    not a change to the core intelligence algorithm.
    """

    # ------------------------------------------------------------
    # Domain vocabulary
    # ------------------------------------------------------------
    # DOMAIN_HINTS is intentionally only a set of optional semantic
    # fingerprints. The rest of the engine remains domain-agnostic.
    # ------------------------------------------------------------
    domain_hints: dict[str, set[str]] = {
        **DOMAIN_HINTS,
        "ecommerce": {
            "cart", "checkout", "sku", "product", "order", "orders",
            "customer", "customer_id", "price", "quantity", "discount",
            "shipping", "delivery", "return", "refund", "rating",
        },
        "customer_support": {
            "ticket", "case", "issue", "complaint", "agent", "resolution",
            "response_time", "handle_time", "priority", "status", "channel",
            "satisfaction", "csat", "nps", "escalation", "support",
        },
        "website_analytics": {
            "session", "sessions", "pageview", "pageviews", "visitor",
            "visitors", "user", "users", "bounce_rate", "session_duration",
            "impressions", "clicks", "conversion", "traffic", "source",
            "device", "browser", "landing_page", "referrer",
        },
        "social_media": {
            "post", "posts", "likes", "comments", "shares", "followers",
            "reach", "engagement", "impressions", "mentions", "hashtag",
            "views", "reactions", "platform", "creator",
        },
        "project_management": {
            "project", "task", "tasks", "milestone", "sprint", "assignee",
            "owner", "deadline", "due_date", "start_date", "end_date",
            "completion", "progress", "status", "priority", "hours",
            "effort", "budget", "dependency",
        },
        "procurement": {
            "supplier", "vendor", "purchase_order", "po", "procurement",
            "purchasing", "unit_cost", "quantity", "lead_time", "delivery",
            "invoice", "payment_terms", "buyer", "category",
        },
        "accounting": {
            "account", "account_code", "debit", "credit", "journal",
            "ledger", "invoice", "tax", "payment", "balance", "fiscal_year",
            "gl", "transaction", "expense", "reconciliation",
        },
        "real_estate": {
            "property", "listing", "rent", "sale_price", "property_type",
            "bedrooms", "bathrooms", "area_sqft", "address", "city",
            "neighborhood", "mortgage", "tenant", "landlord", "valuation",
        },
        "survey": {
            "respondent", "response", "question", "answer", "rating",
            "satisfaction", "feedback", "survey", "likert", "demographic",
            "age", "gender", "comment",
        },
        "manufacturing": {
            "production", "machine", "batch", "plant", "factory", "output",
            "defect", "downtime", "cycle_time", "yield", "quality",
            "operator", "work_order", "maintenance", "scrap",
        },
        "telecommunications": {
            "subscriber", "call", "calls", "sms", "data_usage", "plan",
            "network", "cell", "tower", "bandwidth", "latency", "drop_rate",
            "churn", "usage", "device",
        },
        "transportation": {
            "vehicle", "trip", "route", "driver", "distance", "fuel",
            "mileage", "departure", "arrival", "delay", "passenger",
            "fare", "journey", "fleet",
        },
        "energy": {
            "energy", "electricity", "power", "consumption", "generation",
            "voltage", "current", "meter", "kwh", "mw", "load", "outage",
            "solar", "gas", "oil",
        },
        "insurance": {
            "policy", "policyholder", "claim", "premium", "coverage",
            "deductible", "incident", "beneficiary", "risk", "underwriting",
            "loss", "settlement",
        },
        "banking": {
            "account", "account_number", "transaction", "balance", "deposit",
            "withdrawal", "loan", "interest", "branch", "card", "merchant",
            "credit_score", "payment", "transfer",
        },
        "education": {
            "student", "course", "subject", "grade", "marks", "score",
            "teacher", "attendance", "classroom", "semester", "exam",
            "assignment", "school", "college", "university",
        },
        "healthcare": {
            "patient", "diagnosis", "treatment", "doctor", "hospital",
            "medicine", "symptom", "admission", "discharge", "procedure",
            "prescription", "lab", "test", "dosage",
        },
        "logistics": {
            "shipment", "delivery", "carrier", "warehouse", "tracking",
            "dispatch", "shipping", "route", "transport", "package",
            "parcel", "freight", "destination", "origin",
        },
    }

    scores: dict[str, float] = {domain: 0.0 for domain in domain_hints}
    evidence: dict[str, list[str]] = {domain: [] for domain in domain_hints}
    matched_columns: dict[str, set[str]] = {domain: set() for domain in domain_hints}

    # ------------------------------------------------------------
    # Score each column independently.
    # ------------------------------------------------------------
    for column_name, info in column_roles.items():
        normalized = _normalize_name(column_name)
        tokens = _tokens(column_name)
        role = info.get("role")

        for domain, vocabulary in domain_hints.items():
            column_score = 0.0
            matched: list[str] = []

            for hint in vocabulary:
                hint_normalized = _normalize_name(hint)
                hint_tokens = _tokens(hint)

                if not hint_tokens:
                    continue

                # Exact field-name match is strong evidence.
                if normalized == hint_normalized:
                    column_score += 4.0
                    matched.append(hint_normalized)
                    continue

                # Multi-word / compound semantic match.
                if hint_normalized in normalized:
                    column_score += 1.5
                    matched.append(hint_normalized)
                    continue

                # Token overlap. Require at least one meaningful token.
                overlap = tokens.intersection(hint_tokens)
                if overlap:
                    column_score += min(2.0, 1.0 + 0.5 * len(overlap))
                    matched.extend(sorted(overlap))

            if column_score <= 0:
                continue

            # Structured analytical columns provide slightly stronger
            # evidence than free-form text columns.
            role_multiplier = {
                "identifier": 0.90,
                "text": 0.85,
                "categorical": 1.05,
                "numeric": 1.05,
                "datetime": 1.05,
                "boolean": 0.95,
            }.get(role, 1.0)

            column_score *= role_multiplier
            scores[domain] += column_score
            matched_columns[domain].add(column_name)

            if matched:
                evidence[domain].extend(matched[:5])

    # ------------------------------------------------------------
    # Reward domains whose evidence comes from multiple columns.
    # This prevents a single generic field such as "status" or "user"
    # from deciding the entire dataset domain.
    # ------------------------------------------------------------
    for domain, columns in matched_columns.items():
        distinct_columns = len(columns)

        if distinct_columns >= 5:
            scores[domain] += 5.0
        elif distinct_columns >= 4:
            scores[domain] += 3.5
        elif distinct_columns >= 3:
            scores[domain] += 2.0
        elif distinct_columns == 2:
            scores[domain] += 0.75
        elif distinct_columns == 1:
            scores[domain] *= 0.65

    # ------------------------------------------------------------
    # Remove duplicate evidence while preserving order.
    # ------------------------------------------------------------
    for domain in evidence:
        evidence[domain] = list(dict.fromkeys(evidence[domain]))[:10]

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    if not ranked or ranked[0][1] <= 0:
        return {
            "domain": "general_analytics",
            "confidence": 0.50,
            "alternatives": [],
        }

    best_domain, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    best_column_count = len(matched_columns[best_domain])

    # ------------------------------------------------------------
    # Confidence gate.
    # A domain should only be surfaced when there is enough
    # multi-column evidence. Otherwise the dataset remains universal.
    # ------------------------------------------------------------
    minimum_score = 5.0

    if best_score < minimum_score or best_column_count == 0:
        return {
            "domain": "general_analytics",
            "confidence": 0.55,
            "alternatives": [
                {
                    "domain": domain,
                    "score": round(score, 2),
                    "evidence_columns": len(matched_columns[domain]),
                }
                for domain, score in ranked[:3]
                if score > 0
            ],
        }

    # A one-column match is intentionally never considered high confidence.
    if best_column_count == 1 and best_score < 8:
        return {
            "domain": "general_analytics",
            "confidence": 0.58,
            "alternatives": [
                {
                    "domain": domain,
                    "score": round(score, 2),
                    "evidence_columns": len(matched_columns[domain]),
                }
                for domain, score in ranked[:3]
                if score > 0
            ],
        }

    separation = max(best_score - second_score, 0.0)

    confidence = min(
        0.98,
        0.55
        + min(best_score / 35.0, 0.25)
        + min(separation / 20.0, 0.12)
        + min(best_column_count / 20.0, 0.08),
    )

    return {
        "domain": best_domain,
        "confidence": round(confidence, 3),
        "evidence_columns": best_column_count,
        "evidence": evidence[best_domain],
        "alternatives": [
            {
                "domain": domain,
                "score": round(score, 2),
                "evidence_columns": len(matched_columns[domain]),
            }
            for domain, score in ranked[1:4]
            if score > 0
        ],
    }


# UNIVERSAL KPI CANDIDATES


# ============================================================


def build_metric_candidates(


    df: pd.DataFrame,


    column_roles: dict[str, dict[str, Any]],


) -> list[dict[str, Any]]:


    metrics: list[dict[str, Any]] = []


    for column_name, info in column_roles.items():


        if info["role"] != "numeric":


            continue


        _, series, _ = _try_numeric(df[column_name])


        valid = series.dropna()


        if valid.empty:


            continue


        tags = set(info.get("semantic_tags", []))


        if "rate" in tags or "rating" in tags:


            metric_type = "average"


            recommended = [


                "average",


                "median",


                "minimum",


                "maximum",


            ]


        elif "quantity" in tags:


            metric_type = "sum"


            recommended = [


                "sum",


                "average",


                "median",


                "minimum",


                "maximum",


            ]


        else:


            metric_type = "summary"


            recommended = [


                "sum",


                "average",


                "median",


                "minimum",


                "maximum",


            ]


        metrics.append(


            {


                "column": column_name,


                "label": column_name.replace("_", " ").title(),


                "metric_type": metric_type,


                "recommended_aggregations": recommended,


                "sample_value": _json_safe(valid.iloc[0]),


                "sum": _json_safe(valid.sum()),


                "average": _json_safe(valid.mean()),


                "median": _json_safe(valid.median()),


                "minimum": _json_safe(valid.min()),


                "maximum": _json_safe(valid.max()),


            }


        )


    return metrics


# ============================================================


# ANALYSIS OPPORTUNITIES


# ============================================================


def build_analysis_opportunities(


    column_roles: dict[str, dict[str, Any]],


) -> list[dict[str, Any]]:


    numeric = [


        column for column, info in column_roles.items()


        if info["role"] == "numeric"


    ]


    categorical = [


        column for column, info in column_roles.items()


        if info["role"] == "categorical"


    ]


    dates = [


        column for column, info in column_roles.items()


        if info["role"] == "datetime"


    ]


    opportunities: list[dict[str, Any]] = []


    if numeric:


        opportunities.append({


            "type": "numeric_summary",


            "description": "Summarize numeric measures using totals, averages, medians, minimums and maximums.",


            "columns": numeric,


        })


    if numeric and categorical:


        opportunities.append({


            "type": "dimension_breakdown",


            "description": "Compare numeric measures across categorical dimensions.",


            "measure_columns": numeric,


            "dimension_columns": categorical,


        })


    if dates and numeric:


        opportunities.append({


            "type": "time_trend",


            "description": "Analyze numeric measures over time.",


            "date_columns": dates,


            "measure_columns": numeric,


        })


    if len(numeric) >= 2:


        opportunities.append({


            "type": "numeric_relationships",


            "description": "Explore relationships and correlations between numeric measures.",


            "columns": numeric,


        })


    if categorical:


        opportunities.append({


            "type": "category_distribution",


            "description": "Analyze category frequency, uniqueness and distribution.",


            "columns": categorical,


        })


    if not opportunities:


        opportunities.append({


            "type": "data_overview",


            "description": "Provide a structural overview of the dataset and its available fields.",


            "columns": list(column_roles.keys()),


        })


    return opportunities


# ============================================================


# MAIN UNIVERSAL INTELLIGENCE FUNCTION


# ============================================================


def analyze_dataset(df: pd.DataFrame) -> dict[str, Any]:


    """


    Analyze any pandas DataFrame.


    This function never requires a specific business domain.


    Unknown datasets are valid and receive general_analytics.


    """


    if df is None:


        raise ValueError("Dataset cannot be None.")


    if not isinstance(df, pd.DataFrame):


        raise TypeError("Dataset must be a pandas DataFrame.")


    if df.empty:


        raise ValueError("Dataset is empty.")


    column_roles = {


        str(column): infer_column_role(df, column)


        for column in df.columns


    }


    domain = infer_dataset_domain(df, column_roles)


    role_counts: dict[str, int] = {}


    for info in column_roles.values():


        role = info["role"]


        role_counts[role] = role_counts.get(role, 0) + 1


    metrics = build_metric_candidates(df, column_roles)


    opportunities = build_analysis_opportunities(column_roles)


    numeric_columns = [


        column


        for column, info in column_roles.items()


        if info["role"] == "numeric"


    ]


    categorical_columns = [


        column


        for column, info in column_roles.items()


        if info["role"] == "categorical"


    ]


    date_columns = [


        column


        for column, info in column_roles.items()


        if info["role"] == "datetime"


    ]


    identifier_columns = [


        column


        for column, info in column_roles.items()


        if info["role"] == "identifier"


    ]


    return {


        "success": True,


        "dataset": {


            "row_count": int(len(df)),


            "column_count": int(len(df.columns)),


            "columns": [str(column) for column in df.columns],


        },


        "domain": domain,


        "role_counts": role_counts,


        "columns": column_roles,


        "column_groups": {


            "numeric": numeric_columns,


            "categorical": categorical_columns,


            "datetime": date_columns,


            "identifiers": identifier_columns,


            "boolean": [


                column


                for column, info in column_roles.items()


                if info["role"] == "boolean"


            ],


            "text": [


                column


                for column, info in column_roles.items()


                if info["role"] == "text"


            ],


            "empty": [


                column


                for column, info in column_roles.items()


                if info["role"] == "empty"


            ],


        },


        "metric_candidates": metrics,


        "analysis_opportunities": opportunities,


    }


# ============================================================


# BACKWARD-FRIENDLY ALIAS


# ============================================================


def profile_dataset_intelligence(df: pd.DataFrame) -> dict[str, Any]:


    """Alias for callers that prefer a profile-style function name."""


    return analyze_dataset(df)
