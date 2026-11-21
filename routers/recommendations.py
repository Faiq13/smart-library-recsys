"""FR-04 recommendation API and interactive demonstration page."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import BASE_DIR, get_connection
from services.recommender_engine import RecommenderEngine

router = APIRouter(prefix="/api/recommendations", tags=["FR-04 Recommendations"])
page_router = APIRouter(tags=["FR-04 Web"])
templates = Jinja2Templates(directory=BASE_DIR / "templates")
engine = RecommenderEngine()


@router.get("/user/{user_id}")
def recommend_for_user(user_id: int, limit: int = 5):
    try:
        return engine.user_recommendations(user_id, limit=max(1, min(limit, 20)))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/similar/{book_id}")
def similar_to_book(book_id: int, limit: int = 5):
    try:
        return engine.similar_books(book_id, limit=max(1, min(limit, 20)))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _options():
    with get_connection() as connection:
        users = connection.execute("SELECT id, name, role FROM users ORDER BY id").fetchall()
        books = connection.execute("SELECT id, title, author FROM books ORDER BY id").fetchall()
    return users, books


@page_router.get("/rekomendasi", response_class=HTMLResponse)
def recommendations_page(request: Request):
    users, books = _options()
    return templates.TemplateResponse(
        request=request,
        name="recommendations.html",
        context={"users": users, "books": books, "active_page": "recommendations"},
    )
