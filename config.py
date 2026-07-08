import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# Model to use via Groq
LLM_MODEL = "llama-3.3-70b-versatile"

# Max number of fix-retry loops before giving up
MAX_FIX_ITERATIONS = 3

# Which linter to use for Python files
PYTHON_LINTER = "pylint"