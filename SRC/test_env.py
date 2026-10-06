from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if api_key:
    print("Groq API key loaded successfully!")
else:
    print("Groq API key not found.")