from database import get_dataset_metadata
from database import load_dataset
from database import get_dataset_schema


dataset_id = "3a5a172b-148f-4d74-a501-d6db14ec6928"


# --------------------------------
# TEST METADATA
# --------------------------------

print("\n===== DATASET METADATA =====")

metadata = get_dataset_metadata(dataset_id)

print(metadata)


# --------------------------------
# TEST SCHEMA
# --------------------------------

print("\n===== DATASET SCHEMA =====")

schema = get_dataset_schema(dataset_id)

print(schema)


# --------------------------------
# TEST DATA LOADING
# --------------------------------

print("\n===== LOADED DATA =====")

data = load_dataset(dataset_id)

print(data.head())

print("\nRows:", len(data))
print("Columns:", len(data.columns))


# for testing the dataset to have and identify unique id for groq id to identify 