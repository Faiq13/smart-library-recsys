"""FastAPI entry point for Smart Library RecSys."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from database import init_db
from routers import analytics, auth, books, circulation, recommendations

BASE_DIR = Path(__file__).resolve().parent
init_db()
app = FastAPI(title="Smart Library RecSys", version="1.0.0", description="Sistem rekomendasi buku FR-04")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(circulation.router)
app.include_router(recommendations.router)
app.include_router(recommendations.page_router)
app.include_router(analytics.router)


@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={"active_page": "home", "page_title": "Smart Library RecSys", "content_only": False},
    )


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "smart-library-recsys"}
