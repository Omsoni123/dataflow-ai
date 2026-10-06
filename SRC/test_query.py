from database import query_dataset


dataset_id = "3a5a172b-148f-4d74-a501-d6db14ec6928"

table_name = "dataset_3a5a172b148f"


# --------------------------------
# TEST 1: TOTAL SALES
# --------------------------------

query = f"""
SELECT SUM(sales) AS total_sales
FROM {table_name}
"""

result = query_dataset(
    dataset_id,
    query
)

print("\n===== TOTAL SALES =====")
print(result)


# --------------------------------
# TEST 2: CATEGORY SALES
# --------------------------------

query = f"""
SELECT
    category,
    SUM(sales) AS total_sales
FROM {table_name}
GROUP BY category
ORDER BY total_sales DESC
"""

result = query_dataset(
    dataset_id,
    query
)

print("\n===== CATEGORY SALES =====")
print(result)

