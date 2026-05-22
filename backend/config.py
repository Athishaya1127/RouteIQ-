import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Dynamically resolve .env path
# This handles both root execution and backend folder execution
BASE_DIR = Path(__file__).resolve().parent.parent  # RouteIQ- root
ENV_PATH_BACKEND = BASE_DIR / "backend" / ".env"
ENV_PATH_ROOT = BASE_DIR / ".env"


# Dynamic congestion multiplier based on predicted delay

env_path = None
if ENV_PATH_BACKEND.exists():
    env_path = ENV_PATH_BACKEND
elif ENV_PATH_ROOT.exists():
    env_path = ENV_PATH_ROOT

# 2. Add Diagnostic Debug Mode
print("="*50)
print("[CONFIG DEBUG MODE]")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Resolved .env path: {env_path}")

# 3. Load Environment Variables
if env_path:
    load_dotenv(dotenv_path=env_path)
    print("[CONFIG] .env file located and parsed successfully.")
else:
    print("[CONFIG] WARNING: No .env file found in root or backend folders.")

print("="*50)

# 4. Centralized Configuration
class Settings:
    def __init__(self):
        self.ORS_API_KEY = os.getenv("ORS_API_KEY", "").strip()
        self.AVERAGE_SPEED_KMPH = float(os.getenv("AVERAGE_SPEED_KMPH", 30.0))
        self.DELAY_THRESHOLD_MINS = float(os.getenv("DELAY_THRESHOLD_MINS", 45.0))
        self.DELAY_PENALTY_COST = float(os.getenv("DELAY_PENALTY_COST", 50.0))

settings = Settings()

# 5. Runtime Validation
if not settings.ORS_API_KEY:
    raise RuntimeError(
        "\n\n🚨 CRITICAL STARTUP ERROR: ORS_API_KEY is missing!\n"
        "Failed to load the OpenRouteService API key.\n"
        "Please ensure your .env file exists and contains:\n"
        "ORS_API_KEY=your_key_here\n"
        f"Expected .env location: {ENV_PATH_ROOT} OR {ENV_PATH_BACKEND}\n\n"
    )
else:
    # Print sanitized confirmation
    key_length = len(settings.ORS_API_KEY)
    masked_key = settings.ORS_API_KEY[:4] + "*" * (key_length - 8) + settings.ORS_API_KEY[-4:] if key_length > 8 else "***"
    print(f"[CONFIG] ORS API key loaded successfully (Key: {masked_key})")
