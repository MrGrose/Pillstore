import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("PILLSTORE_BOT_TOKEN") or ""
API_BASE_URL = (os.environ.get("PILLSTORE_API_URL") or "http://localhost:8000").rstrip(
    "/"
)
MINI_APP_PUBLIC_URL = (os.environ.get("PILLSTORE_MINI_APP_URL") or "").rstrip(
    "/"
) or API_BASE_URL
SITE_URL = (os.environ.get("PILLSTORE_SITE_URL") or "").rstrip("/") or API_BASE_URL
