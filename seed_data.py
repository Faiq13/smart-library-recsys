"""Create deterministic demonstration data for local development."""

from datetime import date, timedelta
import sqlite3

from database import get_connection, init_db

BOOKS = [
    ("Laskar Pelangi", "Andrea Hirata", "Fiksi", "Perjalanan Ikal dan sahabatnya mempertahankan sekolah sederhana di Belitung.", 4),
    ("Bumi Manusia", "Pramoedya Ananta Toer", "Sejarah", "Minke menghadapi ketimpangan kolonial dan perubahan pemikiran pada awal abad kedua puluh.", 3),
    ("Pulang", "Leila S. Chudori", "Sejarah", "Kisah keluarga dan para eksil yang mencari rumah setelah pergolakan politik Indonesia.", 3),
    ("Negeri 5 Menara", "Ahmad Fuadi", "Fiksi", "Enam sahabat belajar disiplin dan mengejar cita-cita dari pesantren.", 5),
    ("Perahu Kertas", "Dee Lestari", "Romansa", "Kugy dan Keenan menemukan arah hidup melalui tulisan, seni, dan pertemuan tak terduga.", 4),
    ("Ronggeng Dukuh Paruk", "Ahmad Tohari", "Fiksi", "Srintil menjalani takdir sebagai ronggeng di tengah perubahan sosial sebuah desa.", 2),
    ("Cantik Itu Luka", "Eka Kurniawan", "Fiksi", "Keluarga Dewi Ayu melewati sejarah panjang dengan humor gelap dan realisme magis.", 3),
    ("Saman", "Ayu Utami", "Fiksi", "Empat sahabat dan seorang aktivis menyuarakan kebebasan, cinta, dan keadilan.", 2),
    ("Amba", "Laksmi Pamuntjak", "Romansa", "Cinta Amba dan Bhisma diuji oleh jarak, sejarah, serta peristiwa politik.", 3),
    ("The Great Gatsby", "F. Scott Fitzgerald", "Klasik", "Kehidupan mewah Gatsby menyimpan kerinduan dan kritik terhadap masyarakat kelas atas.", 2),
    ("Pride and Prejudice", "Jane Austen", "Romansa", "Elizabeth Bennet menilai ulang prasangka dan harapan pernikahan dalam masyarakat Inggris.", 3),
    ("To Kill a Mockingbird", "Harper Lee", "Klasik", "Scout belajar tentang keberanian dan keadilan ketika ayahnya membela seorang terdakwa.", 3),
    ("1984", "George Orwell", "Distopia", "Winston Smith melawan pengawasan negara dan pengendalian pikiran.", 4),
    ("Brave New World", "Aldous Huxley", "Distopia", "Masyarakat masa depan menjaga stabilitas dengan konsumsi, rekayasa manusia, dan kendali sosial.", 2),
    ("Fahrenheit 451", "Ray Bradbury", "Distopia", "Montag mempertanyakan masyarakat yang membakar buku dan menolak pemikiran kritis.", 3),
    ("Dune", "Frank Herbert", "Sains Fiksi", "Paul Atreides menghadapi politik, ekologi gurun, dan takdir di planet Arrakis.", 2),
    ("The Hobbit", "J.R.R. Tolkien", "Fantasi", "Bilbo Baggins meninggalkan rumah untuk mengikuti petualangan menuju gunung sunyi.", 4),
    ("The Lord of the Rings", "J.R.R. Tolkien", "Fantasi", "Frodo dan para sahabatnya membawa cincin menuju kehancuran demi menyelamatkan dunia.", 2),
    ("Harry Potter dan Batu Bertuah", "J.K. Rowling", "Fantasi", "Harry mengenal dunia sihir dan menemukan persahabatan di Hogwarts.", 4),
    ("The Name of the Wind", "Patrick Rothfuss", "Fantasi", "Kvothe menceritakan perjalanan hidupnya sebagai musisi, penyihir, dan pencari kebenaran.", 2),
    ("Atomic Habits", "James Clear", "Pengembangan Diri", "Panduan membangun kebiasaan kecil yang konsisten melalui perubahan sistem sehari-hari.", 5),
    ("Mindset", "Carol S. Dweck", "Psikologi", "Riset tentang pola pikir tetap dan berkembang dalam belajar serta menghadapi tantangan.", 3),
    ("Thinking, Fast and Slow", "Daniel Kahneman", "Psikologi", "Penjelasan tentang dua sistem berpikir dan bias yang memengaruhi keputusan manusia.", 2),
    ("The Power of Habit", "Charles Duhigg", "Pengembangan Diri", "Kisah dan riset tentang lingkaran kebiasaan pada individu, organisasi, dan masyarakat.", 3),
    ("Quiet", "Susan Cain", "Psikologi", "Kekuatan orang introvert dan kontribusinya dalam budaya yang mengutamakan ekstroversi.", 2),
    ("Sapiens", "Yuval Noah Harari", "Sejarah", "Gambaran sejarah manusia dari revolusi kognitif sampai perkembangan dunia modern.", 4),
    ("Homo Deus", "Yuval Noah Harari", "Sejarah", "Spekulasi tentang masa depan manusia, teknologi, algoritma, dan pencarian makna.", 2),
    ("Guns, Germs, and Steel", "Jared Diamond", "Sejarah", "Penjelasan geografis dan ekologis tentang ketimpangan perkembangan peradaban.", 2),
    ("A Brief History of Time", "Stephen Hawking", "Sains", "Pengantar populer mengenai asal-usul alam semesta, waktu, lubang hitam, dan kosmologi.", 3),
    ("Cosmos", "Carl Sagan", "Sains", "Perjalanan ilmu pengetahuan manusia untuk memahami bumi, kehidupan, dan alam semesta.", 3),
    ("The Selfish Gene", "Richard Dawkins", "Sains", "Perspektif evolusi yang menjelaskan perilaku makhluk hidup dari sudut pandang gen.", 2),
    ("Clean Code", "Robert C. Martin", "Teknologi", "Prinsip praktis menulis kode yang mudah dibaca, diuji, dan dirawat.", 4),
    ("The Pragmatic Programmer", "David Thomas dan Andrew Hunt", "Teknologi", "Kebiasaan dan teknik untuk meningkatkan kualitas proses pengembangan perangkat lunak.", 3),
    ("Designing Data-Intensive Applications", "Martin Kleppmann", "Teknologi", "Konsep arsitektur sistem data, penyimpanan, replikasi, dan pemrosesan terdistribusi.", 2),
    ("Python untuk Analisis Data", "Wes McKinney", "Teknologi", "Panduan pandas dan teknik analisis data menggunakan Python.", 3),
    ("Hands-On Machine Learning", "Aurélien Géron", "Teknologi", "Implementasi pembelajaran mesin dengan contoh praktis dan evaluasi model.", 2),
    ("Laut Bercerita", "Leila S. Chudori", "Sejarah", "Keluarga mencari kabar orang hilang sementara aktivisme dan ingatan terus bertahan.", 3),
    ("Pachinko", "Min Jin Lee", "Sejarah", "Empat generasi keluarga Korea menghadapi identitas, migrasi, dan diskriminasi di Jepang.", 2),
    ("The Kite Runner", "Khaled Hosseini", "Fiksi", "Persahabatan dan penebusan seorang anak Afghanistan dibayangi perubahan sejarah.", 3),
    ("Norwegian Wood", "Haruki Murakami", "Romansa", "Kenangan masa muda dan kehilangan membentuk perjalanan emosional seorang mahasiswa.", 3),
    ("Kafka on the Shore", "Haruki Murakami", "Fantasi", "Dua perjalanan aneh saling berkelindan melalui mimpi, simbol, dan pencarian diri.", 2),
    ("The Alchemist", "Paulo Coelho", "Pengembangan Diri", "Seorang penggembala mengikuti mimpi dan belajar membaca tanda dalam perjalanan hidup.", 4),
    ("Man's Search for Meaning", "Viktor E. Frankl", "Psikologi", "Refleksi tentang makna hidup dan ketahanan manusia dari pengalaman di kamp konsentrasi.", 3),
    ("Educated", "Tara Westover", "Memoar", "Seorang perempuan mengejar pendidikan dan membangun identitas di luar lingkungan masa kecilnya.", 2),
    ("The Design of Everyday Things", "Don Norman", "Teknologi", "Prinsip desain berpusat pada manusia untuk membuat produk lebih mudah dipahami dan digunakan.", 3),
    ("Thinking in Systems", "Donella H. Meadows", "Sains", "Cara memahami hubungan, umpan balik, dan titik ungkit dalam sistem kompleks.", 2),
    ("Factfulness", "Hans Rosling", "Pengembangan Diri", "Data dan cara berpikir untuk memahami dunia tanpa terjebak pada pandangan yang terlalu negatif.", 3),
    ("The Little Prince", "Antoine de Saint-Exupéry", "Klasik", "Percakapan seorang penerbang dengan pangeran kecil tentang persahabatan dan tanggung jawab.", 4),
    ("The Midnight Library", "Matt Haig", "Fiksi", "Nora menemukan perpustakaan ajaib yang berisi berbagai kemungkinan hidupnya.", 3),
    ("The Book Thief", "Markus Zusak", "Sejarah", "Liesel menemukan kekuatan kata-kata di tengah Jerman pada masa Perang Dunia Kedua.", 2),
]

