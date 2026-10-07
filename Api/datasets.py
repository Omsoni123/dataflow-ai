from fastapi import (

    APIRouter,

    UploadFile,

    File,

    HTTPException,

    Depends,

    Form,

)

from pydantic import BaseModel



import json

import os

import tempfile



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



        if data is None or data.empty:

            raise HTTPException(

                status_code=400,

                detail="The uploaded CSV contains no usable data.",

            )



        cleaned_data, cleaning_summary = apply_cleaning_decisions(

            data,

            decision,

        )



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



@router.post("/ask")

async def ask_ai(

    request: AskRequest,

    current_user: dict = Depends(get_current_user),

):

    """

    Ask the AI Analyst a question about the user's

    latest uploaded dataset.

    """



    question = request.question.strip()



    if not question:

        raise HTTPException(

            status_code=400,

            detail="Question cannot be empty.",

        )



    dataset = get_latest_dataset_for_user(

        current_user["user_id"]

    )



    if dataset is None:

        raise HTTPException(

            status_code=404,

            detail="No dataset found. Please upload a CSV first.",

        )



    try:

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

        }



    except ValueError as error:

        raise HTTPException(

            status_code=400,

            detail=str(error),

        )



    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail=f"AI analysis failed: {str(error)}",

        )
