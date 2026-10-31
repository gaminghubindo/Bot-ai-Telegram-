# 🤖 Bot Telegram AI Customer Service & Pemesanan UMKM Kuliner

Bot Telegram berbasis kecerdasan buatan (AI) yang dirancang khusus untuk membantu operasional usaha kuliner kecil / UMKM di Indonesia (seperti warung makan, kedai kopi, resto rumahan, catering). 

Bot ini berfungsi sebagai **asisten Customer Service (CS)** yang ramah dan **penerima pesanan otomatis** dengan bahasa Indonesia yang natural, hangat, dan interaktif. Bot dapat langsung dijalankan di laptop atau komputer lokal Anda.

---

## 🌟 Fitur Utama

1. **CS Cerdas Berbasis Data Asli:**
   - Menjawab pertanyaan pelanggan terkait menu, harga, jam buka, alamat warung, area pengantaran, ongkos kirim, dan metode pembayaran berdasarkan file `data/menu.json`.
   - Data `data/menu.json` selalu disisipkan sebagai sumber kebenaran (*single source of truth*) dalam setiap *prompt* ke LLM agar bot tidak pernah mengarang menu atau harga.

2. **Penerimaan Pesanan Lewat Percakapan Alami:**
   - Bot mengumpulkan data secara bertahap dan santai: nama pelanggan, daftar menu & jumlah porsi, metode (antar / ambil sendiri), alamat pengantaran, waktu pengantaran/pengambilan, serta catatan khusus (misal: tingkat kepedasan, es dipisah).

3. **Perhitungan Harga Otomatis & Akurat (Anti Halusinasi):**
   - Sebelum pesanan final, sistem menghitung subtotal, ongkir berdasarkan area, dan grand total menggunakan kode Python murni berdasarkan `data/menu.json` (**BUKAN dihitung oleh LLM**).
   - Menampilkan ringkasan pesanan rapi ke pelanggan dan meminta konfirmasi kata **"ya"**.

4. **Notifikasi Rekap ke Pemilik & Penyimpanan CSV:**
   - Setelah pelanggan mengonfirmasi dengan "ya", bot mengirimkan rekap pesanan ke Telegram pemilik warung (`OWNER_CHAT_ID`) dan mencatatnya ke file `data/orders.csv`.

5. **Penanganan Komplain & Eskalasi Otomatis:**
   - Jika pelanggan komplain, marah, atau meminta bantuan di luar wewenang bot, bot akan merespons dengan sopan dan otomatis meneruskan notifikasi berisi pesan pelanggan ke pemilik.

6. **Dukungan Dual LLM dengan Fallback Otomatis:**
   - **LLM Utama:** Google Gemini (lewat endpoint OpenAI-compatible).
   - **LLM Cadangan:** Groq API. Jika Gemini mengalami gangguan atau *rate limit*, bot otomatis mengalihkan proses ke Groq tanpa mengganggu pelanggan.
   - Jika kedua LLM gagal, bot merespons santai: *"Duh, lagi ada gangguan nih. Coba kirim lagi sebentar ya, atau tunggu dibalas langsung sama pemilik."*

7. **Perintah Cepat:**
   - `/start` : Sapaan ramah dan instruksi awal.
   - `/menu` : Menampilkan daftar menu lengkap beserta harga, ongkir, dan info rekening.
   - `/id` : Menampilkan Chat ID Telegram pengguna (memudahkan pemilik mendapatkan `OWNER_CHAT_ID`).

8. **Indikator Sedang Mengetik (*Typing Indicator*):**
   - Menampilkan status *"typing..."* di Telegram saat bot sedang memproses balasan AI.

---

## 🛠️ Tech Stack

- **Bahasa Pemrograman:** Python 3.10+
- **Library Telegram:** `python-telegram-bot` (versi terbaru, async)
- **Library AI:** `openai` (digunakan sebagai klien OpenAI-compatible untuk Gemini & Groq)
- **Konfigurasi Lingkungan:** `python-dotenv`
- **Penyimpanan:** In-memory untuk riwayat 10 pesan terakhir, CSV untuk rekap pesanan

---

## 📁 Struktur Project

```text
Ai Bot Telegram/
├── data/
│   ├── menu.json             # Data resmi menu, harga, jam buka, ongkir, dan pembayaran
│   └── orders.csv            # Rekap pesanan yang berhasil (dibuat otomatis)
├── prompts/
│   └── system_prompt.txt     # Persona dan system prompt bot AI
├── tests/
│   ├── test_scenarios.py     # Pengujian skenario logika bot
│   └── test_bot_handlers.py  # Pengujian integrasi handler Telegram
├── .env.example              # Template variabel konfigurasi & API key
├── .gitignore                # Berkas pengabaian git (menjaga keamanan API key)
├── llm.py                    # Integrasi LLM & logika fallback Gemini -> Groq
├── main.py                   # Entry point aplikasi bot Telegram
├── memory.py                 # Penyimpanan riwayat chat per user (maks 10 pesan)
├── orders.py                 # Logika pesanan, kalkulasi harga, CSV, dan notifikasi
├── requirements.txt          # Daftar dependensi library Python
└── README.md                 # Dokumentasi panduan lengkap
```

---

## 🚀 Panduan Instalasi & Menjalankan di Laptop

