"""Auth & Member Management module (FR-01) owned by Rifa Gusti Pradipta."""

import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_connection

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(prefix="/auth", tags=["Auth"])

VALID_ROLES = ("anggota", "petugas", "pengelola")
COOKIE_MAX_AGE = 60 * 60 * 8  # 8 jam


def _ensure_password_column(connection: sqlite3.Connection) -> None:
    """Ensure the 'password' column exists in the users table without breaking existing DBs."""
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "password" not in columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN password TEXT NOT NULL DEFAULT ''"
        )


def _hash_password(plain_password: str) -> str:
    """Hash password using salted PBKDF2-HMAC-SHA256 from Python standard library."""
    salt = secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"pbkdf2_sha256${salt}${derived_key}"


def _verify_password(plain_password: str, stored_password: str) -> bool:
    """Verify user password against stored hash (with fallback for seeded accounts)."""
    if not stored_password:
        # Fallback untuk akun bawaan seed_data.py yang belum memiliki password
        return plain_password == "123456"

    if stored_password.startswith("pbkdf2_sha256$"):
        parts = stored_password.split("$", 2)
        if len(parts) != 3:
            return False
        _, salt, expected_hash = parts
        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return hmac.compare_digest(actual_hash, expected_hash)

    return hmac.compare_digest(plain_password, stored_password)


def _get_current_user(request: Request) -> dict[str, str] | None:
    """Extract active user session from cookies."""
    user_id = request.cookies.get("user_id")
    user_nama = request.cookies.get("user_nama")
    user_role = request.cookies.get("user_role")
    if not user_id or not user_role:
        return None
    return {
        "id": user_id,
        "name": user_nama or "Pengguna",
        "role": user_role,
    }


def _safe_cookie_value(value: str) -> str:
    """Ensure cookie string is Latin-1 compatible."""
    return value.encode("latin-1", "ignore").decode("latin-1") or "Pengguna"


@router.get("/status")
def auth_status(request: Request):
    """Health/status endpoint for FR-01 Auth module."""
    current_user = _get_current_user(request)
    return {
        "module": "auth",
        "feature": "FR-01 Autentikasi & Manajemen Anggota",
        "status": "active",
        "owner": "Rifa Gusti Pradipta",
        "authenticated": current_user is not None,
        "user": current_user,
    }


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(
    request: Request,
    error: str | None = None,
    success: str | None = None,
):
    """Render login page."""
    current_user = _get_current_user(request)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "active_page": "auth",
            "page_title": "Login Pengguna — Smart Library RecSys",
            "content_only": True,
            "current_user": current_user,
            "error": error,
            "success": success,
        },
    )


