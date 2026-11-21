"""Hybrid recommendation engine for FR-04.

The engine is intentionally stateless. It loads small SQLite tables into pandas,
then builds one TF-IDF matrix per request. This keeps local development simple
and avoids stale in-memory data after seed updates.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database import get_connection


class RecommenderEngine:
    """Content and borrowing-history recommender for library books."""

    def _load_books(self) -> pd.DataFrame:
        with get_connection() as connection:
            frame = pd.read_sql_query(
                "SELECT id, title, author, category, synopsis, stock FROM books ORDER BY id",
                connection,
            )
        if frame.empty:
            return frame
        frame["features"] = (
            frame["category"].fillna("")
            + " "
            + frame["title"].fillna("")
            + " "
            + frame["synopsis"].fillna("")
        )
        return frame

    def _content_matrix(self, books: pd.DataFrame):
        vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=5000)
        matrix = vectorizer.fit_transform(books["features"])
        return matrix

    @staticmethod
    def _book_payload(row: pd.Series, score: float, reason: str) -> dict[str, Any]:
        return {
            "book_id": int(row["id"]),
            "title": str(row["title"]),
            "author": str(row["author"]),
            "category": str(row["category"]),
            "stock": int(row["stock"]),
            "score": round(float(score), 4),
            "score_percent": round(float(score) * 100, 2),
            "reason": reason,
        }

    def similar_books(self, book_id: int, limit: int = 5) -> dict[str, Any]:
        """Return books close to one selected book by TF-IDF cosine similarity."""
        books = self._load_books()
        if books.empty:
            raise ValueError("Belum ada data buku")
        matches = books.index[books["id"] == book_id].tolist()
        if not matches:
            raise ValueError(f"Buku dengan id {book_id} tidak ditemukan")

        matrix = self._content_matrix(books)
        selected_index = matches[0]
        scores = cosine_similarity(matrix[selected_index], matrix).ravel()
        ranked = books.assign(_score=scores).drop(index=selected_index)
        ranked = ranked.sort_values(["_score", "id"], ascending=[False, True]).head(limit)
        selected = books.loc[selected_index]
        items = [
            self._book_payload(
                row,
                row["_score"],
                f"Mirip dengan buku pilihan pada tema {selected['category']} dan konteks sinopsis.",
            )
            for _, row in ranked.iterrows()
        ]
        return {
            "mode": "content-based",
            "source_book": {
                "book_id": int(selected["id"]),
                "title": str(selected["title"]),
                "category": str(selected["category"]),
            },
            "recommendations": items,
        }

    def user_recommendations(self, user_id: int, limit: int = 5) -> dict[str, Any]:
        """Recommend unseen books from a user's history, with popularity fallback."""
        books = self._load_books()
        if books.empty:
            raise ValueError("Belum ada data buku")
        with get_connection() as connection:
            history = pd.read_sql_query(
                "SELECT book_id FROM borrowings WHERE user_id = ? ORDER BY borrowed_at",
                connection,
                params=(user_id,),
            )
            user = connection.execute("SELECT id, name, role FROM users WHERE id = ?", (user_id,)).fetchone()
            popularity = pd.read_sql_query(
                "SELECT book_id, COUNT(*) AS borrow_count FROM borrowings GROUP BY book_id",
                connection,
            )
        if user is None:
            raise ValueError(f"User dengan id {user_id} tidak ditemukan")

        seen_ids = set(history["book_id"].astype(int).tolist())
        candidates = books[~books["id"].isin(seen_ids)].copy()
        if candidates.empty:
            candidates = books.copy()

        if history.empty:
            ranked = candidates.merge(popularity, left_on="id", right_on="book_id", how="left")
            ranked["borrow_count"] = ranked["borrow_count"].fillna(0)
            ranked = ranked.sort_values(["borrow_count", "id"], ascending=[False, True]).head(limit)
            items = [
                self._book_payload(
                    row,
                    min(float(row["borrow_count"]) / max(float(popularity["borrow_count"].max() or 1), 1), 1.0),
                    "Fallback buku populer karena user belum memiliki riwayat peminjaman.",
                )
                for _, row in ranked.iterrows()
            ]
            mode = "popular-fallback"
        else:
            matrix = self._content_matrix(books)
            history_indices = books.index[books["id"].isin(seen_ids)].tolist()
            candidate_indices = candidates.index.tolist()
            profile = matrix[history_indices].mean(axis=0)
            scores = cosine_similarity(profile.A, matrix[candidate_indices]).ravel()
            candidates["_score"] = scores
            ranked = candidates.sort_values(["_score", "id"], ascending=[False, True]).head(limit)
            items = [
                self._book_payload(
                    row,
                    row["_score"],
                    "Cocok dengan profil kategori dan topik dari riwayat pinjaman user.",
                )
                for _, row in ranked.iterrows()
            ]
            mode = "history-based"

        return {
            "mode": mode,
            "user": {"user_id": int(user["id"]), "name": str(user["name"]), "role": str(user["role"])},
            "history_count": int(len(history)),
            "recommendations": items,
        }
