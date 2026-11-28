"""Circulation module (FR-03: Peminjaman & Pengembalian Buku)."""

from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_connection

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

LOAN_DURATION_DAYS = 7
FINE_PER_DAY = 2000  # Rp 2.000 per hari keterlambatan

router = APIRouter(tags=["Circulation"])
sirkulasi_router = APIRouter(prefix="/sirkulasi")
legacy_router = APIRouter(prefix="/circulation")


def _ensure_circulation_schema() -> None:
    """
    Memastikan tabel borrowings mendukung status 'menunggu' dan 'ditolak',
    serta memiliki kolom due_date dan fine tanpa menghapus data seed yang ada.
    Kolom due_date dibuat nullable dengan backfill otomatis agar seed_data.py
    tetap kompatibel saat dijalankan ulang.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='borrowings'"
        ).fetchone()
        if not row or not row["sql"]:
            return

        schema_sql = row["sql"]
        needs_migration = (
            "'menunggu'" not in schema_sql
            or "due_date" not in schema_sql
            or "fine" not in schema_sql
        )

        if needs_migration:
            existing_cols = {
                col["name"]
                for col in connection.execute("PRAGMA table_info(borrowings)").fetchall()
            }
            due_date_expr = (
                "COALESCE(due_date, date(borrowed_at, '+7 days'))"
                if "due_date" in existing_cols
                else "date(borrowed_at, '+7 days')"
            )
            fine_expr = "COALESCE(fine, 0)" if "fine" in existing_cols else "0"

            connection.execute("PRAGMA foreign_keys = OFF")
            try:
                connection.executescript(
                    f"""
                    BEGIN TRANSACTION;

                    CREATE TABLE borrowings_migrated (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        book_id INTEGER NOT NULL,
                        borrowed_at TEXT NOT NULL,
                        due_date TEXT,
                        returned_at TEXT,
                        status TEXT NOT NULL CHECK (status IN ('menunggu', 'dipinjam', 'dikembalikan', 'ditolak')),
                        fine INTEGER NOT NULL DEFAULT 0 CHECK (fine >= 0),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                    );

                    INSERT INTO borrowings_migrated (id, user_id, book_id, borrowed_at, due_date, returned_at, status, fine)
                    SELECT
                        id,
                        user_id,
                        book_id,
                        borrowed_at,
                        {due_date_expr},
                        returned_at,
                        status,
                        {fine_expr}
                    FROM borrowings;

                    DROP TABLE borrowings;
                    ALTER TABLE borrowings_migrated RENAME TO borrowings;

                    CREATE INDEX IF NOT EXISTS idx_borrowings_user ON borrowings(user_id);
                    CREATE INDEX IF NOT EXISTS idx_borrowings_book ON borrowings(book_id);
                    CREATE INDEX IF NOT EXISTS idx_borrowings_status ON borrowings(status);

                    COMMIT;
                    """
                )
            except Exception:
                connection.execute("ROLLBACK")
                raise
            finally:
                connection.execute("PRAGMA foreign_keys = ON")

        # Backfill due_date jika ada baris baru dari seed_data.py yang belum memiliki due_date
        connection.execute(
            """
            UPDATE borrowings
            SET due_date = date(borrowed_at, '+7 days')
            WHERE due_date IS NULL OR due_date = ''
            """
        )


# Jalankan pengecekan skema saat router di-import oleh main.py
_ensure_circulation_schema()


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _calculate_overdue_and_fine(
    status: str,
    borrowed_at_str: str,
    due_date_str: Optional[str],
    returned_at_str: Optional[str],
    saved_fine: int,
) -> tuple[int, int]:
    """Menghitung (hari_terlambat, nominal_denda) dalam Rupiah."""
    borrowed_dt = _parse_iso_date(borrowed_at_str) or date.today()
    due_dt = _parse_iso_date(due_date_str) or (borrowed_dt + timedelta(days=LOAN_DURATION_DAYS))

    if status == "dipinjam":
        overdue_days = max(0, (date.today() - due_dt).days)
        return overdue_days, overdue_days * FINE_PER_DAY

    if status == "dikembalikan":
        returned_dt = _parse_iso_date(returned_at_str)
        if returned_dt:
            overdue_days = max(0, (returned_dt - due_dt).days)
            fine = saved_fine if saved_fine > 0 else overdue_days * FINE_PER_DAY
            return overdue_days, fine
        return 0, saved_fine

    return 0, 0


def _redirect_with_message(message: str, msg_type: str = "success") -> RedirectResponse:
    encoded_msg = quote(message)
    return RedirectResponse(
        url=f"/sirkulasi?msg={encoded_msg}&type={msg_type}",
        status_code=303,
    )


@legacy_router.get("/status")
def circulation_status():
    return {"module": "circulation", "status": "active", "owner": "Wildan & Azrur"}


@sirkulasi_router.get("", response_class=HTMLResponse, include_in_schema=False)
def circulation_page(
    request: Request,
    status_filter: str = "semua",
    msg: Optional[str] = None,
    type: str = "success",
):
    _ensure_circulation_schema()

    valid_filters = {"semua", "menunggu", "dipinjam", "dikembalikan", "ditolak"}
    active_filter = status_filter if status_filter in valid_filters else "semua"

    with get_connection() as connection:
        users = connection.execute(
            """
            SELECT id, name, email, role
            FROM users
            ORDER BY CASE WHEN role = 'anggota' THEN 0 ELSE 1 END, name ASC
            """
        ).fetchall()

        available_books = connection.execute(
            """
            SELECT id, title, author, category, stock, total_stock
            FROM books
            WHERE stock > 0
            ORDER BY title ASC
            """
        ).fetchall()

        base_query = """
            SELECT
                br.id,
                br.user_id,
                br.book_id,
                br.borrowed_at,
                COALESCE(br.due_date, date(br.borrowed_at, '+7 days')) AS due_date,
                br.returned_at,
                br.status,
                br.fine,
                u.name AS user_name,
                u.email AS user_email,
                u.role AS user_role,
                b.title AS book_title,
                b.author AS book_author,
                b.category AS book_category,
                b.stock AS book_stock
            FROM borrowings br
            INNER JOIN users u ON br.user_id = u.id
            INNER JOIN books b ON br.book_id = b.id
        """
        if active_filter != "semua":
            raw_rows = connection.execute(
                base_query
                + """
                WHERE br.status = ?
                ORDER BY
                    CASE br.status
                        WHEN 'menunggu' THEN 1
                        WHEN 'dipinjam' THEN 2
                        WHEN 'dikembalikan' THEN 3
                        ELSE 4
                    END,
                    br.id DESC
                """,
                (active_filter,),
            ).fetchall()
        else:
            raw_rows = connection.execute(
                base_query
                + """
                ORDER BY
                    CASE br.status
                        WHEN 'menunggu' THEN 1
                        WHEN 'dipinjam' THEN 2
                        WHEN 'dikembalikan' THEN 3
                        ELSE 4
                    END,
                    br.id DESC
                """
            ).fetchall()

        all_rows = connection.execute(
            """
            SELECT
                status,
                borrowed_at,
                COALESCE(due_date, date(borrowed_at, '+7 days')) AS due_date,
                returned_at,
                fine
            FROM borrowings
            """
        ).fetchall()

    stats = {
        "menunggu": 0,
        "dipinjam": 0,
        "dikembalikan": 0,
        "ditolak": 0,
        "terlambat": 0,
        "total_estimasi_denda": 0,
    }
    for r in all_rows:
        st = r["status"]
        if st in stats:
            stats[st] += 1
        overdue_days, fine_val = _calculate_overdue_and_fine(
            status=st,
            borrowed_at_str=r["borrowed_at"],
            due_date_str=r["due_date"],
            returned_at_str=r["returned_at"],
            saved_fine=r["fine"] or 0,
        )
        if st == "dipinjam" and overdue_days > 0:
            stats["terlambat"] += 1
            stats["total_estimasi_denda"] += fine_val

    transactions = []
    for row in raw_rows:
        overdue_days, fine_val = _calculate_overdue_and_fine(
            status=row["status"],
            borrowed_at_str=row["borrowed_at"],
            due_date_str=row["due_date"],
            returned_at_str=row["returned_at"],
            saved_fine=row["fine"] or 0,
        )
        item = dict(row)
        item["overdue_days"] = overdue_days
        item["estimated_fine"] = fine_val
        transactions.append(item)

    return templates.TemplateResponse(
        request=request,
        name="circulation.html",
        context={
            "active_page": "circulation",
            "page_title": "Sirkulasi Peminjaman & Pengembalian — Smart Library",
            "content_only": False,
            "users": users,
            "available_books": available_books,
            "transactions": transactions,
            "stats": stats,
            "active_filter": active_filter,
            "loan_duration_days": LOAN_DURATION_DAYS,
            "fine_per_day": FINE_PER_DAY,
            "flash_msg": msg,
            "flash_type": type if type in {"success", "error"} else "success",
        },
    )


@sirkulasi_router.post("/pinjam", include_in_schema=False)
def create_borrowing_request(
    user_id: int = Form(...),
    book_id: int = Form(...),
):
    """Pengajuan peminjaman baru oleh anggota dengan status awal 'menunggu'."""
    _ensure_circulation_schema()

    today = date.today()
    due_dt = today + timedelta(days=LOAN_DURATION_DAYS)

    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            return _redirect_with_message("Anggota tidak ditemukan.", "error")

        book = connection.execute(
            "SELECT id, title, stock FROM books WHERE id = ?",
            (book_id,),
        ).fetchone()
        if not book:
            return _redirect_with_message("Buku tidak ditemukan.", "error")

        if book["stock"] <= 0:
            return _redirect_with_message(
                f"Stok buku '{book['title']}' habis (0 tersedia).",
                "error",
            )

        duplicate = connection.execute(
            """
            SELECT id FROM borrowings
            WHERE user_id = ? AND book_id = ? AND status IN ('menunggu', 'dipinjam')
            """,
            (user_id, book_id),
        ).fetchone()
        if duplicate:
            return _redirect_with_message(
                f"{user['name']} masih memiliki pengajuan atau pinjaman aktif untuk buku '{book['title']}'.",
                "error",
            )

        connection.execute(
            """
            INSERT INTO borrowings (user_id, book_id, borrowed_at, due_date, returned_at, status, fine)
            VALUES (?, ?, ?, ?, NULL, 'menunggu', 0)
            """,
            (user_id, book_id, today.isoformat(), due_dt.isoformat()),
        )

    return _redirect_with_message(
        f"Pengajuan pinjam '{book['title']}' oleh {user['name']} berhasil dibuat (status: menunggu verifikasi petugas).",
        "success",
    )


@sirkulasi_router.post("/verifikasi/{borrowing_id}", include_in_schema=False)
def verify_borrowing_request(
    borrowing_id: int,
    action: str = Form(...),
):
    """Verifikasi pengajuan peminjaman oleh petugas ('setujui' atau 'tolak')."""
    _ensure_circulation_schema()

    normalized_action = action.strip().lower()
    if normalized_action not in {"setujui", "tolak"}:
        return _redirect_with_message("Aksi verifikasi tidak valid.", "error")

    with get_connection() as connection:
        borrowing = connection.execute(
            """
            SELECT br.id, br.status, br.book_id, b.title AS book_title, b.stock AS book_stock, u.name AS user_name
            FROM borrowings br
            INNER JOIN books b ON br.book_id = b.id
            INNER JOIN users u ON br.user_id = u.id
            WHERE br.id = ?
            """,
            (borrowing_id,),
        ).fetchone()

        if not borrowing:
            return _redirect_with_message("Data transaksi peminjaman tidak ditemukan.", "error")

        if borrowing["status"] != "menunggu":
            return _redirect_with_message(
                f"Transaksi #{borrowing_id} sudah diproses sebelumnya (status: {borrowing['status']}).",
                "error",
            )

        if normalized_action == "tolak":
            connection.execute(
                "UPDATE borrowings SET status = 'ditolak' WHERE id = ?",
                (borrowing_id,),
            )
            return _redirect_with_message(
                f"Pengajuan #{borrowing_id} ('{borrowing['book_title']}' - {borrowing['user_name']}) telah ditolak.",
                "success",
            )

        if borrowing["book_stock"] <= 0:
            return _redirect_with_message(
                f"Gagal menyetujui: stok buku '{borrowing['book_title']}' sudah habis.",
                "error",
            )

        today = date.today()
        due_dt = today + timedelta(days=LOAN_DURATION_DAYS)

        connection.execute(
            """
            UPDATE borrowings
            SET status = 'dipinjam',
                borrowed_at = ?,
                due_date = ?
            WHERE id = ?
            """,
            (today.isoformat(), due_dt.isoformat(), borrowing_id),
        )
        connection.execute(
            "UPDATE books SET stock = stock - 1 WHERE id = ? AND stock > 0",
            (borrowing["book_id"],),
        )

    return _redirect_with_message(
        f"Pengajuan #{borrowing_id} disetujui. Buku '{borrowing['book_title']}' dipinjam oleh {borrowing['user_name']} (jatuh tempo {due_dt.isoformat()}).",
        "success",
    )


@sirkulasi_router.post("/kembali/{borrowing_id}", include_in_schema=False)
def return_borrowed_book(borrowing_id: int):
    """Proses pengembalian buku, hitung denda keterlambatan, dan kembalikan stok +1."""
    _ensure_circulation_schema()

    with get_connection() as connection:
        borrowing = connection.execute(
            """
            SELECT br.id, br.status, br.book_id, br.borrowed_at, br.due_date,
                   b.title AS book_title, u.name AS user_name
            FROM borrowings br
            INNER JOIN books b ON br.book_id = b.id
            INNER JOIN users u ON br.user_id = u.id
            WHERE br.id = ?
            """,
            (borrowing_id,),
        ).fetchone()

        if not borrowing:
            return _redirect_with_message("Data peminjaman tidak ditemukan.", "error")

        if borrowing["status"] != "dipinjam":
            return _redirect_with_message(
                f"Transaksi #{borrowing_id} tidak berstatus 'dipinjam' (status saat ini: {borrowing['status']}).",
                "error",
            )

        today = date.today()
        borrowed_dt = _parse_iso_date(borrowing["borrowed_at"]) or today
        due_dt = _parse_iso_date(borrowing["due_date"]) or (borrowed_dt + timedelta(days=LOAN_DURATION_DAYS))
        overdue_days = max(0, (today - due_dt).days)
        fine_amount = overdue_days * FINE_PER_DAY

        connection.execute(
            """
            UPDATE borrowings
            SET status = 'dikembalikan',
                returned_at = ?,
                fine = ?
            WHERE id = ?
            """,
            (today.isoformat(), fine_amount, borrowing_id),
        )
        connection.execute(
            "UPDATE books SET stock = stock + 1 WHERE id = ?",
            (borrowing["book_id"],),
        )

    if fine_amount > 0:
        formatted_fine = f"Rp {fine_amount:,}".replace(",", ".")
        return _redirect_with_message(
            f"Buku '{borrowing['book_title']}' dikembalikan oleh {borrowing['user_name']}. Terlambat {overdue_days} hari — Denda: {formatted_fine}.",
            "success",
        )

    return _redirect_with_message(
        f"Buku '{borrowing['book_title']}' berhasil dikembalikan tepat waktu oleh {borrowing['user_name']} (Denda: Rp 0).",
        "success",
    )


router.include_router(sirkulasi_router)
router.include_router(legacy_router)