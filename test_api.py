from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# List all available models
for model in client.models.list():
    print(f"📌 {model.name} - {model.display_name if hasattr(model, 'display_name') else 'N/A'}")
    print(os.getenv("GEMINI_API_KEY"))