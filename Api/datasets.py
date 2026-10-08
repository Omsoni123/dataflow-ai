from fastapi import (







    APIRouter,







    UploadFile,







    File,







    HTTPException,







    Depends,







    Form,







)
from fastapi.responses import StreamingResponse








from pydantic import BaseModel

from sqlalchemy import text

from SRC.database import get_connection













import json
import io







import os







import tempfile
import re

import pandas as pd
from dateutil import parser as date_parser















from SRC.data_cleaning import process_data, load_data







from SRC.data_profiler import profile_data







from SRC.cleaning_decisions import CleaningDecision







from SRC.data_cleaning_engine import apply_cleaning_decisions







from SRC.dataset_intelligence import analyze_dataset







from SRC.dynamic_kpi import generate_dynamic_kpis















from SRC.database import (







    store_dataset,







    get_latest_dataset_for_user,







)















from SRC.analysis import calculate_kpis







from SRC.groq_service import ask_dataset







from Api.auth import get_current_user























router = APIRouter(







    prefix="/datasets",







    tags=["Datasets"],







)























class AskRequest(BaseModel):







    question: str























# ============================================================







# HELPERS







# ============================================================















def parse_cleaning_decisions(decisions: str) -> CleaningDecision:







    """







    Parse cleaning decisions sent from the frontend as JSON.







    """















    try:







        decision_data = json.loads(decisions)







    except json.JSONDecodeError as error:







        raise HTTPException(







            status_code=400,







            detail=f"Invalid cleaning decisions JSON: {str(error)}",







        )















    try:







        return CleaningDecision(**decision_data)







    except Exception as error:







        raise HTTPException(







            status_code=400,







            detail=f"Invalid cleaning decisions: {str(error)}",







        )























async def save_upload_to_temp(file: UploadFile) -> str:







    """







    Save an uploaded CSV to a temporary file and return its path.







    """















    if not file.filename:







        raise HTTPException(







            status_code=400,







            detail="No file provided.",







        )















    if not file.filename.lower().endswith(".csv"):







        raise HTTPException(







            status_code=400,







            detail="Only CSV files are supported.",







        )















    contents = await file.read()















    if not contents:







        raise HTTPException(







            status_code=400,







            detail="The uploaded file is empty.",







        )















    temp_dir = tempfile.gettempdir()















    temp_path = os.path.join(







        temp_dir,







        file.filename,







    )















    with open(temp_path, "wb") as output_file:







        output_file.write(contents)















    return temp_path























def cleanup_temp_file(temp_path: str | None) -> None:







    """







    Safely remove a temporary file.







    """















    if temp_path and os.path.exists(temp_path):







        try:







            os.remove(temp_path)







        except Exception:







            pass























# ============================================================








# ============================================================
# UNIVERSAL CLEANED-DATA NORMALIZATION
# ============================================================

_MISSING_TEXT_TOKENS = {
    "", " ", "na", "n/a", "nan", "null", "none", "nil", "?", "-"
}

_DATE_NAME_HINTS = (
    "date", "datetime", "timestamp", "time", "dob", "birth",
    "joining", "joined", "created", "updated", "modified",
    "registered", "transaction"
)

_NUMERIC_NAME_HINTS = (
    "quantity", "qty", "unit_price", "price", "amount", "revenue",
    "sales", "cost", "discount", "profit", "income", "expense",
    "spend", "units", "count", "score", "rating", "tax", "margin",
    "rate", "total"
)

_IDENTIFIER_NAME_HINTS = (
    "id", "code", "sku", "zip", "postal", "pincode", "pin_code",
    "phone", "mobile", "account"
)


