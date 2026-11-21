"""Books module placeholder owned by Anggota 3, Dhia."""

from fastapi import APIRouter

router = APIRouter(prefix="/books", tags=["Books"])


@router.get("/status")
def books_status():
    return {"module": "books", "status": "placeholder", "owner": "Dhia"}
