# Personal Career Workbench & Job Matcher

Aplikasi lokal berbasis Python dan FastAPI untuk mempermudah pencarian lowongan kerja, penilaian kecocokan kualifikasi (rule-based matching), serta pelacakan progres lamaran kerja secara terorganisir.

## Fitur Utama

- **Profil Terpusat & Parsing CV:** Ekstraksi data resume (format PDF atau teks) menjadi data profil terstruktur.
- **Pencarian Lowongan:** Penarikan lowongan dari portal publik dan aggregator, dilengkapi filter deduplikasi otomatis.
- **Evaluasi Kecocokan (Rule-Based):**
  - Pemeriksaan syarat mutlak (*deal-breakers* & bahasa).
  - Pembobotan skor teknis, pengalaman, lokasi kerja, dan preferensi.
  - Identifikasi gap skill untuk persiapan wawancara.
- **Tracker Lamaran (SQLite):** Pencatatan riwayat lamaran, status seleksi (Draft, Submitted, Interview, Offer, Rejected), dan catatan wawancara.
- **Generator Surat Lamaran:** Pembuatan draf surat lamaran profesional secara instan (Bahasa Indonesia & Inggris).
- **Export Data:** Unduh data riwayat lamaran ke format CSV.

## Struktur Direktori

```text
├── app.py                  # Server FastAPI & API endpoints
├── run.py                  # Entry point lokal Uvicorn
├── Procfile                # Konfigurasi deployment cloud
├── requirements.txt        # Dependensi Python
├── test_core.py            # Unit test logika inti
├── static/
│   └── index.html          # Antarmuka web responsif
├── backend/
│   ├── models.py           # Model data Pydantic
│   ├── parser.py           # Ekstraksi dan parsing CV
│   ├── matcher.py          # Logika evaluasi dan scoring kecocokan
│   ├── scraper.py          # Penarikan data lowongan
│   └── db.py               # Operasi database SQLite
├── profile.example.json    # Contoh template profil
└── .gitignore              # Proteksi privasi dan file database lokal
```

## Menjalankan di Lokal

1. **Clone repositori:**
   ```bash
   git clone https://github.com/fattahmaulana/Personal-Career-Workbench-Job-Matcher.git
   cd Personal-Career-Workbench-Job-Matcher
   ```

2. **Buat virtual environment (opsional tapi disarankan):**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. **Install dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Jalankan aplikasi:**
   ```bash
   python run.py
   ```
   Buka browser di `http://127.0.0.1:8000`.

5. **Menjalankan Pengujian (Testing):**
   ```bash
   python test_core.py
   ```

## Lisensi

MIT License.
