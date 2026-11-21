"""Circulation module placeholder owned by Anggota 2, Wildan."""

from fastapi import APIRouter

router = APIRouter(prefix="/circulation", tags=["Circulation"])


@router.get("/status")
def circulation_status():
    return {"module": "circulation", "status": "placeholder", "owner": "Wildan"}
