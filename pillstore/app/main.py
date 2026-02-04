import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware

from app.core.init import lifespan
from app.core.logger import LoggingMiddleware

from app.routers import products, orders, auth, profile, admin, errors, scraper
from app.api import api_products

from app.exceptions.handlers import setup_html_error_handlers

tags_metadata = [
    {"name": "Health"},
    {"name": "API v2 Products"},
    {"name": "Products"},
    {"name": "Auth"},
    {"name": "Orders"},
    {"name": "Admin"},
    {"name": "Profile"},
    {"name": "Errors"},
    {"name": "Scraper"},
]

app = FastAPI(
    title="PillStore",
    description="Интернет-магазин продаж БАДов",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

setup_html_error_handlers(app)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"],
)

if os.getenv("ENV") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(LoggingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/products", status_code=302)


app.include_router(scraper.router, tags=["Scraper"])
app.include_router(auth.auth_router, tags=["Auth"])
app.include_router(products.router, tags=["Products"])
app.include_router(orders.router, tags=["Orders"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(errors.router, tags=["Errors"])
app.include_router(api_products.router, prefix="/api/v2", tags=["API v2 Products"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "pillstore": "ready"}
