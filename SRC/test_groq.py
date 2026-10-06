from groq_service import client


response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "user",
            "content": "Say hello in one short sentence."
        }
    ]
)


print(response.choices[0].message.content)