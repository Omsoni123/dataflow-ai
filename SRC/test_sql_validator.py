from database import validate_sql


dataset_id = "3a5a172b-148f-4d74-a501-d6db14ec6928"

table_name = "dataset_3a5a172b148f"


# --------------------------------
# TEST 1 — VALID SELECT
# --------------------------------

query = f"""
SELECT SUM(sales) AS total_sales
FROM {table_name}
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 1")
print("Valid:", valid)
print("Message:", message)


# --------------------------------
# TEST 2 — DROP
# --------------------------------

query = f"""
DROP TABLE {table_name}
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 2")
print("Valid:", valid)
print("Message:", message)


# --------------------------------
# TEST 3 — DELETE
# --------------------------------

query = f"""
DELETE FROM {table_name}
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 3")
print("Valid:", valid)
print("Message:", message)


# --------------------------------
# TEST 4 — UPDATE
# --------------------------------

query = f"""
UPDATE {table_name}
SET sales = 0
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 4")
print("Valid:", valid)
print("Message:", message)


# --------------------------------
# TEST 5 — MULTIPLE STATEMENTS
# --------------------------------

query = f"""
SELECT * FROM {table_name};
DROP TABLE {table_name};
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 5")
print("Valid:", valid)
print("Message:", message)


# --------------------------------
# TEST 6 — WRONG TABLE
# --------------------------------

query = """
SELECT SUM(sales)
FROM another_dataset
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 6")
print("Valid:", valid)
print("Message:", message)

# --------------------------------
# TEST 7 — VALID COLUMNS
# --------------------------------

query = f"""
SELECT category, SUM(sales) AS total_sales
FROM {table_name}
GROUP BY category
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 7")
print("Valid:", valid)
print("Message:", message)

# --------------------------------
# TEST 8 — INVALID COLUMN
# --------------------------------

query = f"""
SELECT secret_column
FROM {table_name}
"""

valid, message = validate_sql(
    dataset_id,
    query
)

print("\nTEST 8")
print("Valid:", valid)
print("Message:", message)