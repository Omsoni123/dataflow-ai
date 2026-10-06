import os

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")


# ============================================================
# GROQ CLIENT
# ============================================================

client = Groq(
    api_key=api_key
)

GROQ_MODEL = "openai/gpt-oss-120b"


# ============================================================
# GENERATE SQL
# ============================================================

def generate_sql(question, table_name, schema):
    """
    Convert a natural-language question into a PostgreSQL
    SELECT query.

    The dataset/table is selected by the backend.
    Groq only generates SQL for the provided table.
    """

    schema_text = "\n".join(
        f"- {column} ({data_type})"
        for column, data_type in schema.items()
    )

    prompt = f"""
You are an SQL analytics assistant.

Your job is to convert the user's natural-language
question into ONE PostgreSQL SELECT query.

DATABASE TABLE:
{table_name}

AVAILABLE COLUMNS:
{schema_text}

USER QUESTION:
{question}

STRICT RULES:

1. Generate ONLY one SELECT statement.
2. Use ONLY the provided table.
3. Use ONLY columns that exist in the provided schema.
4. Never create, modify, update, or delete data.
5. Never use DROP, DELETE, UPDATE, INSERT, ALTER,
   CREATE, TRUNCATE, REPLACE, ATTACH, DETACH, or PRAGMA.
6. Do not reference any other table.
7. Do not invent columns.
8. Do not invent tables.
9. Return ONLY the SQL query.
10. Do not use markdown code fences.
11. Use PostgreSQL-compatible SQL.
12. For aggregations use appropriate functions such as
    SUM, AVG, COUNT, MAX, MIN, GROUP BY and ORDER BY.
13. For "top" results use ORDER BY and LIMIT.
14. For date analysis use the available date column.
15. Never access information outside the provided table.
16. Never attempt to determine or select another dataset.
17. Do not use multiple SQL statements.

SQL:
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    sql = response.choices[0].message.content.strip()

    # --------------------------------------------------------
    # REMOVE MARKDOWN CODE FENCES
    # --------------------------------------------------------

    if sql.startswith("```"):
        sql = (
            sql
            .replace("```sql", "")
            .replace("```postgresql", "")
            .replace("```", "")
            .strip()
        )

    # --------------------------------------------------------
    # REMOVE ACCIDENTAL TEXT BEFORE SELECT
    # --------------------------------------------------------

    select_position = sql.upper().find("SELECT")

    if select_position == -1:
        raise ValueError(
            "Groq did not generate a valid SELECT query."
        )

    sql = sql[select_position:].strip()

    return sql


# ============================================================
# ASK DATASET
# ============================================================

def ask_dataset(dataset_id, question):
    """
    Ask a natural-language question about a stored dataset.

    IMPORTANT:
    dataset_id is supplied by the backend.
    The user and Groq do not select the dataset.

    Flow:

        Authenticated User
              ↓
        Backend selects dataset
              ↓
        Dataset Metadata
              ↓
        Groq generates SQL
              ↓
        SQL validation
              ↓
        PostgreSQL execution
              ↓
        Groq generates answer
    """

    from SRC.database import (
        get_dataset_metadata,
        validate_sql,
        query_dataset
    )

    # --------------------------------------------------------
    # GET DATASET METADATA
    # --------------------------------------------------------

    metadata = get_dataset_metadata(dataset_id)

    if metadata is None:
        raise ValueError(
            "Dataset not found."
        )

    table_name = metadata["table_name"]
    schema = metadata["schema"]

    # --------------------------------------------------------
    # GENERATE SQL
    # --------------------------------------------------------

    sql = generate_sql(
        question=question,
        table_name=table_name,
        schema=schema
    )

    print("\n===== GENERATED SQL =====")
    print(sql)

    # --------------------------------------------------------
    # VALIDATE SQL
    # --------------------------------------------------------

    is_valid, message = validate_sql(
        dataset_id,
        sql
    )

    if not is_valid:
        raise ValueError(
            f"SQL validation failed: {message}"
        )

    print("\n===== SQL VALIDATION =====")
    print(message)

    # --------------------------------------------------------
    # EXECUTE SQL
    # --------------------------------------------------------

    result = query_dataset(
        dataset_id,
        sql
    )

    print("\n===== QUERY RESULT =====")
    print(result)

    # --------------------------------------------------------
    # GENERATE NATURAL LANGUAGE ANSWER
    # --------------------------------------------------------

    answer = generate_answer(
        question,
        sql,
        result
    )

    # --------------------------------------------------------
    # RETURN INTERNAL RESULT
    # --------------------------------------------------------

    return {
        "question": question,
        "sql": sql,
        "result": result,
        "answer": answer
    }


# ============================================================
# GENERATE NATURAL-LANGUAGE ANSWER
# ============================================================

def generate_answer(question, sql, result):
    """
    Convert the database result into a concise
    natural-language answer.
    """

    if result is None or result.empty:
        result_text = "No results were returned."
    else:
        # Limit the amount of database output sent to Groq.
        result_text = result.head(100).to_string(index=False)

    prompt = f"""
You are a professional data analytics assistant.

Answer the user's question using ONLY the database
result provided below.

USER QUESTION:
{question}

DATABASE RESULT:
{result_text}

RULES:

1. Use ONLY facts present in the database result.
2. Do NOT invent information.
3. Do NOT estimate numbers.
4. Do NOT change numbers.
5. Keep the answer concise and professional.
6. Format financial values using ₹.
7. For large Indian financial values, prefer lakh
   or crore when appropriate.
8. Avoid unnecessary decimal places.
9. Format percentages with at most 2 decimal places.
10. Clearly state the main result.
11. Do not mention SQL.
12. Do not mention table names.
13. Do not mention database internals.
14. Return ONLY the final answer.

ANSWER:
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()