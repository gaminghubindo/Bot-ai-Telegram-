"""
orders.py - Logika pencatatan pesanan, perhitungan harga berdasarkan menu.json,
penyimpanan ke CSV, dan format notifikasi untuk pemilik toko.
"""

import csv
import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

# Path file menu dan penyimpanan pesanan
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENU_FILE = os.path.join(BASE_DIR, "data", "menu.json")
ORDERS_CSV = os.path.join(BASE_DIR, "data", "orders.csv")

# State pesanan yang sedang menunggu konfirmasi "ya": {chat_id: order_data}
_pending_orders: Dict[str, dict] = {}


def load_menu() -> dict:
    """Membaca file data/menu.json."""
    if not os.path.exists(MENU_FILE):
        return {}
    with open(MENU_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_menu_display_text() -> str:
    """
    Menghasilkan tampilan menu yang rapi untuk perintah /menu
    maupun sebagai konteks informasi toko.
    """
    menu_data = load_menu()
    if not menu_data:
        return "Menu belum tersedia saat ini."

    nama_usaha = menu_data.get("nama_usaha", "Warung Kuliner")
    slogan = menu_data.get("slogan", "")
    jam_buka = menu_data.get("jam_buka", "-")
    alamat = menu_data.get("alamat", "-")
    area_antar = ", ".join(menu_data.get("area_antar", []))

    lines = [
        f"🍽️ *DAFTAR MENU {nama_usaha.upper()}*",
        f"_{slogan}_" if slogan else "",
        "",
        f"📍 Alamat: {alamat}",
        f"⏰ Jam Buka: {jam_buka}",
        f"🛵 Area Antar: {area_antar}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        ""
    ]

    # Kelompokkan menu berdasarkan kategori
    categories: Dict[str, List[dict]] = {}
    for item in menu_data.get("menu", []):
        cat = item.get("kategori", "Menu Lainnya")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    for cat_name, items in categories.items():
        lines.append(f"📌 *{cat_name.upper()}*")
        for item in items:
            nama = item.get("nama")
            harga = f"Rp{item.get('harga', 0):,}".replace(",", ".")
            desc = item.get("deskripsi", "")
            lines.append(f"• *{nama}* — {harga}")
            if desc:
                lines.append(f"  _{desc}_")
        lines.append("")

    # Info Ongkir & Pembayaran
    ongkir_info = menu_data.get("ongkir", {})
    ket_ongkir = ongkir_info.get("keterangan", "")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    if ket_ongkir:
        lines.append(f"🚚 *Ongkir:* {ket_ongkir}")

    info_bayar = menu_data.get("info_pembayaran", {})
    metode_list = ", ".join(info_bayar.get("metode", []))
    if metode_list:
        lines.append(f"💳 *Metode Bayar:* {metode_list}")

    lines.append("\nMau pesan apa nih kak? Langsung chat aja ya, siap dicatat! 😊")
    return "\n".join(lines).strip()


def find_matching_menu_item(item_query: str, menu_items: List[dict]) -> Optional[dict]:
    """
    Mencari kecocokan menu berdasarkan nama query menggunakan normalisasi dan fuzzy match.
    """
    clean_query = item_query.lower().strip()
    
    # 1. Cek kecocokan langsung (exact atau substring)
    for item in menu_items:
        nama_item = item.get("nama", "").lower()
        id_item = item.get("id", "").lower()
        if clean_query == nama_item or clean_query == id_item:
            return item
        if clean_query in nama_item or nama_item in clean_query:
            return item

    # 2. Cek kecocokan kata kunci terpenting
    query_words = set(re.findall(r"\w+", clean_query))
    best_item = None
    best_score = 0.0

    for item in menu_items:
        nama_item = item.get("nama", "").lower()
        item_words = set(re.findall(r"\w+", nama_item))
        
        # Hitung overlap kata kunci
        common_words = query_words.intersection(item_words)
        if common_words:
            score = len(common_words) / max(len(query_words), len(item_words))
            if score > best_score:
                best_score = score
                best_item = item

        # Hitung fuzzy ratio
        ratio = SequenceMatcher(None, clean_query, nama_item).ratio()
        if ratio > best_score and ratio >= 0.55:
            best_score = ratio
            best_item = item

    return best_item


def calculate_shipping_fee(address: str, subtotal: int, menu_data: dict) -> Tuple[int, str]:
    """
    Menghitung ongkos kirim berdasarkan alamat pelanggan dan aturan menu.json.
    Mengembalikan (ongkir, nama_area).
    """
    ongkir_cfg = menu_data.get("ongkir", {})
    default_ongkir = ongkir_cfg.get("default", 8000)
    area_tarif = ongkir_cfg.get("area_tarif", {})

    addr_lower = (address or "").lower()

    detected_area = "Lainnya"
    fee = default_ongkir

    for area, tarif in area_tarif.items():
        if area.lower() in addr_lower:
            detected_area = area.title()
            fee = tarif
            break

    # Cek promo gratis ongkir jika ada
    # Khusus warung bu sari: pesanan >= 100k di area Sukajadi/Pasteur gratis ongkir
    if subtotal >= 100000 and detected_area.lower() in ["sukajadi", "pasteur"]:
        fee = 0
        detected_area += " (Promo Gratis Ongkir)"

    return fee, detected_area


def calculate_order_total(raw_order: dict) -> dict:
    """
    Menghitung rincian harga pesanan menggunakan kode Python murni berdasarkan menu.json.
    BUKAN dihitung oleh LLM untuk mencegah halusinasi matematika.
    """
    menu_data = load_menu()
    menu_items = menu_data.get("menu", [])

    items_input = raw_order.get("items", [])
    method = (raw_order.get("metode") or "antar").strip().lower()
    address = raw_order.get("alamat", "")

    calculated_items = []
    subtotal = 0

    for it in items_input:
        raw_name = it.get("nama", "")
        qty = int(it.get("qty", 1))
        if qty <= 0:
            qty = 1
        item_notes = it.get("catatan", "")

        matched = find_matching_menu_item(raw_name, menu_items)
        if matched:
            item_name = matched.get("nama")
            unit_price = int(matched.get("harga", 0))
        else:
            # Fallback jika menu tidak teridentifikasi
            item_name = raw_name.title()
            unit_price = int(it.get("harga", 0))

        item_total = unit_price * qty
        subtotal += item_total

        calculated_items.append({
            "nama": item_name,
            "qty": qty,
            "harga_satuan": unit_price,
            "subtotal": item_total,
            "catatan": item_notes
        })

    # Hitung ongkir jika diantar
    if "antar" in method:
        ongkir, area_name = calculate_shipping_fee(address, subtotal, menu_data)
        metode_clean = "Antar (Delivery)"
    else:
        ongkir = 0
        area_name = "-"
        metode_clean = "Ambil Sendiri (Pickup)"

    grand_total = subtotal + ongkir

    return {
        "nama": raw_order.get("nama", "Pelanggan"),
        "metode": metode_clean,
        "alamat": address if "antar" in method else "-",
        "area_antar": area_name,
        "waktu": raw_order.get("waktu", "Secepatnya"),
        "catatan": raw_order.get("catatan", "-"),
        "items": calculated_items,
        "subtotal": subtotal,
        "ongkir": ongkir,
        "total_harga": grand_total
    }


def format_order_summary_for_customer(order: dict) -> str:
    """
    Menghasilkan ringkasan pesanan rapi untuk pelanggan sebelum konfirmasi final.
    """
    lines = [
        f"📋 *RINGKASAN PESANAN KAK {order['nama'].upper()}*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🍽️ *Menu yang Dipesan:*"
    ]

    for it in order["items"]:
        nama = it["nama"]
        qty = it["qty"]
        harga_satuan = f"Rp{it['harga_satuan']:,}".replace(",", ".")
        sub = f"Rp{it['subtotal']:,}".replace(",", ".")
        catatan = f" ({it['catatan']})" if it.get("catatan") and it['catatan'] != "-" else ""
        lines.append(f"• {qty}x {nama} @ {harga_satuan} = {sub}{catatan}")

    subtotal_str = f"Rp{order['subtotal']:,}".replace(",", ".")
    lines.append("──────────────────────")
    lines.append(f"Subtotal Menu: {subtotal_str}")
    lines.append(f"Metode: {order['metode']}")
    
    if "antar" in order['metode'].lower():
        lines.append(f"Alamat: {order['alamat']}")
        ongkir_str = f"Rp{order['ongkir']:,}".replace(",", ".") if order['ongkir'] > 0 else "GRATIS"
        lines.append(f"Ongkir ({order['area_antar']}): {ongkir_str}")

    lines.append(f"Waktu: {order['waktu']}")
    if order.get("catatan") and order['catatan'] != "-":
        lines.append(f"Catatan Pesanan: {order['catatan']}")

    total_str = f"Rp{order['total_harga']:,}".replace(",", ".")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 *TOTAL BAYAR: {total_str}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("\nApakah data pesanan di atas sudah benar kak?")
    lines.append("Ketik *'ya'* untuk konfirmasi pesanan ya! 😊")

    return "\n".join(lines)


def format_owner_order_recap(order: dict, chat_id: int | str, user_info: dict) -> str:
    """
    Menghasilkan rekap pesanan lengkap yang dikirim ke OWNER_CHAT_ID.
    """
    timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M WIB")
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    username = f"@{user_info.get('username')}" if user_info.get("username") else "-"
    customer_fullname = user_info.get("full_name") or order.get("nama")

    lines = [
        "🔔 *PESANAN BARU MASUK!*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🆔 No. Pesanan: `{order_id}`",
        f"📅 Waktu Pesan: {timestamp_str}",
        f"👤 Nama: *{order['nama']}* ({customer_fullname})",
        f"💬 Telegram: {username} (ID: `{chat_id}`)",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🍽️ *Daftar Pesanan:*"
    ]

    for it in order["items"]:
        nama = it["nama"]
        qty = it["qty"]
        harga_satuan = f"Rp{it['harga_satuan']:,}".replace(",", ".")
        sub = f"Rp{it['subtotal']:,}".replace(",", ".")
        catatan = f" [{it['catatan']}]" if it.get("catatan") and it['catatan'] != "-" else ""
        lines.append(f"• {qty}x {nama} @ {harga_satuan} = {sub}{catatan}")

    subtotal_str = f"Rp{order['subtotal']:,}".replace(",", ".")
    lines.append("──────────────────────")
    lines.append(f"Subtotal: {subtotal_str}")
    lines.append(f"Metode: *{order['metode']}*")
    
    if "antar" in order['metode'].lower():
        lines.append(f"📍 Alamat Kirim: {order['alamat']}")
        ongkir_str = f"Rp{order['ongkir']:,}".replace(",", ".") if order['ongkir'] > 0 else "GRATIS"
        lines.append(f"🛵 Ongkir ({order['area_antar']}): {ongkir_str}")

    lines.append(f"⏰ Waktu: {order['waktu']}")
    if order.get("catatan") and order['catatan'] != "-":
        lines.append(f"📝 Catatan: {order['catatan']}")

    total_str = f"Rp{order['total_harga']:,}".replace(",", ".")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 *TOTAL BAYAR: {total_str}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚡ Status: *Menunggu Proses Dapur & Pembayaran*")

    return "\n".join(lines), order_id


def format_owner_escalation(customer_user: dict, reason: str, customer_message: str) -> str:
    """
    Format notifikasi komplain / eskalasi pelanggan untuk pemilik toko.
    """
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
    """
    Menyimpan pesanan yang telah dikonfirmasi ke file data/orders.csv.
    """
    os.makedirs(os.path.dirname(ORDERS_CSV), exist_ok=True)
    file_exists = os.path.exists(ORDERS_CSV)

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Format ringkas daftar item untuk satu kolom CSV
    items_summary = "; ".join([
        f"{it['qty']}x {it['nama']}" + (f" ({it['catatan']})" if it.get('catatan') and it['catatan'] != '-' else "")
        for it in order["items"]
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
            "status": "Dikonfirmasi"
        })


# State pengelolaan pending order per user
def set_pending_order(chat_id: int | str, order_data: dict) -> None:
    _pending_orders[str(chat_id)] = order_data


def get_pending_order(chat_id: int | str) -> Optional[dict]:
    return _pending_orders.get(str(chat_id))


def clear_pending_order(chat_id: int | str) -> None:
    key = str(chat_id)
    if key in _pending_orders:
        del _pending_orders[key]