USERS = [
    (1, "Alya Pratama", "alya@example.com", "anggota"),
    (2, "Bagas Saputra", "bagas@example.com", "anggota"),
    (3, "Citra Lestari", "citra@example.com", "anggota"),
    (4, "Dimas Ramadhan", "dimas@example.com", "anggota"),
    (5, "Eka Wulandari", "eka@example.com", "anggota"),
    (6, "Fajar Nugroho", "fajar@example.com", "anggota"),
    (7, "Rifa Aulia", "rifa@example.com", "petugas"),
    (8, "Wildan Hakim", "wildan@example.com", "petugas"),
    (9, "Azrur Maulana", "azrur@example.com", "pengelola"),
    (10, "Mohammad Rosyiqul Faiq", "faiq@example.com", "pengelola"),
]


def seed_database() -> None:
    init_db()
    with get_connection() as connection:
        connection.execute("DELETE FROM borrowings")
        connection.execute("DELETE FROM books")
        connection.execute("DELETE FROM users")
        connection.executemany("INSERT INTO users (id, name, email, role) VALUES (?, ?, ?, ?)", USERS)
        connection.executemany(
            "INSERT INTO books (id, title, author, category, synopsis, stock, total_stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(index, *book, book[4]) for index, book in enumerate(BOOKS, start=1)],
        )
        transactions = []
        for transaction_id in range(1, 81):
            user_id = ((transaction_id * 7) % 6) + 1
            book_id = ((transaction_id * 11) % len(BOOKS)) + 1
            borrowed = date(2025, 1, 1) + timedelta(days=transaction_id * 3)
            returned = borrowed + timedelta(days=7 + transaction_id % 12)
            status = "dikembalikan" if transaction_id % 7 else "dipinjam"
            transactions.append((transaction_id, user_id, book_id, borrowed.isoformat(), None if status == "dipinjam" else returned.isoformat(), status))
        connection.executemany(
            "INSERT INTO borrowings (id, user_id, book_id, borrowed_at, returned_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            transactions,
        )
    print(f"Seed selesai: {len(BOOKS)} buku, {len(USERS)} user, 80 transaksi -> library.db")


if __name__ == "__main__":
    seed_database()