### 1. Prasyarat Sistem
Pastikan laptop Anda sudah terpasang:
- **Python 3.10 atau yang lebih baru** (Cek di terminal: `python --version`)
- **Git** (Cek di terminal: `git --version`)

### 2. Clone atau Buka Folder Project
```bash
git clone https://github.com/gaminghubindo/Bot-ai-Telegram-.git
cd Bot-ai-Telegram-
```
*(Atau buka langsung folder project ini di terminal laptop Anda)*

### 3. Buat dan Aktifkan Virtual Environment (Direkomendasikan)
- **Windows (PowerShell/CMD):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
  *(Catatan: Jika di environment MSYS2/MinGW, gunakan `source venv/bin/activate`)*

- **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 4. Install Dependensi
```bash
pip install -r requirements.txt
```

---

## 🔑 Cara Mendapatkan Token & API Key

### 1. Telegram Bot Token (`TELEGRAM_BOT_TOKEN`)
1. Buka aplikasi Telegram, lalu cari akun resmi **[@BotFather](https://t.me/BotFather)**.
2. Kirim pesan `/newbot`.
3. Masukkan nama bot Anda (contoh: `Warung Bu Sari CS`).
4. Masukkan *username* bot berakhiran `bot` (contoh: `warung_busari_bot`).
5. BotFather akan memberikan **HTTP API Token** (contoh: `7123456789:AAH...`).
6. Salin token tersebut untuk dimasukkan ke file `.env`.

### 2. Google Gemini API Key (`GEMINI_API_KEY`)
1. Buka situs [Google AI Studio](https://aistudio.google.com/).
2. Masuk menggunakan akun Google Anda.
3. Klik tombol **Get API key** di menu sebelah kiri.
4. Klik **Create API key** lalu salin kunci API yang dihasilkan.
5. Google menyediakan kuota gratis (*free tier*) yang sangat cukup untuk penggunaan UMKM.

### 3. Groq API Key (`GROQ_API_KEY`) sebagai LLM Cadangan
1. Buka situs [Groq Console](https://console.groq.com/).
2. Daftar atau login akun.
3. Masuk ke tab **API Keys**, lalu klik **Create API Key**.
4. Beri nama (misal `bot-kuliner-backup`), lalu salin kuncinya.
5. Groq menyediakan akses LLM berkecepatan tinggi gratis yang ideal untuk cadangan.

### 4. Menemukan Chat ID Pemilik (`OWNER_CHAT_ID`)
1. Setelah bot berhasil dijalankan nanti, buka bot Anda di Telegram dari akun pemilik toko.
2. Kirim perintah:
   ```text
   /id
   ```
3. Bot akan membalas dengan menampilkan angka **Chat ID** Anda (contoh: `123456789`).
4. Masukkan angka tersebut ke variabel `OWNER_CHAT_ID` di file `.env`.

---

## ⚙️ Konfigurasi File `.env`

Salin file `.env.example` menjadi `.env`:
- **Windows:**
  ```powershell
  copy .env.example .env
  ```
- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```

Buka file `.env` dengan teks editor (Notepad, VS Code, dll.), lalu isi nilai variabel:

```env
# 1. Token Telegram dari @BotFather
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxx

# 2. Chat ID Telegram Pemilik Toko (didapat dari ketik /id di bot)
OWNER_CHAT_ID=123456789

# 3. Google Gemini (LLM Utama)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-2.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# 4. Groq (LLM Cadangan Otomatis)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

---

## 🏃 Cara Menjalankan Bot

Pastikan virtual environment aktif, lalu jalankan:
```bash
python main.py
```

Jika konfigurasi benar, akan muncul tampilan di terminal:
```text
============================================================
🤖 Memulai Bot Telegram AI Kuliner...
Owner Chat ID: 123456789
Tekan Ctrl+C untuk menghentikan bot.
============================================================
```

Sekarang buka aplikasi Telegram dan mulai chat dengan bot Anda!

---

## 🍽️ Mengganti Data Menu dengan Usaha Anda

Anda dapat langsung mengganti data contoh "Warung Bu Sari" dengan data menu asli warung/restoran Anda di file:
`data/menu.json`

Bagian yang bisa diubah:
- `nama_usaha` : Nama warung/restoran Anda
- `jam_buka` : Jam operasional usaha
- `alamat` : Lokasi warung Anda
- `area_antar` & `ongkir` : Area jangkauan antar dan tarif ongkirnya
- `info_pembayaran` : Nomor rekening BCA/Mandiri/BRI atau catatan QRIS
- `menu` : Daftar menu, harga (dalam angka murni, misal `18000`), dan deskripsinya

---

## 🧪 Menjalankan Pengujian Otomatis (*Unit Tests*)

Project ini dilengkapi dengan pengujian unit otomatis untuk memastikan semua skenario berjalan normal (menu, perhitungan harga, penyimpanan CSV, komplain, fallback LLM, dan memori):

```bash
python -m unittest discover tests
```

Semua 13 skenario uji telah lulus verifikasi (100% OK).

---

## 🔒 Keamanan & Lisensi

- File `.env` dan `data/orders.csv` sudah dimasukkan ke `.gitignore` sehingga tidak akan pernah terunggah ke repositori publik GitHub.
- Jaga selalu kerahasiaan `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, dan `GROQ_API_KEY` Anda.
