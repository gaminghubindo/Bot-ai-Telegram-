"""
orders.py - Logika katalog produk digital, pembuatan antarmuka tombol inline (seperti BerryGrowID),
penghitungan harga, pencatatan pesanan ke CSV, dan notifikasi ke pemilik toko.
"""

import csv
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Path file data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENU_FILE = os.path.join(BASE_DIR, "data", "menu.json")
ORDERS_CSV = os.path.join(BASE_DIR, "data", "orders.csv")
VERIFIED_USERS_FILE = os.path.join(BASE_DIR, "data", "verified_users.json")
FREELANCE_FILE = os.path.join(BASE_DIR, "data", "freelance.json")
FREELANCE_UNLOCKED_FILE = os.path.join(BASE_DIR, "data", "freelance_unlocked.json")


def load_freelance_data() -> dict:
    """Membaca data info lowongan freelance dari data/freelance.json."""
    if not os.path.exists(FREELANCE_FILE):
        return {"biaya_akses": 5000, "biaya_format": "Rp5.000", "daftar_job": []}
    try:
        with open(FREELANCE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"biaya_akses": 5000, "biaya_format": "Rp5.000", "daftar_job": []}


def save_freelance_data(data: dict) -> None:
    """Menyimpan data lowongan freelance ke data/freelance.json."""
    try:
        os.makedirs(os.path.dirname(FREELANCE_FILE), exist_ok=True)
        with open(FREELANCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_unlocked_freelance_users() -> set:
    """Membaca daftar ID pengguna yang sudah membayar & membuka akses info freelance."""
    if not os.path.exists(FREELANCE_UNLOCKED_FILE):
        return set()
    try:
        with open(FREELANCE_UNLOCKED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(str(uid) for uid in data)
    except Exception:
        return set()


def unlock_freelance_user(user_id: int | str) -> None:
    """Membuka akses info freelance untuk user_id tertentu."""
    users = load_unlocked_freelance_users()
    users.add(str(user_id))
    try:
        os.makedirs(os.path.dirname(FREELANCE_UNLOCKED_FILE), exist_ok=True)
        with open(FREELANCE_UNLOCKED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users), f, indent=2)
    except Exception:
        pass


def clear_unlocked_freelance_users() -> None:
    """Menghapus data user unlocked freelance (untuk keperluan testing)."""
    if os.path.exists(FREELANCE_UNLOCKED_FILE):
        try:
            os.remove(FREELANCE_UNLOCKED_FILE)
        except Exception:
            pass


def is_freelance_unlocked(user_id: int | str, owner_id: str = "") -> bool:
    """Memeriksa apakah user sudah membuka akses info freelance."""
    uid = str(user_id)
    if owner_id and uid == str(owner_id):
        return True
    return uid in load_unlocked_freelance_users()


def get_active_freelance_jobs() -> List[dict]:
    """Mengambil daftar job freelance yang statusnya 'aktif'."""
    data = load_freelance_data()
    return [j for j in data.get("daftar_job", []) if j.get("status") == "aktif"]


def load_verified_users() -> set:
    """Membaca daftar ID pengguna yang sudah terverifikasi bergabung di grup."""
    if not os.path.exists(VERIFIED_USERS_FILE):
        return set()
    try:
        with open(VERIFIED_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(str(uid) for uid in data)
    except Exception:
        return set()


def save_verified_user(user_id: int | str) -> None:
    """Menyimpan ID pengguna yang telah bergabung ke file verified_users.json."""
    users = load_verified_users()
    users.add(str(user_id))
    try:
        os.makedirs(os.path.dirname(VERIFIED_USERS_FILE), exist_ok=True)
        with open(VERIFIED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users), f, indent=2)
    except Exception:
        pass


def clear_verified_users() -> None:
    """Menghapus data verified users (untuk keperluan testing)."""
    if os.path.exists(VERIFIED_USERS_FILE):
        try:
            os.remove(VERIFIED_USERS_FILE)
        except Exception:
            pass

# State pesanan sementara dalam memori: {chat_id: order_data}
_pending_orders: Dict[str, dict] = {}


def load_menu() -> dict:
    """Membaca file data/menu.json."""
    if not os.path.exists(MENU_FILE):
        return {}
    try:
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_user_stats(chat_id: int | str) -> Tuple[int, int]:
    """
    Menghitung total belanja (Rp) dan total pesanan yang pernah dibuat oleh user_id dari orders.csv.
    """
    key_id = str(chat_id)
    total_spend = 0
    total_orders = 0

    if os.path.exists(ORDERS_CSV):
        try:
            with open(ORDERS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("customer_id") == key_id:
                        total_orders += 1
                        try:
                            total_spend += int(row.get("total_price", 0))
                        except ValueError:
                            pass
        except Exception:
            pass

    return total_spend, total_orders


def format_rupiah(amount: int) -> str:
    """Format angka integer menjadi format Rupiah Indonesia: Rp20.000"""
    return f"Rp{amount:,}".replace(",", ".")


def get_product_by_id(prod_id: str) -> Optional[dict]:
    """Mencari objek produk berdasarkan product ID."""
    menu_data = load_menu()
    for p in menu_data.get("produk", []):
        if p.get("id") == prod_id:
            return p
    return None


def get_variant_by_id(product: dict, var_id: str) -> Optional[dict]:
    """Mencari objek varian berdasarkan variant ID dalam suatu produk."""
    for v in product.get("varian", []):
        if v.get("id") == var_id:
            return v
    return None


def get_group_info() -> dict:
    """Mendapatkan link dan info grup Elva Group."""
    menu_data = load_menu()
    grp = menu_data.get("elva_group", {})
    env_link = os.getenv("ELVA_GROUP_LINK", "").strip()
    link = env_link if env_link else grp.get("url", "https://t.me/+elvagroup")
    return {
        "nama": grp.get("nama", "Elva Group"),
        "url": link,
        "deskripsi": grp.get("deskripsi", "Grup resmi Elva Tech untuk update restock, notifikasi saat stok reset, promo kilat, dan diskusi komunitas pelanggan.")
    }


def build_group_keyboard() -> Tuple[str, InlineKeyboardMarkup]:
    """Membuat tampilan informasi & tautan bergabung ke Elva Group."""
    grp = get_group_info()
    text = (
        f"📢 *{grp['nama'].upper()} — PUSAT INFORMASI & RESTOCK*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Selamat datang di grup resmi *Elva Tech*! 🚀\n\n"
        f"Grup ini dibuat khusus untuk pelanggan agar selalu tahu:\n"
        f"🔔 *Notifikasi Reset Stok*: Info tercepat saat akun/layanan ready kembali!\n"
        f"⚡ *Flash Sale & Diskon Khusus*: Promo eksklusif khusus member grup.\n"
        f"🛠️ *Update Layanan & Fitur*: Pembaruan katalog & produk digital baru.\n"
        f"💬 *Diskusi Komunitas*: Berbagi tips dan konsultasi seputar tools AI & digital.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 *Klik tombol di bawah untuk bergabung ke Elva Group sekarang:* 👇"
    )

    keyboard = [
        [
            InlineKeyboardButton("🚀 Gabung ke Elva Group Sekarang", url=grp["url"])
        ],
        [
            InlineKeyboardButton("🪙 Katalog Produk", callback_data="view_catalog"),
            InlineKeyboardButton("◀️ Kembali ke Menu Utama", callback_data="menu_main")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


# ==========================================
# PEMBUATAN INLINE KEYBOARD (UI SEPERTI BerryGrowID)
# ==========================================

def build_gatekeeper_keyboard(user_info: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan Gatekeeper / Akses Terkunci.
    Pengguna diwajibkan bergabung ke Elva Group sebelum bisa mengakses bot.
    """
    grp = get_group_info()
    full_name = user_info.get("full_name", "Pelanggan")

    text = (
        f"🔒 *AKSES TERKUNCI — SILAKAN GABUNG ELVA GROUP DAHULU*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Halo kak *{full_name}*! 👋\n\n"
        f"Untuk mengakses katalog produk *Elva Tech* dan konsultasi dengan asisten AI, "
        f"Anda diwajibkan bergabung ke grup resmi kami terlebih dahulu.\n\n"
        f"📢 *Keuntungan Bergabung ke {grp['nama']}:*\n"
        f"🔔 *Info Reset Stok*: Notifikasi instan saat stok akun ready kembali!\n"
        f"⚡ *Flash Sale*: Diskon dan harga khusus member grup.\n"
        f"💡 *Update & Bantuan*: Informasi tips dan konsultasi AI.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 *3 Langkah Cepat untuk Membuka Akses:*\n"
        f"1. Klik tombol *[ 📢 Gabung Elva Group ]* di bawah.\n"
        f"2. Tekan tombol *Join / Gabung* di grup Telegram.\n"
        f"3. Kembali ke chat ini lalu klik tombol *[ ✅ Saya Sudah Bergabung ]*."
    )

    keyboard = [
        [
            InlineKeyboardButton("📢 Gabung Elva Group (Wajib)", url=grp["url"])
        ],
        [
            InlineKeyboardButton("✅ Saya Sudah Bergabung", callback_data="check_joined")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


def build_main_dashboard(chat_id: int | str, user_info: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan Dashboard Akun & Ringkasan mirip dengan referensi BerryGrowID.
    """
    menu_data = load_menu()
    nama_usaha = menu_data.get("nama_usaha", "Elva Tech")
    username_str = f"@{user_info.get('username')}" if user_info.get("username") else "-"
    full_name = user_info.get("full_name", "Pengguna")

    total_spend, order_count = get_user_stats(chat_id)
    spend_str = format_rupiah(total_spend)

    text = (
        f"👤 *ACCOUNT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪪 *User ID:* `{chat_id}`\n"
        f"✈️ *Username:* {username_str}\n"
        f"⭐ *Status:* Pelanggan Terdaftar\n\n"
        f"📊 *RINGKASAN BELANJA*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 *Total Belanja:* {spend_str}\n"
        f"📦 *Total Order:* {order_count} pesanan\n\n"
        f"✨ *Pilih menu di bawah untuk mulai berbelanja atau bertanya:*"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔥 GEMINI PRO & AI SPECIAL", callback_data="prod:google_gemini_pro")
        ],
        [
            InlineKeyboardButton("🪙 Katalog Produk", callback_data="view_catalog"),
            InlineKeyboardButton("🛠️ Layanan Jasa", callback_data="view_jasa")
        ],
        [
            InlineKeyboardButton("💼 Info Freelance (Rp5k)", callback_data="freelance_preview"),
            InlineKeyboardButton("📢 Elva Group (Info Stok)", callback_data="view_group")
        ],
        [
            InlineKeyboardButton("📦 Pesanan Saya", callback_data="my_orders"),
            InlineKeyboardButton("💳 Info Pembayaran", callback_data="payment_info")
        ],
        [
            InlineKeyboardButton("👤 Profil Akun", callback_data="my_profile"),
            InlineKeyboardButton("❗ Bantuan & Garansi", callback_data="help_info")
        ],
        [
            InlineKeyboardButton("👨‍💼 Hubungi Admin (@Carlendra)", url="https://t.me/Carlendra")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


def build_freelance_preview_keyboard(user_id: int | str, owner_id: str = "") -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan preview Info Freelance dengan proteksi 'Biar Tidak Tergocek'.
    """
    if is_freelance_unlocked(user_id, owner_id):
        return build_freelance_unlocked_keyboard()

    active_jobs = get_active_freelance_jobs()
    fl_data = load_freelance_data()
    fee_str = fl_data.get("biaya_format", "Rp5.000")

    # KASUS 1: JOB KOSONG (BIAR TIDAK TERGOCEK)
    if not active_jobs:
        text = (
            "💼 *INFORMASI LOWONGAN FREELANCE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *Status Ketersediaan:* 🔴 *SEDANG KOSONG (0 Job)*\n\n"
            "⚠️ *Jaminan Anti-Tergocek:*\n"
            "Saat ini belum ada info job freelance baru yang aktif. "
            "Tombol pembayaran sengaja kami *NONAKTIFKAN* agar saldo kakak aman dan tidak rugi!\n\n"
            "🔔 _Silakan pantau terus Elva Group. Kami akan segera umumkan begitu ada proyek freelance baru yang siap dikerjakan._"
        )
        grp = get_group_info()
        keyboard = [
            [
                InlineKeyboardButton("📢 Pantau di Elva Group", url=grp["url"])
            ],
            [
                InlineKeyboardButton("🔄 Refresh Status", callback_data="freelance_preview"),
                InlineKeyboardButton("◀️ Kembali ke Menu", callback_data="menu_main")
            ]
        ]
        return text, InlineKeyboardMarkup(keyboard)

    # KASUS 2: ADA JOB AKTIF (TAMPILKAN TEASER & TOMBOL BAYAR RP5.000)
    lines = [
        "💼 *INFORMASI LOWONGAN FREELANCE*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 *Status Ketersediaan:* 🟢 *TERSEDIA {len(active_jobs)} JOB AKTIF!*",
        "Update Terkini: Hari Ini ✅\n",
        "📋 *Preview Proyek yang Sedang Buka:*"
    ]

    for idx, j in enumerate(active_jobs, 1):
        judul = j.get("judul", "Job Freelance")
        kat = j.get("kategori", "-")
        budget = j.get("budget", "-")
        deadline = j.get("deadline", "-")
        teaser = j.get("teaser", "-")
        lines.append(f"*{idx}. {judul}*")
        lines.append(f"   • Kategori: _{kat}_")
        lines.append(f"   • Fee Proyek: *{budget}*")
        lines.append(f"   • Estimasi Waktu: {deadline}")
        lines.append(f"   • Ringkasan: _{teaser}_\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔒 *Detail Rahasia Terkunci:*")
    lines.append("• Nomor WhatsApp & Akun Telegram Klien Langsung")
    lines.append("• Link Dokumen Brief & Aset Proyek")
    lines.append("• Rekomendasi Format Penawaran Cepat Diterima\n")
    lines.append(f"💰 *Biaya Akses Penuh:* Hanya *{fee_str}* (Sekali Bayar)")
    lines.append("_Dapatkan kontak langsung klien sekarang sebelum slot diambil freelancer lain!_")

    keyboard = [
        [
            InlineKeyboardButton(f"📱 Bayar {fee_str} via QR Code GoPay / QRIS", callback_data="fl_pay:qris")
        ],
        [
            InlineKeyboardButton("🏦 Transfer Bank BCA", callback_data="fl_pay:bca"),
            InlineKeyboardButton("💳 DANA / OVO / GoPay", callback_data="fl_pay:ewallet")
        ],
        [
            InlineKeyboardButton("◀️ Kembali ke Menu Utama", callback_data="menu_main")
        ]
    ]

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_freelance_unlocked_keyboard() -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan info freelance LENGKAP setelah pengguna membayar Rp5.000.
    """
    active_jobs = get_active_freelance_jobs()
    if not active_jobs:
        text = (
            "🎉 *AKSES FREELANCE ANDA AKTIF (VIP)*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Saat ini semua slot proyek sebelumnya telah diambil / selesai. "
            "Status Anda tetap VIP dan akan otomatis melihat kontak proyek berikutnya tanpa perlu bayar lagi!\n\n"
            "🔔 _Pantau terus update di sini atau Elva Group ya kak!_"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="freelance_preview")],
            [InlineKeyboardButton("◀️ Menu Utama", callback_data="menu_main")]
        ]
        return text, InlineKeyboardMarkup(keyboard)

    lines = [
        "🔓 *AKSES LENGKAP INFO FREELANCER (VIP)*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "Selamat! Akses Anda telah aktif. Berikut kontak langsung klien & brief proyek:\n"
    ]

    for idx, j in enumerate(active_jobs, 1):
        judul = j.get("judul", "Job Freelance")
        kat = j.get("kategori", "-")
        budget = j.get("budget", "-")
        deadline = j.get("deadline", "-")
        detail = j.get("detail_rahasia", "-")
        lines.append(f"📌 *{idx}. {judul.upper()}*")
        lines.append(f"• Kategori: *{kat}*")
        lines.append(f"• Budget Fee: *{budget}*")
        lines.append(f"• Waktu Pengerjaan: {deadline}\n")
        lines.append(f"📝 *Detail Brief & Kontak Klien:*\n{detail}\n")
        lines.append("──────────────────────\n")

    lines.append("💡 *Tips Melamar:*")
    lines.append("Hubungi klien dengan sopan, perkenalkan nama dan kirimkan portofolio terbaik Anda agar peluang closing lebih tinggi! Semoga sukses ya kak! 🚀")

    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh Info", callback_data="freelance_preview")
        ],
        [
            InlineKeyboardButton("💬 Butuh Bantuan? Hubungi Admin", url="https://t.me/Carlendra")
        ],
        [
            InlineKeyboardButton("◀️ Kembali ke Menu Utama", callback_data="menu_main")
        ]
    ]

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_freelance_payment_instruction(method_code: str, chat_id: int | str, user_info: dict) -> Tuple[str, InlineKeyboardMarkup, str]:
    """
    Membuat instruksi pembayaran Rp5.000 untuk membuka Info Freelance.
    """
    menu_data = load_menu()
    info_pay = menu_data.get("info_pembayaran", {})
    order_id = f"ORD-FL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    total_str = "Rp5.000"

    if method_code in ["qris", "gopay"]:
        nama_metode = "QR Code GoPay / QRIS"
        detail_rekening = (
            "📱 *Metode:* QR Code GoPay / QRIS\n"
            "Silakan scan foto *QR Code GoPay* di atas menggunakan GoPay/Gojek, BCA, DANA, OVO, atau ShopeePay."
        )
    elif method_code == "bca":
        nama_metode = "Bank BCA"
        detail_rekening = (
            "🏦 *Bank:* BCA\n"
            f"• *Rekening:* `{info_pay.get('bank', '1234567890 a/n Elva Tech')}`"
        )
    else:
        nama_metode = "E-Wallet (DANA/OVO/GoPay)"
        detail_rekening = (
            "💳 *E-Wallet:* DANA / OVO / GoPay\n"
            f"• *Nomor:* `{info_pay.get('ewallet', '081234567890 a/n Elva Tech')}`"
        )

    text = (
        f"✅ *PEMESANAN AKSES INFO FREELANCE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 *No. Pesanan:* `{order_id}`\n"
        f"💼 *Layanan:* Akses Kontak & Brief Lowongan Freelance\n"
        f"💰 *TOTAL TRANSFER:* *{total_str}* (Tepat)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Tujuan Pembayaran:*\n"
        f"{detail_rekening}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📸 *LANGKAH CEPAT AKTIVASI:*\n"
        f"1. Transfer *{total_str}* ke tujuan di atas.\n"
        f"2. Kirimkan *FOTO BUKTI TRANSFER* ke chat bot ini.\n"
        f"3. Admin akan langsung memverifikasi atau ketik `/freelance` setelah disetujui.\n\n"
        f"Terima kasih! Semoga berkah dan proyeknya tembus ya kak! 😊"
    )

    # Catat order ke CSV
    order_data = {
        "nama": user_info.get("full_name") or f"User {chat_id}",
        "metode": nama_metode,
        "alamat": "Akses Digital (Info Freelance)",
        "waktu": "Instan",
        "catatan": "Akses Info Freelancer Rp5.000",
        "items": [{
            "nama": "Akses Info Freelancer",
            "qty": 1,
            "harga_satuan": 5000,
            "subtotal": 5000,
            "catatan": "-"
        }],
        "total_harga": 5000
    }
    save_order_to_csv(order_data, chat_id, order_id, user_info)

    # Format rekap untuk owner
    username = f"@{user_info.get('username')}" if user_info.get('username') else "-"
    cust_name = user_info.get('full_name') or f"User {chat_id}"
    owner_msg = (
        "💼 *PESANAN AKSES INFO FREELANCE BARU (Rp5.000)!*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 No. Pesanan: `{order_id}`\n"
        f"👤 Pelanggan: *{cust_name}* ({username})\n"
        f"🆔 Chat ID: `{chat_id}`\n"
        f"💰 Total: *{total_str}* ({nama_metode})\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *Perintah Instan Pemilik:*\n"
        f"Ketik `/unlock {chat_id}` untuk langsung membuka akses pelanggan ini setelah mengecek mutasi pembayaran."
    )

    keyboard = [
        [
            InlineKeyboardButton("📸 Cara Kirim Bukti", callback_data="send_proof_hint"),
            InlineKeyboardButton("💬 Hubungi Admin", url="https://t.me/Carlendra")
        ],
        [
            InlineKeyboardButton("◀️ Kembali ke Menu Utama", callback_data="menu_main")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard), owner_msg


def build_jasa_keyboard() -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan daftar layanan jasa (Landing Page, Desain PPT/Canva, 3D Modeling).
    """
    menu_data = load_menu()
    jasa_data = menu_data.get("layanan_jasa", {})
    lynk_url = jasa_data.get("lynk_url", "https://lynk.id/nellionel")
    tagline = jasa_data.get("tagline", "")
    daftar = jasa_data.get("daftar_jasa", [])

    lines = [
        "🛠️ *LAYANAN JASA PROFESIONAL*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"_{tagline}_\n",
        "🌐 *Website Resmi Lynk.id:*",
        f"{lynk_url}\n",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📌 *Daftar Layanan Jasa Kami:*\n"
    ]

    for j in daftar:
        icon = j.get("icon", "💼")
        nama = j.get("nama")
        harga = j.get("harga_format")
        desc = j.get("deskripsi")
        lines.append(f"{icon} *{nama}*")
        lines.append(f"   • Tarif: *{harga}*")
        lines.append(f"   • _{desc}_\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💬 *KONSULTASI & TANYA LEBIH LANJUT:*")
    lines.append("Untuk diskusi brief, konsultasi kebutuhan proyek, atau tanya-tanya lebih lanjut seputar jasa, silakan hubungi akun Telegram: *@Carlendra* 😊")

    keyboard = [
        [
            InlineKeyboardButton("🌐 Detail Landing Page", callback_data="jasa_detail:jasa_landing_page"),
            InlineKeyboardButton("🎨 Detail Desain PPT", callback_data="jasa_detail:jasa_desain_ppt")
        ],
        [
            InlineKeyboardButton("🧊 Detail 3D Modeling", callback_data="jasa_detail:jasa_3d_modeling")
        ],
        [
            InlineKeyboardButton("🔗 Buka Website Lynk.id", url=lynk_url),
            InlineKeyboardButton("💬 Chat Telegram @Carlendra", url="https://t.me/Carlendra")
        ],
        [
            InlineKeyboardButton("◀️ Kembali ke Menu Utama", callback_data="menu_main")
        ]
    ]

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_jasa_detail_keyboard(jasa_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan detail spesifik dari salah satu layanan jasa.
    """
    menu_data = load_menu()
    jasa_data = menu_data.get("layanan_jasa", {})
    lynk_url = jasa_data.get("lynk_url", "https://lynk.id/nellionel")
    daftar = jasa_data.get("daftar_jasa", [])

    selected = None
    for j in daftar:
        if j.get("id") == jasa_id:
            selected = j
            break

    if not selected:
        return "Layanan tidak ditemukan.", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data="view_jasa")]])

    icon = selected.get("icon", "💼")
    nama = selected.get("nama")
    harga = selected.get("harga_format")
    desc = selected.get("deskripsi")
    link = selected.get("link_lynk", lynk_url)

    text = (
        f"{icon} *{nama.upper()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Tarif:* *{harga}*\n\n"
        f"📝 *Deskripsi Layanan:*\n"
        f"{desc}\n\n"
        f"🌐 *Pemesanan Langsung di Lynk.id:*\n"
        f"{link}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 *Ingin bertanya atau konsultasi lebih lanjut?*\n"
        f"Silakan langsung hubungi akun Telegram: *@Carlendra*"
    )

    keyboard = [
        [
            InlineKeyboardButton("🛒 Order via Lynk.id", url=link),
            InlineKeyboardButton("💬 Konsultasi @Carlendra", url="https://t.me/Carlendra")
        ],
        [
            InlineKeyboardButton("◀️ Kembali ke Menu Jasa", callback_data="view_jasa")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


def build_catalog_keyboard() -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan grid daftar produk (Screen 2 referensi).
    """
    menu_data = load_menu()
    products = menu_data.get("produk", [])

    text = (
        "💎 *PRODUK TERSEDIA*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Pilih aplikasi atau produk digital yang Anda butuhkan di bawah ini:\n\n"
        "_Tip: Anda juga bisa langsung chat menanyakan produk apa saja ke bot AI kami!_"
    )

    keyboard = []
    row = []

    for idx, p in enumerate(products):
        icon = p.get("icon", "📦")
        name = p.get("nama", "Produk")
        # Buat label ringkas untuk tombol
        btn_label = f"{icon} {name}"
        row.append(InlineKeyboardButton(btn_label, callback_data=f"prod:{p['id']}"))

        # 2 tombol per baris agar rapi di layar HP
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Tombol kembali ke menu utama
    keyboard.append([InlineKeyboardButton("◀️ Kembali ke Menu Utama", callback_data="menu_main")])

    return text, InlineKeyboardMarkup(keyboard)


def build_product_variants_keyboard(prod_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan pilihan varian & harga produk (Screen 3 referensi).
    """
    product = get_product_by_id(prod_id)
    if not product:
        return "Produk tidak ditemukan.", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data="view_catalog")]])

    icon = product.get("icon", "📦")
    nama = product.get("nama", "Produk")
    deskripsi = product.get("deskripsi", "-")
    menu_data = load_menu()
    syarat = menu_data.get("syarat_ketentuan", "Harap patuhi syarat & garansi yang berlaku.")

    text = (
        f"{icon} *{nama.upper()} — PILIHAN VARIAN*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 *Pilih varian / durasi yang ingin dibeli:*\n\n"
        f"_{deskripsi}_\n\n"
        f"⚠️ *Syarat & Ketentuan:*\n"
        f"_{syarat}_"
    )

    keyboard = []
    for v in product.get("varian", []):
        var_name = v.get("nama")
        harga_str = format_rupiah(v.get("harga", 0))
        stok = v.get("stok", 0)

        if stok > 0:
            label = f"🟢 {var_name} · {harga_str} [{stok}]"
            callback = f"var:{prod_id}:{v['id']}"
        else:
            label = f"🔴 {var_name} · {harga_str} [Habis]"
            callback = f"var_empty:{prod_id}:{v['id']}"

        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    # Cek apakah ada varian yang stoknya habis
    has_empty = any(v.get("stok", 0) <= 0 for v in product.get("varian", []))

    # Tombol refresh & kembali
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"prod:{prod_id}"),
        InlineKeyboardButton("◀️ Kembali", callback_data="view_catalog")
    ])

    if has_empty:
        grp = get_group_info()
        keyboard.append([
            InlineKeyboardButton("📢 Gabung Elva Group (Info Restock)", url=grp["url"])
        ])

    return text, InlineKeyboardMarkup(keyboard)


