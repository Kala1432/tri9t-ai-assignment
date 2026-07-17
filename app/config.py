import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'ct200.db'}")
GENERATION_STORE = Path(os.getenv("GENERATION_STORE", ROOT / "data" / "generations"))
LLM_MODE = os.getenv("LLM_MODE", "mock")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
