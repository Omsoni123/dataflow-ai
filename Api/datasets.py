from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
import os
import tempfile

from SRC.data_cleaning import process_data
from SRC.database import (
    store_dataset,
    get_latest_dataset_for_user
)
from SRC.analysis import calculate_kpis
from SRC.groq_service import ask_dataset
from Api.auth import get_current_user


router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AskRequest(BaseModel):
    question: str


# ============================================================
# UPLOAD DATASET
# ============================================================

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a CSV dataset and associate it with
    the currently authenticated user.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file provided."
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported."
        )

    temp_path = None

    try:
        # ----------------------------------------------------
        # SAVE FILE TEMPORARILY
        # ----------------------------------------------------

        temp_dir = tempfile.gettempdir()

        temp_path = os.path.join(
            temp_dir,
            file.filename
        )

        contents = await file.read()

        with open(temp_path, "wb") as output_file:
            output_file.write(contents)

        # ----------------------------------------------------
        # PROCESS DATASET
        # ----------------------------------------------------

        data = process_data(temp_path)

        if data is None or data.empty:
            raise HTTPException(
                status_code=400,
                detail="The uploaded CSV contains no usable data."
            )

        # ----------------------------------------------------
        # STORE DATASET
        # ----------------------------------------------------

        dataset_info = store_dataset(
            data,
            file.filename,
            current_user["user_id"]
        )

        # ----------------------------------------------------
        # CALCULATE KPIs
        # ----------------------------------------------------

        kpis = calculate_kpis(data)

        kpis = {
            key: value.item()
            if hasattr(value, "item")
            else value
            for key, value in kpis.items()
        }

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return {
            "success": True,
            "message": "Dataset uploaded successfully.",
            "dataset": dataset_info,
            "kpis": kpis
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    finally:

        # ----------------------------------------------------
        # REMOVE TEMPORARY FILE
        # ----------------------------------------------------

        if temp_path and os.path.exists(temp_path):

            try:
                os.remove(temp_path)

            except Exception:
                pass


# ============================================================
# ASK AI ANALYST
# ============================================================

@router.post("/ask")
async def ask_ai(
    request: AskRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Ask a natural-language question about the
    authenticated user's latest uploaded dataset.

    IMPORTANT:

    The frontend sends ONLY the question.

    The user does NOT provide dataset_id.

    Groq does NOT choose dataset_id.

    The backend automatically finds the dataset
    belonging to the authenticated user.
    """

    # --------------------------------------------------------
    # VALIDATE QUESTION
    # --------------------------------------------------------

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    # --------------------------------------------------------
    # FIND USER'S DATASET
    # --------------------------------------------------------

    dataset = get_latest_dataset_for_user(
        current_user["user_id"]
    )

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="No dataset found. Please upload a CSV first."
        )

    # --------------------------------------------------------
    # SEND QUESTION TO GROQ
    # --------------------------------------------------------

    try:

        result = ask_dataset(
            dataset_id=dataset["dataset_id"],
            question=question
        )

        # ----------------------------------------------------
        # CONVERT DATABASE RESULT TO JSON-SAFE FORMAT
        # ----------------------------------------------------

        database_result = result.get("result")

        if database_result is not None:

            database_result = database_result.to_dict(
                orient="records"
            )

        # ----------------------------------------------------
        # RETURN AI RESPONSE
        # ----------------------------------------------------

        return {
            "success": True,
            "question": question,
            "answer": result["answer"],
            "data": database_result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {str(error)}"
        )