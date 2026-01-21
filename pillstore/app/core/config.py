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

# CATEGORIES = {
#     1: {"id": 1, "name": "Витамины", "slug": "vitamins", "icon": "fas fa-pills"},
#     2: {"id": 2, "name": "Протеины", "slug": "proteins", "icon": "fas fa-dumbbell"},
# }