def build_quantity_keyboard(prod_id: str, var_id: str) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan numpad pilihan jumlah beli 1-10 dengan tombol beli cepat 1 item (Screen 4 referensi).
    """
    product = get_product_by_id(prod_id)
    if not product:
        return "Produk tidak ditemukan.", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data="view_catalog")]])

    variant = get_variant_by_id(product, var_id)
    if not variant:
        return "Varian tidak ditemukan.", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data=f"prod:{prod_id}")]])

    var_name = variant.get("nama")
    harga_str = format_rupiah(variant.get("harga", 0))
    stok = variant.get("stok", 0)

    text = (
        f"📦 *PILIH JUMLAH PESANAN*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Berapa *{var_name}* yang ingin Anda pesan?\n\n"
        f"🪙 *Harga:* {harga_str} / item\n"
        f"📦 *Stok tersedia:* {stok}\n\n"
        f"💡 _Pilih jumlah di bawah atau klik Beli Langsung 1 Item:_"
    )

    keyboard = [
        [
            InlineKeyboardButton("⚡ Beli Langsung (1 Item) 💳", callback_data=f"qty:{prod_id}:{var_id}:1")
        ],
        [
            InlineKeyboardButton("1", callback_data=f"qty:{prod_id}:{var_id}:1"),
            InlineKeyboardButton("2", callback_data=f"qty:{prod_id}:{var_id}:2"),
            InlineKeyboardButton("3", callback_data=f"qty:{prod_id}:{var_id}:3"),
            InlineKeyboardButton("4", callback_data=f"qty:{prod_id}:{var_id}:4"),
            InlineKeyboardButton("5", callback_data=f"qty:{prod_id}:{var_id}:5"),
        ],
        [
            InlineKeyboardButton("6", callback_data=f"qty:{prod_id}:{var_id}:6"),
            InlineKeyboardButton("7", callback_data=f"qty:{prod_id}:{var_id}:7"),
            InlineKeyboardButton("8", callback_data=f"qty:{prod_id}:{var_id}:8"),
            InlineKeyboardButton("9", callback_data=f"qty:{prod_id}:{var_id}:9"),
            InlineKeyboardButton("10", callback_data=f"qty:{prod_id}:{var_id}:10"),
        ],
        [
            InlineKeyboardButton("◀️ Kembali", callback_data=f"prod:{prod_id}")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


def build_checkout_keyboard(prod_id: str, var_id: str, qty: int) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan detail pesanan dengan Stepper Interaktif [➖] [📦 X Item] [➕]
    dan tombol metode pembayaran (Screen 5 referensi).
    """
    product = get_product_by_id(prod_id)
    if not product:
        return "Produk tidak ditemukan.", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data="view_catalog")]])

    variant = get_variant_by_id(product, var_id)
    if not variant:
        return "Varian tidak ditemukan.", InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data=f"prod:{prod_id}")]])

    var_name = variant.get("nama")
    harga_satuan = variant.get("harga", 0)
    stok = variant.get("stok", 10)
    total_harga = harga_satuan * qty
    total_str = format_rupiah(total_harga)

    text = (
        f"🛍️ *DETAIL PESANAN*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Produk:* {var_name}\n"
        f"🔢 *Jumlah:* {qty} item\n"
        f"💰 *Total Bayar:* *{total_str}* ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ _Gunakan tombol ➖ dan ➕ di bawah untuk ubah jumlah secara langsung._\n\n"
        f"Silakan pilih metode pembayaran di bawah ini: 💳"
    )

    prev_qty = max(1, qty - 1)
    next_qty = min(stok, qty + 1)

    keyboard = [
        [
            InlineKeyboardButton("➖", callback_data=f"step:{prod_id}:{var_id}:{prev_qty}"),
            InlineKeyboardButton(f"📦 {qty} Item ({total_str})", callback_data=f"step_info:{prod_id}:{var_id}:{qty}"),
            InlineKeyboardButton("➕", callback_data=f"step:{prod_id}:{var_id}:{next_qty}")
        ],
        [
            InlineKeyboardButton("📱 QRIS (Semua E-Wallet & Bank)", callback_data=f"pay:{prod_id}:{var_id}:{qty}:qris")
        ],
        [
            InlineKeyboardButton("🏦 Transfer Bank BCA", callback_data=f"pay:{prod_id}:{var_id}:{qty}:bca")
        ],
        [
            InlineKeyboardButton("💳 DANA / OVO / GoPay", callback_data=f"pay:{prod_id}:{var_id}:{qty}:ewallet")
        ],
        [
            InlineKeyboardButton("◀️ Ganti Varian", callback_data=f"prod:{prod_id}"),
            InlineKeyboardButton("🏠 Menu Utama", callback_data="menu_main")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


def build_payment_instruction(prod_id: str, var_id: str, qty: int, method_code: str, chat_id: int | str, user_info: dict) -> Tuple[str, InlineKeyboardMarkup, str]:
    """
    Membuat rincian instruksi pembayaran lengkap, menyimpan pesanan ke CSV, dan mengirim notifikasi.
    """
    product = get_product_by_id(prod_id)
    variant = get_variant_by_id(product, var_id)
    menu_data = load_menu()
    info_pay = menu_data.get("info_pembayaran", {})

    var_name = variant.get("nama") if variant else "Item Digital"
    harga_satuan = variant.get("harga", 0) if variant else 0
    total_harga = harga_satuan * qty
    total_str = format_rupiah(total_harga)

    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if method_code == "qris":
        nama_metode = "QRIS Dinamis"
        detail_rekening = (
            "📱 *Metode:* QRIS (Gopay, OVO, Dana, ShopeePay, BCA, Livin, dll.)\n"
            "Silakan hubungi admin atau ketik di chat untuk menerima barcode QRIS, atau bayar via E-Wallet di bawah."
        )
    elif method_code == "bca":
        nama_metode = "Bank BCA"
        detail_rekening = (
            "🏦 *Bank:* BCA\n"
            f"• *Rekening:* `{info_pay.get('bank', '1234567890 a/n Toko Digital')}`"
        )
    else:
        nama_metode = "E-Wallet (DANA/OVO/GoPay)"
        detail_rekening = (
            "💳 *E-Wallet:* DANA / OVO / GoPay\n"
            f"• *Nomor:* `{info_pay.get('ewallet', '081234567890 a/n Toko Digital')}`"
        )

    text = (
        f"✅ *PESANAN BERHASIL DIBUAT!*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 *No. Pesanan:* `{order_id}`\n"
        f"📦 *Produk:* {var_name}\n"
        f"🖊️ *Jumlah:* {qty} porsi/akun\n"
        f"💰 *TOTAL TRANSFER:* *{total_str}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Tujuan Pembayaran:*\n"
        f"{detail_rekening}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📸 *LANGKAH SELANJUTNYA:*\n"
        f"1. Lakukan pembayaran sejumlah *{total_str}* tepat.\n"
        f"2. Kirimkan *FOTO BUKTI TRANSFER* langsung ke chat bot ini.\n"
        f"3. Admin toko akan langsung memverifikasi dan mengirimkan akun/akses pesanan Anda.\n\n"
        f"Terima kasih telah berbelanja! 😊"
    )

    # Catat ke CSV
    order_data = {
        "nama": user_info.get("full_name") or f"User {chat_id}",
        "metode": nama_metode,
        "alamat": "Pengiriman Digital (Chat Telegram)",
        "waktu": "Instan",
        "catatan": "-",
        "items": [{
            "nama": var_name,
            "qty": qty,
            "harga_satuan": harga_satuan,
            "subtotal": total_harga,
            "catatan": "-"
        }],
        "total_harga": total_harga
    }
    save_order_to_csv(order_data, chat_id, order_id, user_info)

    # Format pesan rekap untuk pemilik
    owner_msg, _ = format_owner_order_recap(order_data, chat_id, user_info, order_id=order_id)

    keyboard = [
        [
            InlineKeyboardButton("📸 Cara Kirim Bukti", callback_data="send_proof_hint"),
            InlineKeyboardButton("💬 Hubungi Admin", url="https://t.me/Carlendra")
        ],
        [
            InlineKeyboardButton("◀️ Kembali ke Menu Utama", callback_data="menu_main")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard), owner_msg


def format_owner_order_recap(order: dict, chat_id: int | str, user_info: dict, order_id: Optional[str] = None) -> Tuple[str, str]:
    """Menghasilkan rekap notifikasi pesanan ke OWNER_CHAT_ID."""
    if not order_id:
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M WIB")
    username = f"@{user_info.get('username')}" if user_info.get("username") else "-"
    customer_fullname = user_info.get("full_name") or order.get("nama")

    lines = [
        "🔔 *PESANAN BARU MASUK!*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 No. Pesanan: `{order_id}`",
        f"📅 Waktu: {timestamp_str}",
        f"👤 Nama: *{order['nama']}* ({customer_fullname})",
        f"💬 Telegram: {username} (ID: `{chat_id}`)",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📦 *Daftar Pesanan:*"
    ]

    for it in order.get("items", []):
        nama = it.get("nama")
        qty = it.get("qty", 1)
        sub = format_rupiah(it.get("subtotal", 0))
        lines.append(f"• {qty}x *{nama}* = {sub}")

    lines.append("──────────────────────")
    lines.append(f"Metode Pembayaran: *{order.get('metode', '-')}*")
    lines.append(f"💰 *TOTAL BAYAR: {format_rupiah(order.get('total_harga', 0))}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚡ Status: *Menunggu Bukti Transfer dari Pelanggan*")

    return "\n".join(lines), order_id


def format_owner_escalation(customer_user: dict, reason: str, customer_message: str) -> str:
    """Format notifikasi komplain / eskalasi pelanggan untuk pemilik toko."""
    username = f"@{customer_user.get('username')}" if customer_user.get("username") else "-"
    fullname = customer_user.get("full_name", "Pelanggan")
    chat_id = customer_user.get("chat_id", "-")
    timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M WIB")

    lines = [
        "🚨 *NOTIFIKASI CS / KOMPLAIN PELANGGAN*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 Waktu: {timestamp_str}",
        f"👤 Dari: *{fullname}* ({username})",
        f"🆔 Chat ID: `{chat_id}`",
        f"📌 Kategori/Alasan: {reason}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "💬 *Pesan Terakhir Pelanggan:*",
        f"\"{customer_message}\"",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "⚠️ _Silakan cek atau balas langsung pelanggan ini jika diperlukan._"
    ]
    return "\n".join(lines)


def save_order_to_csv(order: dict, chat_id: int | str, order_id: str, user_info: dict) -> None:
    """Menyimpan pesanan ke data/orders.csv."""
    os.makedirs(os.path.dirname(ORDERS_CSV), exist_ok=True)
    file_exists = os.path.exists(ORDERS_CSV)

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items_summary = "; ".join([
        f"{it['qty']}x {it['nama']}" for it in order.get("items", [])
    ])

    fieldnames = [
        "order_id",
        "timestamp",
        "customer_name",
        "customer_id",
        "items",
        "method",
        "address",
        "delivery_time",
        "notes",
        "total_price",
        "status"
    ]

    with open(ORDERS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "order_id": order_id,
            "timestamp": timestamp_str,
            "customer_name": order.get("nama") or user_info.get("full_name"),
            "customer_id": str(chat_id),
            "items": items_summary,
            "method": order.get("metode", "-"),
            "address": order.get("alamat", "-"),
            "delivery_time": order.get("waktu", "-"),
            "notes": order.get("catatan", "-"),
            "total_price": order.get("total_harga", 0),
            "status": "Menunggu Verifikasi"
        })


def get_menu_display_text() -> str:
    """Fallback teks daftar produk jika dipanggil sebagai teks biasa."""
    menu_data = load_menu()
    nama = menu_data.get("nama_usaha", "Digital Store")
    lines = [f"💎 *KATALOG {nama.upper()}*", ""]
    for p in menu_data.get("produk", []):
        icon = p.get("icon", "📦")
        nama_p = p.get("nama")
        lines.append(f"{icon} *{nama_p}*")
        for v in p.get("varian", []):
            lines.append(f"   • {v['nama']} — {format_rupiah(v['harga'])} [Stok: {v['stok']}]")
        lines.append("")
    lines.append("Gunakan tombol interaktif di bawah atau ketik langsung pesan Anda! 😊")
    return "\n".join(lines)


# State manajemen pending order berbasis percakapan teks
def set_pending_order(chat_id: int | str, order_data: dict) -> None:
    _pending_orders[str(chat_id)] = order_data


def get_pending_order(chat_id: int | str) -> Optional[dict]:
    return _pending_orders.get(str(chat_id))


def clear_pending_order(chat_id: int | str) -> None:
    key = str(chat_id)
    if key in _pending_orders:
        del _pending_orders[key]


# ==========================================
# NOTIFIKASI NEW PURCHASE & TOP BUYER GRUP
# ==========================================

def mask_customer_id(customer_id: int | str) -> str:
    """Menyamarkan ID pengguna demi privasi, format persis seperti di grup: 651*****99."""
    s = str(customer_id).strip()
    if len(s) <= 4:
        return s[:1] + "***" + s[-1:]
    return s[:3] + "*****" + s[-2:]


def mask_order_id(order_id: str) -> str:
    """Menyamarkan No. Order, format persis seperti: Elva-26****-0109."""
    s = str(order_id).strip()
    if s.startswith("ORD-FL-"):
        rest = s[7:]
        return f"Elva-FL-{rest[:2]}****-{rest[-4:]}"
    elif s.startswith("ORD-"):
        rest = s[4:]
        return f"Elva-{rest[:2]}****-{rest[-4:]}"
    return s[:4] + "****" + s[-4:]


def get_customer_purchase_count(customer_id: int | str) -> int:
    """Menghitung total riwayat transaksi pembelian yang pernah dilakukan pelanggan."""
    if not os.path.exists(ORDERS_CSV):
        return 1
    cnt = 0
    cid_str = str(customer_id).strip()
    try:
        with open(ORDERS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("customer_id", "").strip() == cid_str:
                    cnt += 1
    except Exception:
        pass
    return max(cnt, 1)


def get_top_buyers(limit: int = 5) -> List[dict]:
    """Mengambil daftar pelanggan dengan pembelian terbanyak dari orders.csv."""
    if not os.path.exists(ORDERS_CSV):
        return []

    from collections import defaultdict
    buyers = defaultdict(lambda: {"count": 0, "total_price": 0, "name": ""})

    try:
        with open(ORDERS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get("customer_id", "").strip()
                if not cid:
                    continue
                buyers[cid]["count"] += 1
                try:
                    buyers[cid]["total_price"] += int(float(row.get("total_price", 0) or 0))
                except Exception:
                    pass
                if row.get("customer_name"):
                    buyers[cid]["name"] = row.get("customer_name")
    except Exception:
        return []

    sorted_buyers = sorted(buyers.items(), key=lambda x: (x[1]["count"], x[1]["total_price"]), reverse=True)
    res = []
    for cid, stats in sorted_buyers[:limit]:
        res.append({
            "customer_id": cid,
            "masked_id": mask_customer_id(cid),
            "name": stats["name"],
            "count": stats["count"],
            "total_price": stats["total_price"]
        })
    return res


def build_group_purchase_notification(
    order: dict,
    chat_id: int | str,
    order_id: str,
    bot_username: str = "Profesional_umkm_bot"
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat kartu notifikasi NEW PURCHASE untuk dikirimkan ke Elva Group.
    Format persis seperti di gambar BerryGrowID Grup.
    """
    masked_id = mask_customer_id(str(chat_id))
    masked_oid = mask_order_id(order_id)

    items = order.get("items", [])
    if items:
        prod_name = items[0].get("nama", "Produk Digital")
        qty = sum(item.get("qty", 1) for item in items)
    else:
        prod_name = "Produk Digital"
        qty = 1

    total_purchases = get_customer_purchase_count(str(chat_id))

    lines = [
        "*Elva Group*\n",
        "🎉 *NEW PURCHASE* 🎉",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Pelanggan       `{masked_id}`",
        f"Produk          *{prod_name}*",
        f"Order           `{masked_oid}`",
        f"Jumlah          {qty}",
        f"Total Pembelian {total_purchases}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    keyboard = [
        [
            InlineKeyboardButton("🛍️ Beli Produk ↗️", url=f"https://t.me/{bot_username}?start=katalog"),
            InlineKeyboardButton("📲 Buka Bot ↗️", url=f"https://t.me/{bot_username}?start=menu")
        ]
    ]

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


def build_top_buyers_keyboard(limit: int = 5, bot_username: str = "Profesional_umkm_bot") -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan leaderboard / peringkat pembeli terbanyak di Elva Tech.
    """
    top_list = get_top_buyers(limit)
    lines = [
        "🏆 *LEADERBOARD PEMBELIAN TERBANYAK* 🏆",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "_Daftar pelanggan setia dengan transaksi terbanyak di Elva Tech Store:_\n"
    ]

    medals = ["🥇", "🥈", "🥉", "🎖️", "🎖️"]

    if not top_list:
        lines.append("Belum ada riwayat transaksi yang tercatat.")
    else:
        for idx, buyer in enumerate(top_list):
            medal = medals[idx] if idx < len(medals) else "🎖️"
            masked_id = buyer["masked_id"]
            count = buyer["count"]
            total_fmt = f"Rp{buyer['total_price']:,}".replace(",", ".")
            lines.append(
                f"{medal} *Peringkat #{idx + 1} — Pelanggan `{masked_id}`*\n"
                f"   • Total Pembelian: *{count}x Transaksi*\n"
                f"   • Total Belanja: *{total_fmt}*\n"
            )

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🔥 _Yuk tingkatkan transaksi kakak dan raih reward & diskon khusus Top Buyer!_"
    ])

    keyboard = [
        [
            InlineKeyboardButton("🛍️ Beli Produk Sekarang ↗️", url=f"https://t.me/{bot_username}?start=katalog")
        ],
        [
            InlineKeyboardButton("📢 Gabung Elva Group ↗️", url="https://t.me/+4_By8JH_MPg2Mjc9")
        ]
    ]

    return "\n".join(lines), InlineKeyboardMarkup(keyboard)
