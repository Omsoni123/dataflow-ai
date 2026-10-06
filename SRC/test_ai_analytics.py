from groq_service import ask_dataset


dataset_id = "3a5a172b-148f-4d74-a501-d6db14ec6928"

question = "What is my total sales?"

response = ask_dataset(
    dataset_id,
    question
)


print("\n===== USER QUESTION =====")
print(response["question"])


print("\n===== GENERATED SQL =====")
print(response["sql"])


print("\n===== FINAL RESULT =====")
print(response["result"])


print("\n===== AI ANSWER =====")
print(response["answer"])