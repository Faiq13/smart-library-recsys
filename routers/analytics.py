"""Analytics & Circulation Reporting module (FR-05)."""

from datetime import date, datetime
import io
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import pandas as pd

from database import get_connection

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Konfigurasi kebijakan sirkulasi untuk kalkulasi keterlambatan & denda
MAX_LOAN_DAYS = 7
FINE_PER_DAY = 2000  # Rp 2.000 per hari keterlambatan


def _load_analytics_dataframes() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Membaca data buku dan riwayat peminjaman dari SQLite ke Pandas DataFrame."""
    with get_connection() as connection:
        books_df = pd.read_sql_query(
            """
            SELECT id, title, author, category, stock, total_stock
            FROM books
            """,
            connection,
        )

        borrowings_df = pd.read_sql_query(
            """
            SELECT
                br.id AS borrowing_id,
                br.user_id,
                u.name AS member_name,
                u.email AS member_email,
                br.book_id,
                b.title AS book_title,
                b.author AS book_author,
                b.category AS book_category,
                br.borrowed_at,
                br.returned_at,
                br.status
            FROM borrowings br
            JOIN users u ON br.user_id = u.id
            JOIN books b ON br.book_id = b.id
            ORDER BY br.borrowed_at DESC, br.id DESC
            """,
            connection,
        )

    if not borrowings_df.empty:
        today_ts = pd.Timestamp(date.today())
        borrowed_dt = pd.to_datetime(borrowings_df["borrowed_at"])
        returned_dt = pd.to_datetime(borrowings_df["returned_at"])

        # Jika belum dikembalikan, hitung durasi berjalan sampai hari ini
        effective_end_dt = returned_dt.fillna(today_ts)
        loan_duration = (effective_end_dt - borrowed_dt).dt.days.clip(lower=0)
        overdue_days = (loan_duration - MAX_LOAN_DAYS).clip(lower=0)

        borrowings_df["loan_days"] = loan_duration.astype(int)
        borrowings_df["overdue_days"] = overdue_days.astype(int)
        borrowings_df["fine_amount"] = (overdue_days * FINE_PER_DAY).astype(int)
    else:
        borrowings_df["loan_days"] = pd.Series(dtype="int")
        borrowings_df["overdue_days"] = pd.Series(dtype="int")
        borrowings_df["fine_amount"] = pd.Series(dtype="int")

    return books_df, borrowings_df


@router.get("/status")
def analytics_status():
    return {"module": "analytics", "status": "active", "owner": "Wildan Kharisma Jati & Azrur"}


@router.get("/laporan", response_class=HTMLResponse)
def analytics_dashboard(request: Request):
    """Menampilkan halaman Dashboard Analitik & Laporan Sirkulasi Perpustakaan (FR-05)."""
    books_df, borrowings_df = _load_analytics_dataframes()

    # 1. Perhitungan Kartu KPI
    total_book_titles = int(len(books_df))
    total_available_stock = int(books_df["stock"].sum()) if not books_df.empty else 0
    total_transactions = int(len(borrowings_df))
    total_fines_collected = int(borrowings_df["fine_amount"].sum()) if not borrowings_df.empty else 0

    # Format nominal rupiah (contoh: Rp 142.000)
    formatted_total_fines = f"Rp {total_fines_collected:,}".replace(",", ".")

    # 2. Agregasi Grafik Peminjaman per Kategori Buku (Bar Chart)
    if not borrowings_df.empty:
        category_counts = (
            borrowings_df.groupby("book_category", as_index=False)["borrowing_id"]
            .count()
            .rename(columns={"borrowing_id": "total_borrowed"})
            .sort_values(by="total_borrowed", ascending=False)
        )
        category_labels = category_counts["book_category"].tolist()
        category_values = category_counts["total_borrowed"].astype(int).tolist()
    else:
        category_labels = []
        category_values = []

    # 3. Agregasi Grafik Status Transaksi (Doughnut Chart)
    status_order = ["dikembalikan", "dipinjam"]
    if not borrowings_df.empty:
        raw_status_counts = borrowings_df["status"].value_counts().to_dict()
        status_labels = ["Dikembalikan", "Sedang Dipinjam"]
        status_values = [int(raw_status_counts.get(s, 0)) for s in status_order]
    else:
        status_labels = ["Dikembalikan", "Sedang Dipinjam"]
        status_values = [0, 0]

    # 4. Tabel 5 Buku Paling Sering Dipinjam
    if not borrowings_df.empty:
        top_books_df = (
            borrowings_df.groupby(["book_id", "book_title", "book_author", "book_category"], as_index=False)
            .agg(
                borrow_count=("borrowing_id", "count"),
                total_fine=("fine_amount", "sum"),
            )
            .sort_values(by=["borrow_count", "book_title"], ascending=[False, True])
            .head(5)
        )
        # Gabungkan informasi stok saat ini dari books_df
        top_books_df = top_books_df.merge(
            books_df[["id", "stock", "total_stock"]],
            left_on="book_id",
            right_on="id",
            how="left",
        )
        top_books = top_books_df.to_dict(orient="records")
    else:
        top_books = []

    context = {
        "active_page": "analytics",
        "page_title": "Laporan & Analitik Sirkulasi - Smart Library",
        "content_only": False,
        "kpi": {
            "total_book_titles": total_book_titles,
            "total_available_stock": total_available_stock,
            "total_transactions": total_transactions,
            "total_fines": formatted_total_fines,
        },
        "chart_category": {
            "labels": category_labels,
            "values": category_values,
        },
        "chart_status": {
            "labels": status_labels,
            "values": status_values,
        },
        "top_books": top_books,
        "generated_at": datetime.now().strftime("%d %b %Y, %H:%M WIB"),
    }

    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context=context,
    )


@router.get("/laporan/export-csv")
def export_circulation_csv():
    """Mengekspor seluruh rekap transaksi peminjaman ke dalam file CSV."""
    _, borrowings_df = _load_analytics_dataframes()

    export_columns = {
        "borrowing_id": "ID_Transaksi",
        "member_name": "Nama_Peminjam",
        "member_email": "Email_Peminjam",
        "book_title": "Judul_Buku",
        "book_author": "Penulis",
        "book_category": "Kategori",
        "borrowed_at": "Tanggal_Pinjam",
        "returned_at": "Tanggal_Kembali",
        "status": "Status_Transaksi",
        "loan_days": "Durasi_Pinjam_Hari",
        "overdue_days": "Keterlambatan_Hari",
        "fine_amount": "Denda_IDR",
    }

    if borrowings_df.empty:
        export_df = pd.DataFrame(columns=list(export_columns.values()))
    else:
        export_df = borrowings_df[list(export_columns.keys())].rename(columns=export_columns)
        export_df["Tanggal_Kembali"] = export_df["Tanggal_Kembali"].fillna("Belum Dikembalikan")

    buffer = io.StringIO()
    export_df.to_csv(buffer, index=False, encoding="utf-8-sig")
    buffer.seek(0)

    filename = f"laporan_sirkulasi_perpustakaan_{date.today().isoformat()}.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )