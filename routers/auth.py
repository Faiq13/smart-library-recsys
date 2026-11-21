"""Auth module placeholder owned by Anggota 4, Rifa."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/status")
def auth_status():
    return {"module": "auth", "status": "placeholder", "owner": "Rifa"}