@router.post("/login", include_in_schema=False)
def login_process(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Authenticate email & password against users table and set session cookies."""
    clean_email = email.strip().lower()
    if not clean_email or not password:
        msg = quote_plus("Email dan password wajib diisi.")
        return RedirectResponse(url=f"/auth/login?error={msg}", status_code=303)

    with get_connection() as connection:
        _ensure_password_column(connection)
        user = connection.execute(
            "SELECT id, name, email, role, password FROM users WHERE LOWER(email) = ?",
            (clean_email,),
        ).fetchone()

    if user is None or not _verify_password(password, user["password"]):
        msg = quote_plus("Email atau password tidak sesuai.")
        return RedirectResponse(url=f"/auth/login?error={msg}", status_code=303)

    target_url = (
        "/auth/anggota"
        if user["role"] in ("petugas", "pengelola")
        else "/rekomendasi"
    )
    response = RedirectResponse(url=target_url, status_code=303)
    response.set_cookie(
        key="user_id",
        value=str(user["id"]),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="user_nama",
        value=_safe_cookie_value(user["name"]),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="user_role",
        value=user["role"],
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/logout", include_in_schema=False)
def logout():
    """Clear session cookies and redirect to login page."""
    msg = quote_plus("Anda telah berhasil keluar dari sesi.")
    response = RedirectResponse(url=f"/auth/login?success={msg}", status_code=303)
    response.delete_cookie(key="user_id", path="/")
    response.delete_cookie(key="user_nama", path="/")
    response.delete_cookie(key="user_role", path="/")
    return response


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
def register_page(
    request: Request,
    error: str | None = None,
):
    """Render member registration page."""
    current_user = _get_current_user(request)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "active_page": "auth",
            "page_title": "Registrasi Anggota — Smart Library RecSys",
            "content_only": True,
            "current_user": current_user,
            "error": error,
        },
    )


@router.post("/register", include_in_schema=False)
def register_process(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Register a new user with default role 'anggota'."""
    clean_name = name.strip()
    clean_email = email.strip().lower()

    if not clean_name or not clean_email or not password:
        msg = quote_plus("Nama lengkap, email, dan password wajib diisi.")
        return RedirectResponse(url=f"/auth/register?error={msg}", status_code=303)

    if len(password) < 6:
        msg = quote_plus("Password minimal terdiri dari 6 karakter.")
        return RedirectResponse(url=f"/auth/register?error={msg}", status_code=303)

    if password != confirm_password:
        msg = quote_plus("Konfirmasi password tidak cocok.")
        return RedirectResponse(url=f"/auth/register?error={msg}", status_code=303)

    hashed_pw = _hash_password(password)

    try:
        with get_connection() as connection:
            _ensure_password_column(connection)
            existing = connection.execute(
                "SELECT id FROM users WHERE LOWER(email) = ?",
                (clean_email,),
            ).fetchone()
            if existing is not None:
                msg = quote_plus("Email sudah terdaftar. Silakan gunakan email lain atau login.")
                return RedirectResponse(url=f"/auth/register?error={msg}", status_code=303)

            connection.execute(
                "INSERT INTO users (name, email, role, password) VALUES (?, ?, 'anggota', ?)",
                (clean_name, clean_email, hashed_pw),
            )
            connection.commit()
    except sqlite3.IntegrityError:
        msg = quote_plus("Gagal mendaftarkan akun karena email sudah digunakan.")
        return RedirectResponse(url=f"/auth/register?error={msg}", status_code=303)

    success_msg = quote_plus("Registrasi anggota berhasil. Silakan login menggunakan akun Anda.")
    return RedirectResponse(url=f"/auth/login?success={success_msg}", status_code=303)


@router.get("/anggota", response_class=HTMLResponse, include_in_schema=False)
def manage_users_page(
    request: Request,
    q: str = "",
    role_filter: str = "",
    error: str | None = None,
    success: str | None = None,
):
    """Display all users and member management controls for Petugas & Pengelola."""
    current_user = _get_current_user(request)
    if current_user is None:
        msg = quote_plus("Silakan login terlebih dahulu untuk mengakses Manajemen Anggota.")
        return RedirectResponse(url=f"/auth/login?error={msg}", status_code=303)

    if current_user["role"] not in ("petugas", "pengelola"):
        msg = quote_plus("Akses ditolak. Halaman Manajemen Anggota hanya untuk Petugas atau Pengelola.")
        return RedirectResponse(url=f"/auth/login?error={msg}", status_code=303)

    search_term = q.strip()
    selected_role = role_filter.strip().lower()

    with get_connection() as connection:
        _ensure_password_column(connection)

        query = "SELECT id, name, email, role, created_at FROM users WHERE 1=1"
        params: list[str] = []

        if search_term:
            query += " AND (LOWER(name) LIKE ? OR LOWER(email) LIKE ?)"
            wildcard = f"%{search_term.lower()}%"
            params.extend([wildcard, wildcard])

        if selected_role in VALID_ROLES:
            query += " AND role = ?"
            params.append(selected_role)

        query += " ORDER BY id ASC"
        users = connection.execute(query, tuple(params)).fetchall()

        all_roles = connection.execute(
            "SELECT role, COUNT(*) AS total FROM users GROUP BY role"
        ).fetchall()

    role_counts = {"anggota": 0, "petugas": 0, "pengelola": 0}
    for row in all_roles:
        if row["role"] in role_counts:
            role_counts[row["role"]] = row["total"]

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "active_page": "auth",
            "page_title": "Manajemen Data Anggota — Smart Library RecSys",
            "content_only": True,
            "current_user": current_user,
            "users": users,
            "role_counts": role_counts,
            "total_users": sum(role_counts.values()),
            "valid_roles": VALID_ROLES,
            "search_term": search_term,
            "selected_role": selected_role,
            "error": error,
            "success": success,
        },
    )


