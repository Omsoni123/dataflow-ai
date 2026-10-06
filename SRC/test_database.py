from data_cleaning import process_data
from database import store_dataset


file_path = "C:/Users/Om Soni/OneDrive/Desktop/Sales_analytical_api/Data/sales.csv"


# Process dataset
data = process_data(file_path)


# Store dataset
result = store_dataset(
    data,
    "sales.csv"
)


print("\n===== DATABASE RESULT =====")

print("Dataset ID:", result["dataset_id"])
print("Table Name:", result["table_name"])
print("Rows:", result["row_count"])
print("Columns:", result["column_count"])