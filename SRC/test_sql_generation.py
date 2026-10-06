from database import get_dataset_metadata
from groq_service import generate_sql


dataset_id = "3a5a172b-148f-4d74-a501-d6db14ec6928"


# Get dataset information
metadata = get_dataset_metadata(dataset_id)

table_name = metadata["table_name"]
schema = metadata["schema"]


# Natural-language question
question = "What is my total sales?"


# Generate SQL
sql = generate_sql(
    question,
    table_name,
    schema
)


print("\n===== GENERATED SQL =====")
print(sql)