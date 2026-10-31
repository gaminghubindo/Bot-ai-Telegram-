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


# ==========================================
# PEMBUATAN INLINE KEYBOARD (UI SEPERTI BerryGrowID)
# ==========================================

def build_main_dashboard(chat_id: int | str, user_info: dict) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Membuat tampilan Dashboard Akun & Ringkasan mirip dengan referensi BerryGrowID.
    """
    menu_data = load_menu()
    nama_usaha = menu_data.get("nama_usaha", "Digital Store")
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
            InlineKeyboardButton("📦 Pesanan Saya", callback_data="my_orders"),
            InlineKeyboardButton("💳 Info Pembayaran", callback_data="payment_info")
        ],
        [
            InlineKeyboardButton("👤 Profil Akun", callback_data="my_profile"),
            InlineKeyboardButton("❗ Bantuan & Garansi", callback_data="help_info")
        ],
        [
            InlineKeyboardButton("👨‍💼 Hubungi CS / Admin", callback_data="contact_admin")
        ]
    ]

    return text, InlineKeyboardMarkup(keyboard)


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

    # Tombol refresh & kembali
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"prod:{prod_id}"),
        InlineKeyboardButton("◀️ Kembali", callback_data="view_catalog")
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