@router.post("/anggota/tambah", include_in_schema=False)
def add_user(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("anggota"),
):
    """Create a new user from the member management dashboard."""
    current_user = _get_current_user(request)
    if current_user is None or current_user["role"] not in ("petugas", "pengelola"):
        msg = quote_plus("Anda tidak memiliki hak akses untuk menambah pengguna.")
        return RedirectResponse(url=f"/auth/login?error={msg}", status_code=303)

    clean_name = name.strip()
    clean_email = email.strip().lower()
    clean_role = role.strip().lower()

    if not clean_name or not clean_email or not password:
        msg = quote_plus("Nama, email, dan password wajib diisi.")
        return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

    if len(password) < 6:
        msg = quote_plus("Password minimal 6 karakter.")
        return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

    if clean_role not in VALID_ROLES:
        msg = quote_plus("Role tidak valid. Pilih anggota, petugas, atau pengelola.")
        return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

    hashed_pw = _hash_password(password)

    try:
        with get_connection() as connection:
            _ensure_password_column(connection)
            existing = connection.execute(
                "SELECT id FROM users WHERE LOWER(email) = ?",
                (clean_email,),
            ).fetchone()
            if existing is not None:
                msg = quote_plus(f"Email {clean_email} sudah terdaftar.")
                return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

            connection.execute(
                "INSERT INTO users (name, email, role, password) VALUES (?, ?, ?, ?)",
                (clean_name, clean_email, clean_role, hashed_pw),
            )
            connection.commit()
    except sqlite3.IntegrityError:
        msg = quote_plus("Gagal menambahkan pengguna karena konflik data.")
        return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

    msg = quote_plus(f"Pengguna '{clean_name}' berhasil ditambahkan dengan role {clean_role}.")
    return RedirectResponse(url=f"/auth/anggota?success={msg}", status_code=303)


@router.post("/anggota/role/{user_id}", include_in_schema=False)
def update_user_role(
    request: Request,
    user_id: int,
    role: str = Form(...),
):
    """Update an existing user's role."""
    current_user = _get_current_user(request)
    if current_user is None or current_user["role"] not in ("petugas", "pengelola"):
        msg = quote_plus("Anda tidak memiliki hak akses untuk mengubah role.")
        return RedirectResponse(url=f"/auth/login?error={msg}", status_code=303)

    clean_role = role.strip().lower()
    if clean_role not in VALID_ROLES:
        msg = quote_plus("Role yang dipilih tidak valid.")
        return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

    with get_connection() as connection:
        target = connection.execute(
            "SELECT id, name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            msg = quote_plus("Data pengguna tidak ditemukan.")
            return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

        connection.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (clean_role, user_id),
        )
        connection.commit()

    msg = quote_plus(f"Role '{target['name']}' berhasil diubah menjadi {clean_role}.")
    response = RedirectResponse(url=f"/auth/anggota?success={msg}", status_code=303)

    # Sinkronkan cookie role jika pengguna mengubah role miliknya sendiri
    if str(user_id) == current_user["id"]:
        response.set_cookie(
            key="user_role",
            value=clean_role,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
        )

    return response


@router.post("/anggota/hapus/{user_id}", include_in_schema=False)
def delete_user(
    request: Request,
    user_id: int,
):
    """Delete a user by ID."""
    current_user = _get_current_user(request)
    if current_user is None or current_user["role"] not in ("petugas", "pengelola"):
        msg = quote_plus("Anda tidak memiliki hak akses untuk menghapus pengguna.")
        return RedirectResponse(url=f"/auth/login?error={msg}", status_code=303)

    if str(user_id) == current_user["id"]:
        msg = quote_plus("Anda tidak dapat menghapus akun yang sedang aktif digunakan.")
        return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

    with get_connection() as connection:
        target = connection.execute(
            "SELECT id, name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            msg = quote_plus("Data pengguna tidak ditemukan.")
            return RedirectResponse(url=f"/auth/anggota?error={msg}", status_code=303)

        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()

    msg = quote_plus(f"Pengguna '{target['name']}' berhasil dihapus.")
    return RedirectResponse(url=f"/auth/anggota?success={msg}", status_code=303)