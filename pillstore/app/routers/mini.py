from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.config import templates

router = APIRouter(prefix="/mini", tags=["Mini App"])


@router.get("", response_class=HTMLResponse)
async def mini_app(request: Request):
    return templates.TemplateResponse(
        "mini_app.html",
        {"request": request},
    )
