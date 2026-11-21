# Smart Library RecSys

Fondasi full-stack Tugas Besar Rekayasa Perangkat Lunak. Backend memakai FastAPI, database SQLite, template Jinja2, dan Tailwind CSS melalui CDN. FR-04 memakai hybrid book recommendation engine berbasis TF-IDF dan cosine similarity.

## Struktur kerja tim

```text
smart-library-recsys/
├── main.py                         # Entry point FastAPI dan registrasi router
├── database.py                     # SQLite, schema, koneksi
├── seed_data.py                    # 50 buku, 10 user, 80 transaksi deterministik
├── services/
│   └── recommender_engine.py       # Implementasi FR-04, dimiliki Lead Engineer
├── routers/
│   ├── auth.py                     # Anggota 4, Rifa
│   ├── books.py                    # Anggota 3, Dhia
│   ├── circulation.py              # Anggota 2, Wildan
│   ├── recommendations.py          # Lead Engineer, FR-04
│   └── analytics.py                # Anggota 5, Azrur
├── templates/
│   ├── base.html                   # Layout dan sidebar
│   └── recommendations.html        # UI simulasi FR-04
├── static/style.css
├── requirements.txt
└── vercel.json
```

Setiap anggota bekerja di router atau service yang ditugaskan. `main.py`, `database.py`, schema, dan kontrak endpoint menjadi area integrasi Lead Engineer. Perubahan lintas modul dibahas sebelum merge untuk menjaga konflik Git rendah.

## Menjalankan lokal

Python 3.10+ dibutuhkan.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python seed_data.py
python -m uvicorn main:app --reload
```

Buka `http://127.0.0.1:8000/rekomendasi`. Health check tersedia di `http://127.0.0.1:8000/health`.

Seed aman dijalankan ulang karena mengisi ulang tiga tabel demo. Database lokal `library.db` tidak perlu dibuat manual.

## Kontrak FR-04

- `GET /api/recommendations/user/{user_id}`: rekomendasi personal. User dengan histori memakai profil TF-IDF dari buku yang pernah dipinjam. User tanpa histori memakai fallback buku paling populer.
- `GET /api/recommendations/similar/{book_id}`: content-based filtering untuk buku serupa.
- `GET /rekomendasi`: halaman interaktif untuk memilih user atau buku, membaca skor cosine similarity, dan melihat alasan rekomendasi.

Feature text engine adalah gabungan `kategori + judul + sinopsis`. Matrix dibuat saat request agar seed atau perubahan katalog langsung terbaca dan penggunaan RAM tetap ringan untuk laptop lokal.

## Deployment Vercel

`vercel.json` mengarahkan seluruh request ke `main.py` menggunakan builder Python Vercel. SQLite cocok untuk demo dan tugas lokal. Untuk deployment production multi-instance, database perlu dipindahkan ke storage persisten terkelola karena filesystem serverless tidak menjamin persistensi write.

## Diagram Mermaid FR-04 dan sistem

### Use Case Diagram

```mermaid
flowchart LR
    Anggota([Aktor: Anggota])
    Petugas([Aktor: Petugas])
    Pengelola([Aktor: Pengelola])
    Auth((Kelola akun dan autentikasi))
    Books((Kelola katalog buku))
    Circulation((Kelola peminjaman dan pengembalian))
    Recs((Lihat rekomendasi buku FR-04))
    Analytics((Lihat analitik perpustakaan))
    Anggota --> Auth
    Anggota --> Books
    Anggota --> Circulation
    Anggota --> Recs
    Petugas --> Auth
    Petugas --> Books
    Petugas --> Circulation
    Petugas --> Recs
    Pengelola --> Auth
    Pengelola --> Books
    Pengelola --> Circulation
    Pengelola --> Recs
    Pengelola --> Analytics
```

### Class Diagram

```mermaid
classDiagram
    class User {
      +int id
      +string name
      +string email
      +string role
    }
    class Book {
      +int id
      +string title
      +string author
      +string category
      +string synopsis
      +int stock
    }
    class Borrowing {
      +int id
      +int user_id
      +int book_id
      +date borrowed_at
      +date returned_at
      +string status
    }
    class Database {
      +get_connection()
      +init_db()
    }
    class RecommenderEngine {
      +similar_books(book_id, limit)
      +user_recommendations(user_id, limit)
      -_load_books()
      -_content_matrix(books)
    }
    class RecommendationRouter {
      +recommend_for_user(user_id)
      +similar_to_book(book_id)
    }
    User "1" --> "many" Borrowing : makes
    Book "1" --> "many" Borrowing : appears in
    Database ..> User : stores
    Database ..> Book : stores
    Database ..> Borrowing : stores
    RecommendationRouter --> RecommenderEngine : calls
    RecommenderEngine --> Database : reads
```

### Activity Diagram FR-04

```mermaid
flowchart TD
    Start([Mulai]) --> Input{Pilih mode}
    Input -->|User| ReadUser[Ambil user dan histori peminjaman]
    Input -->|Buku| ReadBook[Ambil buku pilihan]
    ReadUser --> HasHistory{Ada histori?}
    HasHistory -->|Tidak| Popular[Hitung frekuensi peminjaman]
    Popular --> RankPopular[Urutkan Top Popular Books]
    HasHistory -->|Ya| Profile[Agregasi profil TF-IDF dari buku yang pernah dipinjam]
    Profile --> Candidate[Ambil buku yang belum pernah dipinjam]
    Candidate --> Similarity[Hitung cosine similarity]
    ReadBook --> Matrix[Gabungkan kategori, judul, sinopsis]
    Matrix --> SimilarityBook[Hitung cosine similarity antar buku]
    Similarity --> Rank[Urutkan skor menurun]
    SimilarityBook --> Rank
    RankPopular --> Response[Bangun response dengan skor dan alasan]
    Rank --> Response
    Response --> End([Tampilkan hasil])
```

### Sequence Diagram FR-04

```mermaid
sequenceDiagram
    actor Penguji
    participant UI as Recommendations UI
    participant Router as RecommendationRouter
    participant Engine as RecommenderEngine
    participant DB as SQLite Database
    Penguji->>UI: Pilih User atau Buku
    UI->>Router: GET /api/recommendations/{mode}/{id}
    Router->>Engine: user_recommendations() atau similar_books()
    Engine->>DB: Query users, books, borrowings
    DB-->>Engine: Data katalog dan histori
    Engine->>Engine: Bangun TF-IDF dan cosine similarity
    Engine->>Engine: Ranking kandidat dan susun alasan
    Engine-->>Router: JSON recommendations, score, reason
    Router-->>UI: HTTP 200 JSON
    UI->>UI: Render kartu hasil dan score bar
    UI-->>Penguji: Skor kemiripan dan alasan rekomendasi
```
