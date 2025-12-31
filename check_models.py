from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("--- AVAILABLE MODELS ---")
for m in client.models.list():
    if "flash" in m.name:
        print(f"ID: {m.name} | Display: {m.display_name}")