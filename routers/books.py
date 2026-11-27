
"""
FR-02: Manajemen Katalog dan Pencarian Buku
Owner: Muh. Dhia Ul Khaq
Framework: FastAPI + SQLite + Jinja2
"""

import sqlite3

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_connection
from services.recommender_engine import RecommenderEngine


router = APIRouter(tags=["Katalog Buku"])

templates = Jinja2Templates(directory="templates")

# Engine rekomendasi FR-04
recommender = RecommenderEngine()


# =====================================================
# 1. HALAMAN KATALOG BUKU
# GET /katalog
# =====================================================

@router.get("/katalog", name="catalog")
def catalog(
    request: Request,
    q: str = "",
    kategori: str = ""
):
    with get_connection() as connection:

        # Query dasar
        query = """
            SELECT *
            FROM books
            WHERE 1=1
        """

        parameters = []

        # Pencarian berdasarkan judul atau penulis
        if q.strip():
            query += """
                AND (
                    title LIKE ?
                    OR author LIKE ?
                )
            """

            keyword = f"%{q.strip()}%"
            parameters.extend([keyword, keyword])

        # Filter berdasarkan kategori
        if kategori.strip():
            query += " AND category = ?"
            parameters.append(kategori.strip())

        query += " ORDER BY created_at DESC, id DESC"

        books = connection.execute(
            query,
            parameters
        ).fetchall()

        # Mengambil daftar kategori yang tersedia
        categories = connection.execute("""
            SELECT DISTINCT category
            FROM books
            WHERE category IS NOT NULL
              AND category != ''
            ORDER BY category ASC
        """).fetchall()

    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context={
            "page_title": "Katalog Buku",
            "active_page": "catalog",
            "books": books,
            "categories": categories,
            "q": q,
            "kategori": kategori,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error")
        }
    )


# =====================================================
# 2. HALAMAN DETAIL BUKU
# GET /katalog/{book_id}
# =====================================================

@router.get("/katalog/{book_id}", name="book_detail")
def book_detail(request: Request, book_id: int):

    with get_connection() as connection:

        book = connection.execute("""
            SELECT *
            FROM books
            WHERE id = ?
        """, (book_id,)).fetchone()

    # Jika buku tidak ditemukan
    if book is None:
        raise HTTPException(
            status_code=404,
            detail="Buku tidak ditemukan."
        )

    # Mengambil rekomendasi buku serupa dari FR-04
    similar_books = []
    recommendation_error = None

    try:
        result = recommender.similar_books(
            book_id=book_id,
            limit=5
        )

        similar_books = result.get("recommendations", [])

    except Exception as error:
        # Detail buku tetap bisa ditampilkan meskipun
        # engine rekomendasi mengalami masalah.
        recommendation_error = str(error)
        similar_books = []

    return templates.TemplateResponse(
        request=request,
        name="book_detail.html",
        context={
            "page_title": book["title"],
            "active_page": "catalog",
            "book": book,
            "similar_books": similar_books,
            "recommendation_error": recommendation_error
        }
    )


# =====================================================
# 3. TAMBAH BUKU
# POST /katalog/tambah
# =====================================================

@router.post("/katalog/tambah", name="add_book")
def add_book(
    title: str = Form(...),
    author: str = Form(...),
    category: str = Form(...),
    synopsis: str = Form(...),
    stock: int = Form(...)
):

    # Validasi input
    title = title.strip()
    author = author.strip()
    category = category.strip()
    synopsis = synopsis.strip()

    if not all([title, author, category, synopsis]):
        raise HTTPException(
            status_code=400,
            detail="Semua data buku wajib diisi."
        )

    if stock < 0:
        raise HTTPException(
            status_code=400,
            detail="Stok buku tidak boleh negatif."
        )

    try:
        with get_connection() as connection:

            connection.execute("""
                INSERT INTO books (
                    title,
                    author,
                    category,
                    synopsis,
                    stock,
                    total_stock
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                title,
                author,
                category,
                synopsis,
                stock,
                stock
            ))

        return RedirectResponse(
            url="/katalog?success=Buku berhasil ditambahkan",
            status_code=303
        )

    except sqlite3.Error:
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan saat menyimpan buku."
        )


# =====================================================
# 4. EDIT BUKU
# POST /katalog/edit/{book_id}
# =====================================================

@router.post("/katalog/edit/{book_id}", name="edit_book")
def edit_book(
    book_id: int,
    title: str = Form(...),
    author: str = Form(...),
    category: str = Form(...),
    synopsis: str = Form(...),
    stock: int = Form(...)
):

    title = title.strip()
    author = author.strip()
    category = category.strip()
    synopsis = synopsis.strip()

    if not all([title, author, category, synopsis]):
        raise HTTPException(
            status_code=400,
            detail="Semua data buku wajib diisi."
        )

    if stock < 0:
        raise HTTPException(
            status_code=400,
            detail="Stok buku tidak boleh negatif."
        )

    try:
        with get_connection() as connection:

            existing_book = connection.execute("""
                SELECT id
                FROM books
                WHERE id = ?
            """, (book_id,)).fetchone()

            if existing_book is None:
                raise HTTPException(
                    status_code=404,
                    detail="Buku tidak ditemukan."
                )

            connection.execute("""
                UPDATE books
                SET
                    title = ?,
                    author = ?,
                    category = ?,
                    synopsis = ?,
                    stock = ?
                WHERE id = ?
            """, (
                title,
                author,
                category,
                synopsis,
                stock,
                book_id
            ))

        return RedirectResponse(
            url="/katalog?success=Buku berhasil diperbarui",
            status_code=303
        )

    except sqlite3.Error:
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan saat memperbarui buku."
        )


# =====================================================
# 5. HAPUS BUKU
# POST /katalog/hapus/{book_id}
# =====================================================

@router.post("/katalog/hapus/{book_id}", name="delete_book")
def delete_book(book_id: int):

    try:
        with get_connection() as connection:

            existing_book = connection.execute("""
                SELECT id
                FROM books
                WHERE id = ?
            """, (book_id,)).fetchone()

            if existing_book is None:
                raise HTTPException(
                    status_code=404,
                    detail="Buku tidak ditemukan."
                )

            connection.execute("""
                DELETE FROM books
                WHERE id = ?
            """, (book_id,))

        return RedirectResponse(
            url="/katalog?success=Buku berhasil dihapus",
            status_code=303
        )

    except sqlite3.Error:
        raise HTTPException(
            status_code=500,
            detail="Terjadi kesalahan saat menghapus buku."
        )


# =====================================================
# 6. STATUS MODUL
# GET /books/status
# Mempertahankan endpoint placeholder sebelumnya.
# =====================================================

@router.get("/books/status", name="books_status")
def books_status():

    with get_connection() as connection:
        total_books = connection.execute("""
            SELECT COUNT(*) AS total
            FROM books
        """).fetchone()["total"]

    return {
        "module": "books",
        "status": "active",
        "owner": "Dhia",
        "total_books": total_books
    }
