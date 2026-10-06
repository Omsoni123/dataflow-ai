import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("❌ DATABASE_URL not found in .env")
    raise SystemExit

# Render may provide postgres://
# SQLAlchemy expects postgresql://
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg2://",
        1
    )

engine = create_engine(database_url)

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        version = result.fetchone()[0]

        print("✅ PostgreSQL connection successful!")
        print("Database:", version)

except Exception as e:
    print("❌ PostgreSQL connection failed")
    print("Error:", e)