def _is_missing_text(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip().lower() in _MISSING_TEXT_TOKENS


def _parse_universal_date(value):
    if _is_missing_text(value):
        return pd.NaT

    value_text = re.sub(
        r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+",
        "",
        str(value).strip(),
        flags=re.IGNORECASE,
    )

    if not value_text:
        return pd.NaT

    try:
        return date_parser.parse(value_text, dayfirst=True, fuzzy=False)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def _looks_like_date_column(series: pd.Series, column_name: str) -> bool:
    name = column_name.lower().strip()

    if any(hint in name for hint in _DATE_NAME_HINTS):
        return True

    sample = series.dropna().astype(str).str.strip().head(300)
    if sample.empty:
        return False

    signal = sample.str.contains(
        r"(?:\d{1,4}[./-]\d{1,4}[./-]\d{1,4})|"
        r"(?:\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b)",
        case=False,
        regex=True,
    ).mean()

    if signal < 0.60:
        return False

    return sample.map(_parse_universal_date).notna().mean() >= 0.75


def _clean_numeric_series(series: pd.Series) -> pd.Series:
    def parse_number(value):
        if _is_missing_text(value):
            return pd.NA

        s = str(value).strip()
        negative = s.startswith("(") and s.endswith(")")
        s = s.strip("()")
        s = (
            s.replace(",", "")
            .replace("₹", "")
            .replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .replace("%", "")
        )
        s = re.sub(r"(?i)\b(?:usd|inr|eur|gbp)\b", "", s).strip()

        if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", s):
            return pd.NA

        try:
            number = float(s)
            return -number if negative else number
        except ValueError:
            return pd.NA

    return series.map(parse_number)


def _looks_like_numeric_column(series: pd.Series, column_name: str) -> bool:
    name = column_name.lower().strip()

    if any(hint in name for hint in _IDENTIFIER_NAME_HINTS):
        return False

    if any(hint in name for hint in _NUMERIC_NAME_HINTS):
        return True

    sample = series.dropna().astype(str).str.strip().head(300)
    if sample.empty:
        return False

    return _clean_numeric_series(sample).notna().mean() >= 0.90


def normalize_cleaned_dataset(data: pd.DataFrame) -> pd.DataFrame:
    """
    Universal normalization used before and after cleaning.

    This does not decide which rows to remove or which values to fill.
    Those decisions remain controlled by CleaningDecision/apply_cleaning_decisions.
    """
    cleaned = data.copy()

    # Normalize whitespace and common missing placeholders.
    for column in cleaned.columns:
        if (
            pd.api.types.is_object_dtype(cleaned[column])
            or pd.api.types.is_string_dtype(cleaned[column])
        ):
            cleaned[column] = cleaned[column].map(
                lambda value: pd.NA
                if _is_missing_text(value)
                else str(value).strip()
            )

    # Mixed-format date normalization.
    for column in cleaned.columns:
        if _looks_like_date_column(cleaned[column], str(column)):
            parsed = cleaned[column].map(_parse_universal_date)
            valid_ratio = parsed.notna().mean() if len(parsed) else 0.0

            if valid_ratio >= 0.70 or any(
                hint in str(column).lower() for hint in _DATE_NAME_HINTS
            ):
                cleaned[column] = parsed.map(
                    lambda value: value.strftime("%Y-%m-%d")
                    if pd.notna(value)
                    else pd.NA
                )

    # Numeric/currency normalization.
    for column in cleaned.columns:
        if _looks_like_numeric_column(cleaned[column], str(column)):
            parsed = _clean_numeric_series(cleaned[column])
            non_missing = cleaned[column].notna().sum()
            valid = parsed.notna().sum()

            if non_missing == 0 or valid / max(non_missing, 1) >= 0.70:
                cleaned[column] = pd.to_numeric(parsed, errors="coerce")

    return cleaned


def refresh_cleaning_summary(summary: dict, cleaned_data: pd.DataFrame) -> dict:
    if not isinstance(summary, dict):
        return summary

    after = summary.setdefault("after", {})
    after["row_count"] = int(len(cleaned_data))
    after["column_count"] = int(len(cleaned_data.columns))
    after["missing_value_count"] = int(cleaned_data.isna().sum().sum())
    after["duplicate_row_count"] = int(cleaned_data.duplicated().sum())
    return summary


# DATASET INSPECTION







# ============================================================















@router.post("/inspect")







async def inspect_dataset(







    file: UploadFile = File(...),







    current_user: dict = Depends(get_current_user),







):







    """







    Inspect an uploaded CSV before cleaning or storing it.















    This endpoint does NOT modify or store the dataset.







    """















    temp_path = None















    try:







        temp_path = await save_upload_to_temp(file)















        data = load_data(temp_path)
        data = normalize_cleaned_dataset(data)















        if data is None or data.empty:







            raise HTTPException(







                status_code=400,







                detail="The uploaded CSV contains no usable data.",







            )















        profile = profile_data(data)















        return {







            "success": True,







            "message": "Dataset inspected successfully.",







            "file_name": file.filename,







            "profile": profile,







        }















    except HTTPException:







        raise















    except Exception as error:







        raise HTTPException(







            status_code=400,







            detail=f"Dataset inspection failed: {str(error)}",







        )















    finally:







        cleanup_temp_file(temp_path)















# ============================================================







# UNIVERSAL DATASET INTELLIGENCE







# ============================================================















@router.post("/intelligence")







async def dataset_intelligence(







    file: UploadFile = File(...),







    current_user: dict = Depends(get_current_user),







):







    """







    Analyze an uploaded CSV using the universal dataset intelligence engine.















    This endpoint:







    - Does NOT store the dataset







    - Does NOT modify the dataset







    - Detects column roles







    - Detects optional dataset domain







    - Finds metric candidates







    - Finds analysis opportunities















    It is designed to work with any structured CSV dataset.







    """















    temp_path = None















    try:







        temp_path = await save_upload_to_temp(file)















        data = load_data(temp_path)
        data = normalize_cleaned_dataset(data)















        if data is None or data.empty:







            raise HTTPException(







                status_code=400,







                detail="The uploaded CSV contains no usable data.",







            )















        intelligence = analyze_dataset(data)















        return {







            "success": True,







            "message": "Dataset intelligence generated successfully.",







            "file_name": file.filename,







            "intelligence": intelligence,







        }















    except HTTPException:







        raise















    except Exception as error:







        raise HTTPException(







            status_code=400,







            detail=f"Dataset intelligence analysis failed: {str(error)}",







        )















    finally:







        cleanup_temp_file(temp_path)















@router.post("/dynamic-kpis")







async def dynamic_kpis(







    file: UploadFile = File(...),







    current_user: dict = Depends(get_current_user),







):







    temp_path = None















    try:







        temp_path = await save_upload_to_temp(file)















        data = load_data(temp_path)
        data = normalize_cleaned_dataset(data)















        if data is None or data.empty:







            raise HTTPException(







                status_code=400,







                detail="The uploaded CSV contains no usable data.",







            )















        # Generate dataset intelligence first so the KPI engine







        # can use semantic information when available.







        intelligence = analyze_dataset(data)















        # Generate universal dynamic KPIs.







        kpi_result = generate_dynamic_kpis(







            df=data,







            intelligence=intelligence,







        )















        return {







            "success": True,







            "message": "Dynamic KPIs generated successfully.",







            "file_name": file.filename,







            "kpis": kpi_result.get("kpis", []),







            "summary": kpi_result.get("summary", {}),







        }















    except HTTPException:







        raise















    except Exception as error:







        raise HTTPException(







            status_code=400,







            detail=f"Dynamic KPI generation failed: {str(error)}",







        )















    finally:







        cleanup_temp_file(temp_path)















# ============================================================







# CLEANING PREVIEW







# ============================================================















@router.post("/clean")







async def clean_dataset_preview(







    file: UploadFile = File(...),







    decisions: str = Form(...),







    current_user: dict = Depends(get_current_user),







):







    """







    Apply the user's cleaning decisions in memory and return







    a preview.















    IMPORTANT:







    This endpoint does NOT store the cleaned dataset.







    """















    temp_path = None















    try:







        decision = parse_cleaning_decisions(decisions)















        temp_path = await save_upload_to_temp(file)















        data = load_data(temp_path)
        data = normalize_cleaned_dataset(data)















        if data is None or data.empty:







            raise HTTPException(







                status_code=400,







                detail="The uploaded CSV contains no usable data.",







            )















        cleaned_data, cleaning_summary = apply_cleaning_decisions(







            data,







            decision,







        )

        cleaned_data = normalize_cleaned_dataset(cleaned_data)
        cleaning_summary = refresh_cleaning_summary(cleaning_summary, cleaned_data)















        cleaned_profile = profile_data(cleaned_data)















        return {







            "success": True,







            "message": "Dataset cleaned successfully.",







            "file_name": file.filename,







            "cleaning_summary": cleaning_summary,







            "cleaned_profile": cleaned_profile,







        }















    except HTTPException:







        raise















    except Exception as error:







        raise HTTPException(







            status_code=400,







            detail=f"Dataset cleaning preview failed: {str(error)}",







        )















    finally:







        cleanup_temp_file(temp_path)























# ============================================================







# APPLY CLEANING AND STORE DATASET







# ============================================================















@router.post("/apply-cleaning")







async def apply_cleaning_and_store(







    file: UploadFile = File(...),







    decisions: str = Form(...),







    current_user: dict = Depends(get_current_user),







):







    """







    Apply the user's confirmed cleaning decisions and store







    the cleaned dataset for the authenticated user.







    """















    temp_path = None















    try:







        decision = parse_cleaning_decisions(decisions)















        temp_path = await save_upload_to_temp(file)















        data = load_data(temp_path)
        data = normalize_cleaned_dataset(data)















        if data is None or data.empty:







            raise HTTPException(







                status_code=400,







                detail="The uploaded CSV contains no usable data.",







            )















        cleaned_data, cleaning_summary = apply_cleaning_decisions(







            data,







            decision,







        )















        dataset_info = store_dataset(







            cleaned_data,







            file.filename,







            current_user["user_id"],







        )















        cleaned_profile = profile_data(cleaned_data)















        intelligence = analyze_dataset(cleaned_data)















        dynamic_kpis = generate_dynamic_kpis(







            cleaned_data,







            intelligence=intelligence,







        )















        return {







            "success": True,







            "message": "Cleaned dataset applied and stored successfully.",







            "file_name": file.filename,







            "dataset": dataset_info,







            "cleaning_summary": cleaning_summary,







            "cleaned_profile": cleaned_profile,







            "intelligence": intelligence,







            "dynamic_kpis": dynamic_kpis.get("kpis", []),







            "kpi_summary": dynamic_kpis.get("summary", {}),







        }















    except HTTPException:







        raise















    except Exception as error:







        raise HTTPException(







            status_code=400,







            detail=f"Failed to apply cleaning: {str(error)}",







        )















    finally:







        cleanup_temp_file(temp_path)























# ============================================================







# CLEANING DECISION VALIDATION







# ============================================================















@router.post("/cleaning-preview")







async def cleaning_preview(







    decision: CleaningDecision,







    current_user: dict = Depends(get_current_user),







):







    """







    Validate the user's cleaning decisions.















    This endpoint does not modify or store a dataset.







    """















    return {







        "success": True,







        "message": "Cleaning decisions received successfully.",







        "decisions": (







            decision.model_dump()







            if hasattr(decision, "model_dump")







            else decision.dict()







        ),







    }























# ============================================================







# EXISTING PRODUCTION DATASET UPLOAD







# ============================================================















@router.post("/upload")







async def upload_dataset(







    file: UploadFile = File(...),







    current_user: dict = Depends(get_current_user),







):







    """







    Existing production upload flow.















    Kept unchanged so the new V2 cleaning flow can be tested







    safely before replacing the old upload behavior.







    """















    temp_path = None















    try:







        temp_path = await save_upload_to_temp(file)















        data = process_data(temp_path)















        if data is None or data.empty:







            raise HTTPException(







                status_code=400,







                detail="The uploaded CSV contains no usable data.",







            )















        dataset_info = store_dataset(







            data,







            file.filename,







            current_user["user_id"],







        )















        kpis = calculate_kpis(data)















        kpis = {







            key: value.item() if hasattr(value, "item") else value







            for key, value in kpis.items()







        }















        return {







            "success": True,







            "message": "Dataset uploaded successfully.",







            "dataset": dataset_info,







            "kpis": kpis,







        }















    except HTTPException:







        raise















    except Exception as error:







        raise HTTPException(







            status_code=400,







            detail=str(error),







        )















    finally:







        cleanup_temp_file(temp_path)























# ============================================================

# AI ANALYST

# ============================================================






# ============================================================
# DOWNLOAD CLEANED DATASET
# ============================================================

@router.post("/download-cleaned")
async def download_cleaned_dataset(
    file: UploadFile = File(...),
    decisions: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """Re-apply confirmed cleaning decisions and return the cleaned CSV."""
    temp_path = None

    try:
        # Keep this endpoint user-authenticated, even though the dataset is
        # processed from the file supplied in this request.
        _ = current_user["user_id"]

        decision = parse_cleaning_decisions(decisions)
        temp_path = await save_upload_to_temp(file)
        data = load_data(temp_path)
        data = normalize_cleaned_dataset(data)

        if data is None or data.empty:
            raise HTTPException(
                status_code=400,
                detail="The uploaded CSV contains no usable data.",
            )

        cleaned_data, _ = apply_cleaning_decisions(data, decision)
        cleaned_data = normalize_cleaned_dataset(cleaned_data)

        csv_buffer = io.StringIO()
        cleaned_data.to_csv(csv_buffer, index=False)

        original_name = os.path.basename(file.filename or "dataset.csv")
        safe_name = original_name.replace('"', "").replace("\\", "")
        if not safe_name.lower().endswith(".csv"):
            safe_name = f"{safe_name}.csv"

        return StreamingResponse(
            iter([csv_buffer.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="cleaned_{safe_name}"',
            },
        )

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to generate cleaned dataset: {str(error)}",
        )
    finally:
        cleanup_temp_file(temp_path)

@router.post("/ask")

async def ask_ai(

    request: AskRequest,

    current_user: dict = Depends(get_current_user),

):

    """

    Ask the AI Analyst a question about the user's

    latest uploaded dataset.



    FREE users receive exactly one successful AI question.

    PRO users have unlimited AI Analyst access.



    The quota is enforced server-side so it cannot be

    bypassed by calling the API directly.

    """



    question = request.question.strip()



    if not question:

        raise HTTPException(

            status_code=400,

            detail="Question cannot be empty.",

        )



    user_id = current_user["user_id"]

    is_pro = current_user.get("plan") == "pro"



    # --------------------------------------------------------

    # FREE PLAN QUOTA

    # --------------------------------------------------------

    # Claim the single free AI question atomically BEFORE

    # calling Groq. If the AI request fails, the question

    # is released again.

    # --------------------------------------------------------



    quota_claimed = False



    if not is_pro:

        with get_connection() as connection:

            quota_result = connection.execute(

                text("""

                    UPDATE users

                    SET ai_questions_used = ai_questions_used + 1

                    WHERE user_id = :user_id

                      AND plan = 'free'

                      AND ai_questions_used < 1

                """),

                {

                    "user_id": user_id,

                },

            )



            connection.commit()



            if quota_result.rowcount != 1:

                raise HTTPException(

                    status_code=402,

                    detail=(

                        "Your free AI Analyst question has been used. "

                        "Upgrade to DataFlow AI Pro for unlimited AI access."

                    ),

                )



        quota_claimed = True



    # --------------------------------------------------------

    # Get the authenticated user's latest dataset

    # --------------------------------------------------------



    dataset = get_latest_dataset_for_user(user_id)



    if dataset is None:

        # Release the claimed free question because no AI

        # analysis could actually be performed.

        if quota_claimed:

            with get_connection() as connection:

                connection.execute(

                    text("""

                        UPDATE users

                        SET ai_questions_used = 0

                        WHERE user_id = :user_id

                          AND plan = 'free'

                          AND ai_questions_used = 1

                    """),

                    {

                        "user_id": user_id,

                    },

                )

                connection.commit()



        raise HTTPException(

            status_code=404,

            detail="No dataset found. Please upload a CSV first.",

        )



    try:

        # ----------------------------------------------------

        # Existing AI Analyst flow

        # ----------------------------------------------------



        result = ask_dataset(

            dataset_id=dataset["dataset_id"],

            question=question,

        )



        database_result = result.get("result")



        if database_result is not None:

            database_result = database_result.to_dict(

                orient="records"

            )



        return {

            "success": True,

            "question": question,

            "answer": result["answer"],

            "data": database_result,

            "plan": "pro" if is_pro else "free",

            "ai_questions_used": 1 if not is_pro else current_user.get(

                "ai_questions_used", 0

            ),

            "ai_questions_remaining": 0 if not is_pro else None,

        }



    except ValueError as error:

        # AI failed, so restore the FREE user's question.

        if quota_claimed:

            with get_connection() as connection:

                connection.execute(

                    text("""

                        UPDATE users

                        SET ai_questions_used = 0

                        WHERE user_id = :user_id

                          AND plan = 'free'

                          AND ai_questions_used = 1

                    """),

                    {

                        "user_id": user_id,

                    },

                )

                connection.commit()



        raise HTTPException(

            status_code=400,

            detail=str(error),

        )



    except Exception as error:

        # AI failed, so restore the FREE user's question.

        if quota_claimed:

            with get_connection() as connection:

                connection.execute(

                    text("""

                        UPDATE users

                        SET ai_questions_used = 0

                        WHERE user_id = :user_id

                          AND plan = 'free'

                          AND ai_questions_used = 1

                    """),

                    {

                        "user_id": user_id,

                    },

                )

                connection.commit()



        raise HTTPException(

            status_code=500,

            detail=f"AI analysis failed: {str(error)}",

        )
