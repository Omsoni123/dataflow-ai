import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key.strip())
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_SQL_ATTEMPTS = 2


def _clean_sql_response(content: str) -> str:
    """Extract one SELECT statement from the model response."""
    if not content:
        raise ValueError("Groq returned an empty SQL response.")

    sql = content.strip()
    sql = re.sub(r"^```(?:sql|postgresql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    match = re.search(r"\bSELECT\b", sql, flags=re.IGNORECASE)
    if not match:
        raise ValueError("Groq did not generate a SELECT query.")
    sql = sql[match.start():].strip()

    # A trailing semicolon is fine; multiple statements are not.
    if ";" in sql.rstrip().rstrip(";"):
        raise ValueError("Groq returned multiple SQL statements.")
    return sql.rstrip().rstrip(";").strip()


def generate_sql(question, table_name, schema, previous_sql=None, error_feedback=None):
    """Generate one PostgreSQL SELECT query using only the supplied schema."""
    schema_text = "\n".join(f"- {column} ({data_type})" for column, data_type in schema.items())
    retry_context = ""
    if previous_sql or error_feedback:
        retry_context = f"""
The previous SQL attempt failed.
Previous SQL: {previous_sql or "(not available)"}
Validation/execution feedback: {error_feedback or "(not available)"}
Correct the issue. Do not repeat the same mistake.
"""

    prompt = f"""
You are a careful PostgreSQL analytics assistant. Convert the user's question into exactly one SELECT query.

Dataset table: {table_name}
Available columns:
{schema_text}

User question: {question}
{retry_context}

Rules:
- Use only the one supplied table: {table_name}.
- Use only the listed columns.
- Never use joins, CTEs, subqueries, other tables, or multiple statements.
- Only read data. No INSERT, UPDATE, DELETE, DDL, or database administration.
- Use PostgreSQL syntax.
- Use aggregation/grouping only when appropriate.
- For top/bottom questions, use ORDER BY and a reasonable LIMIT.
- If the question cannot be answered from these columns, still return a safe SELECT that best matches the available data; do not invent columns.
- Return only SQL, without markdown fences or explanations.
SQL:
"""
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return _clean_sql_response(response.choices[0].message.content or "")


def _result_context(result, max_rows=100):
    """Serialize results with explicit truncation metadata for answer generation."""
    if result is None:
        return "No results were returned."
    if result.empty:
        return "No results were returned."
    total_rows = len(result)
    visible = result.head(max_rows)
    context = visible.to_string(index=False)
    if total_rows > max_rows:
        context += f"\n[Showing {max_rows} of {total_rows} rows. Do not claim the displayed rows are the full result.]"
    return context


def generate_answer(question, sql, result):
    """Generate a concise answer grounded in executed query results."""
    result_text = _result_context(result)
    prompt = f"""
You are a professional data analyst. Answer the user's question using only the executed database result below.

Question: {question}
Executed SQL (for context only; do not show it to the user):
{sql}
Database result:
{result_text}

Rules:
- Treat the database result as the only source of facts.
- Do not invent, estimate, or silently alter numbers.
- If no rows were returned, say that no matching results were found.
- If the result is truncated, do not describe the visible rows as the complete dataset.
- Keep the answer concise and useful.
- Format currency as ₹ only when the result/context supports Indian currency; otherwise preserve the source units.
- Use lakh/crore only for clearly Indian financial values.
- Do not expose SQL, table names, or database internals.
- Return only the answer.
"""
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


def ask_dataset(dataset_id, question):
    """
    Run the bounded AI-analytics flow:
    metadata -> SQL generation -> validation -> execution -> grounded answer.
    Keeps the existing return contract expected by Api/datasets.py.
    """
    from SRC.database import get_dataset_metadata, validate_sql, query_dataset

    metadata = get_dataset_metadata(dataset_id)
    if metadata is None:
        raise ValueError("Dataset not found.")

    table_name = metadata["table_name"]
    schema = metadata["schema"]
    last_error = None
    last_sql = None

    for attempt in range(MAX_SQL_ATTEMPTS):
        try:
            sql = generate_sql(
                question=question,
                table_name=table_name,
                schema=schema,
                previous_sql=last_sql if attempt else None,
                error_feedback=last_error if attempt else None,
            )
            last_sql = sql

            is_valid, message = validate_sql(dataset_id, sql)
            if not is_valid:
                raise ValueError(f"SQL validation failed: {message}")

            result = query_dataset(dataset_id, sql)
            answer = generate_answer(question, sql, result)

            return {
                "question": question,
                "sql": sql,
                "result": result,
                "answer": answer,
            }
        except Exception as error:
            last_error = str(error)
            # Only one corrective retry; never loop indefinitely.
            if attempt + 1 >= MAX_SQL_ATTEMPTS:
                raise ValueError(f"AI analysis could not complete after {MAX_SQL_ATTEMPTS} attempts: {last_error}") from error

    raise ValueError("AI analysis could not complete.")
