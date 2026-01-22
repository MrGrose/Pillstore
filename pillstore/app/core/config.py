from pathlib import Path
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv


templates_dir = Path(__file__).parent.parent.parent / "templates"
templates = Jinja2Templates(directory=templates_dir)

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
PAGINATION_SIZES = [10, 20, 50, 100]