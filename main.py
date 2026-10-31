"""
main.py - Entry point bot Telegram AI Toko Digital / UMKM.
Mendukung antarmuka tombol interaktif (Dashboard Akun, Katalog Produk, Pilihan Varian,
Numpad Jumlah, Pembayaran QRIS/Bank) serta asisten AI cerdas (Gemini 3.5 Flash).
"""

import logging
import os
import re
import sys

# Dukungan UTF-8 di Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from telegram import BotCommand, MenuButtonCommands, Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from llm import call_llm, extract_metadata_tags, load_system_prompt
import memory
import orders

# Muat variabel konfigurasi dari file .env
load_dotenv()

# Konfigurasi logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Kunci rahasia dari .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()


async def send_safe_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, text: str, reply_markup=None) -> None:
    """Mengirim pesan dengan Markdown, jika gagal otomatis kirim sebagai teks biasa."""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning(f"Gagal kirim format Markdown ({e}), mencoba teks biasa...")
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=None,
            reply_markup=reply_markup
        )


async def edit_safe_message(query, text: str, reply_markup=None) -> None:
    """Mengedit pesan callback secara aman."""
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning(f"Gagal edit message Markdown ({e}), mencoba teks biasa...")
        try:
            await query.edit_message_text(
                text=text,
                parse_mode=None,
                reply_markup=reply_markup
            )
        except Exception:
            pass


async def safe_react(message, emoji: str) -> None:
    """Menambahkan reaksi emoji lucu pada pesan pengguna secara non-blocking dan aman."""
    if not message:
        return
    try:
        await message.set_reaction(emoji)
    except Exception:
        pass


# ==========================================
# COMMAND HANDLERS (/start, /menu, /id)
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /start: Menampilkan Dashboard Akun & Menu Tombol Interaktif."""
    if update.message:
        await safe_react(update.message, "🔥")

    user = update.effective_user
    chat_id = update.effective_chat.id

    memory.clear_history(chat_id)
    orders.clear_pending_order(chat_id)

    user_info = {
        "chat_id": chat_id,
        "username": user.username if user else "",
        "full_name": user.full_name if user else "Pelanggan"
    }

    text, reply_markup = orders.build_main_dashboard(chat_id, user_info)
    await send_safe_message(context, chat_id, text, reply_markup=reply_markup)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /menu: Menampilkan Dashboard Akun & Menu Tombol Interaktif."""
    if update.message:
        await safe_react(update.message, "⚡")

    user = update.effective_user
    chat_id = update.effective_chat.id

    user_info = {
        "chat_id": chat_id,
        "username": user.username if user else "",
        "full_name": user.full_name if user else "Pelanggan"
    }

    text, reply_markup = orders.build_main_dashboard(chat_id, user_info)
    await send_safe_message(context, chat_id, text, reply_markup=reply_markup)


async def jasa_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /jasa: Menampilkan menu layanan jasa profesional dari Lynk.id."""
    if update.message:
        await safe_react(update.message, "👨‍💻")

    chat_id = update.effective_chat.id
    text, reply_markup = orders.build_jasa_keyboard()
    await send_safe_message(context, chat_id, text, reply_markup=reply_markup)


async def grup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /grup atau /group: Menampilkan informasi & tautan bergabung ke Elva Group."""
    if update.message:
        await safe_react(update.message, "📢")

    chat_id = update.effective_chat.id
    text, reply_markup = orders.build_group_keyboard()
    await send_safe_message(context, chat_id, text, reply_markup=reply_markup)


async def restock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /restock (Khusus Owner): Mengirim notifikasi reset/restock stok ke Elva Group."""
    chat_id = str(update.effective_chat.id)

    # Validasi hanya pemilik toko yang bisa broadcast
    if OWNER_CHAT_ID and chat_id != str(OWNER_CHAT_ID):
        await send_safe_message(context, chat_id, "⚠️ Perintah ini khusus untuk pemilik toko.")
        return

    # Ambil pesan restock dari argumen perintah
    args = context.args
    if not args:
        help_msg = (
            "📢 *PANDUAN BROADCAST RESTOCK (OWNER)*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Gunakan format: `/restock <informasi restock>`\n\n"
            "*Contoh:*\n"
            "`/restock Gemini Pro 3 Bulan & ChatGPT Plus sudah restock 50 akun! Langsung order di bot sebelum kehabisan!`\n\n"
            "💡 _Notifikasi ini otomatis dikirimkan ke Elva Group jika ID grup sudah disetel di .env._"
        )
        await send_safe_message(context, chat_id, help_msg)
        return

    restock_text = " ".join(args)
    elva_group_chat_id = os.getenv("ELVA_GROUP_CHAT_ID", "").strip()

    announcement = (
        "🔔 *NOTIFIKASI RESTOCK & RESET STOK ELVA TECH!* 🔔\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{restock_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *Cara Beli:* Langsung buka bot @Profesional_umkm_bot dan klik menu produk!\n"
        "💬 Ada pertanyaan? Hubungi akun Telegram @Carlendra"
    )

    if elva_group_chat_id:
        try:
            await context.bot.send_message(
                chat_id=elva_group_chat_id,
                text=announcement,
                parse_mode=constants.ParseMode.MARKDOWN
            )
            await send_safe_message(context, chat_id, "✅ Pesan restock berhasil otomatis dikirim ke Elva Group! 🚀")
            return
        except Exception as e:
            logger.error(f"Gagal mengirim pesan restock ke Elva Group ({e})")

    # Jika ELVA_GROUP_CHAT_ID belum disetel di .env
    reply = (
        "📢 *Pesan Restock Siap Dikirim:*\n\n"
        f"{announcement}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tips Otomatisasi:* Masukkan ID Elva Group ke file `.env` pada variabel `ELVA_GROUP_CHAT_ID` agar bot dapat mengirim langsung ke grup tanpa perlu disalin manual."
    )
    await send_safe_message(context, chat_id, reply)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /id: Menampilkan Chat ID Telegram pengguna."""
    if update.message:
        await safe_react(update.message, "👍")

    user = update.effective_user
    chat_id = update.effective_chat.id

    username = f"@{user.username}" if user and user.username else "-"
    fullname = user.full_name if user else "-"

    id_info = (
        "🆔 *Informasi Akun Telegram Anda*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Chat ID: `{chat_id}`\n"
        f"Nama: {fullname}\n"
        f"Username: {username}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tips Pemilik Toko:*\n"
        f"Salin angka `{chat_id}` di atas dan masukkan ke file `.env` pada variabel "
        "`OWNER_CHAT_ID` agar setiap pesanan dan komplain pelanggan langsung masuk ke akun ini."
    )

    await send_safe_message(context, chat_id, id_info)


# ==========================================
# CALLBACK QUERY HANDLER (TOMBOL INTERAKTIF)
# ==========================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani setiap klik tombol inline (Menu, Produk, Varian, Stepper, Jumlah, Pembayaran)."""
    query = update.callback_query
    data = query.data or ""
    user = update.effective_user
    chat_id = update.effective_chat.id

    user_info = {
        "chat_id": chat_id,
        "username": user.username if user else "",
        "full_name": user.full_name if user else "Pelanggan"
    }

    # 1. Kembali ke Menu Dashboard Utama
    if data == "menu_main":
        await query.answer("🏠 Kembali ke Menu Utama ✨")
        text, markup = orders.build_main_dashboard(chat_id, user_info)
        await edit_safe_message(query, text, markup)
        return

    # 2. Lihat Katalog Produk Lengkap (Grid)
    if data == "view_catalog":
        await query.answer("🛍️ Membuka Katalog Produk Digital... ✨")
        text, markup = orders.build_catalog_keyboard()
        await edit_safe_message(query, text, markup)
        return

    # 2b. Lihat Layanan Jasa (Landing Page, Desain, 3D)
    if data == "view_jasa":
        await query.answer("🎨 Membuka Portofolio Jasa @nellionel... 💼")
        text, markup = orders.build_jasa_keyboard()
        await edit_safe_message(query, text, markup)
        return

    # 2d. Lihat Elva Group (Info Restock & Reset Stok)
    if data == "view_group":
        await query.answer("📢 Membuka Informasi Elva Group... ✨")
        text, markup = orders.build_group_keyboard()
        await edit_safe_message(query, text, markup)
        return

    # 2c. Lihat Detail Jasa Tertentu
    if data.startswith("jasa_detail:"):
        await query.answer("🔍 Membuka detail & tarif layanan... ✨")
        jasa_id = data.split(":", 1)[1]
        text, markup = orders.build_jasa_detail_keyboard(jasa_id)
        await edit_safe_message(query, text, markup)
        return

    # 3. Pilih Produk Tertentu -> Tampilkan Varian & Harga
    if data.startswith("prod:"):
        await query.answer("📦 Memuat pilihan varian & harga... 🚀")
        prod_id = data.split(":", 1)[1]
        text, markup = orders.build_product_variants_keyboard(prod_id)
        await edit_safe_message(query, text, markup)
        return

    # 4. Klik Varian yang Stoknya Habis
    if data.startswith("var_empty:"):
        await query.answer(
            "🥺 Yah, stok varian ini sedang habis kak!\n\n"
            "Yuk gabung ke Elva Group agar langsung dapat notifikasi saat stok di-reset & ready ya! ✨",
            show_alert=True
        )
        return

    # 5. Pilih Varian yang Tersedia -> Tampilkan Numpad / Stepper Jumlah
    if data.startswith("var:"):
        await query.answer("🔢 Silakan pilih jumlah item ya kak! ✨")
        parts = data.split(":")
        prod_id, var_id = parts[1], parts[2]
        text, markup = orders.build_quantity_keyboard(prod_id, var_id)
        await edit_safe_message(query, text, markup)
        return

    # 5b. Tombol Stepper Interaktif (+ / -) di Layar Checkout
    if data.startswith("step:"):
        parts = data.split(":")
        prod_id, var_id, new_qty_str = parts[1], parts[2], parts[3]
        new_qty = int(new_qty_str)

        product = orders.get_product_by_id(prod_id)
        variant = orders.get_variant_by_id(product, var_id) if product else None
        stok = variant.get("stok", 10) if variant else 10
        harga_satuan = variant.get("harga", 0) if variant else 0

        total_harga = harga_satuan * new_qty
        total_str = orders.format_rupiah(total_harga)

        await query.answer(f"🛒 Jumlah: {new_qty} item ({total_str}) ✨")
        text, markup = orders.build_checkout_keyboard(prod_id, var_id, new_qty)
        await edit_safe_message(query, text, markup)
        return

    # 5c. Info Stepper (Klik Tombol Tengah)
    if data.startswith("step_info:"):
        parts = data.split(":")
        prod_id, var_id, qty_str = parts[1], parts[2], parts[3]
        qty = int(qty_str)
        product = orders.get_product_by_id(prod_id)
        variant = orders.get_variant_by_id(product, var_id) if product else None
        harga_satuan = variant.get("harga", 0) if variant else 0
        total_str = orders.format_rupiah(harga_satuan * qty)
        await query.answer(f"💡 Info: {qty} item · Total {total_str} ✨", show_alert=False)
        return

    # 6. Pilih Jumlah Porsi / Akun -> Tampilkan Rincian Checkout & Metode Bayar
    if data.startswith("qty:"):
        parts = data.split(":")
        prod_id, var_id, qty_str = parts[1], parts[2], parts[3]
        qty = int(qty_str)
        await query.answer(f"🛒 Dipilih {qty} item. Menyiapkan checkout... 💳")
        text, markup = orders.build_checkout_keyboard(prod_id, var_id, qty)
        await edit_safe_message(query, text, markup)
        return

    # 7. Pilih Metode Pembayaran (QRIS, BCA, E-Wallet) -> Selesaikan Pesanan
    if data.startswith("pay:"):
        parts = data.split(":")
        prod_id, var_id, qty_str, method_code = parts[1], parts[2], parts[3], parts[4]
        qty = int(qty_str)

        await query.answer(
            "🎉 Yeay! Pesanan berhasil dibuat.\n\n"
            "Silakan transfer dan kirimkan bukti foto pembayaran ke chat ini ya kak! ✨",
            show_alert=True
        )

        text, markup, owner_msg = orders.build_payment_instruction(
            prod_id, var_id, qty, method_code, chat_id, user_info
        )
        await edit_safe_message(query, text, markup)

        # Kirim notifikasi pesanan ke pemilik toko
        if OWNER_CHAT_ID and OWNER_CHAT_ID != "your_chat_id_here":
            try:
                await send_safe_message(context, OWNER_CHAT_ID, owner_msg)
            except Exception as e:
                logger.error(f"Gagal mengirim pesanan ke owner: {e}")
        return

    # 7b. Hint Petunjuk Pengiriman Bukti Bayar
    if data == "send_proof_hint":
        await query.answer(
            "📸 Kirim foto screenshot bukti transfer langsung ke chat ini ya kak!\n\n"
            "Admin kami akan segera mengecek dan memberikan akses akun/layanan Anda. 🙏",
            show_alert=True
        )
        return

    # 8. Menu Pesanan Saya
    if data == "my_orders":
        await query.answer("📦 Memuat riwayat belanja kamu... ✨")
        total_spend, order_count = orders.get_user_stats(chat_id)
        text = (
            "📦 *RIWAYAT PESANAN SAYA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User ID: `{chat_id}`\n"
            f"💳 Total Belanja: {orders.format_rupiah(total_spend)}\n"
            f"📊 Total Transaksi: {order_count} pesanan\n\n"
            "_Pesanan Anda diproses otomatis oleh admin setelah bukti transfer dikirimkan ke chat ini._"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data="menu_main")]])
        await edit_safe_message(query, text, markup)
        return

    # 9. Menu Info Pembayaran
    if data == "payment_info":
        await query.answer("💳 Memuat rekening & QRIS toko... ✨")
        menu_data = orders.load_menu()
        pay = menu_data.get("info_pembayaran", {})
        text = (
            "💳 *INFORMASI PEMBAYARAN TOKO*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 *QRIS:* {pay.get('qris', '-')}\n"
            f"🏦 *Bank:* `{pay.get('bank', '-')}`\n"
            f"💳 *E-Wallet:* `{pay.get('ewallet', '-')}`\n\n"
            f"📌 *Catatan:* {pay.get('catatan', '-')}"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data="menu_main")]])
        await edit_safe_message(query, text, markup)
        return

    # 10. Menu Profil Akun
    if data == "my_profile":
        await query.answer("👤 Memuat profil akun kamu... ✨")
        total_spend, order_count = orders.get_user_stats(chat_id)
        text = (
            "👤 *PROFIL PENGGUNA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Nama: *{user_info['full_name']}*\n"
            f"Username: @{user_info['username'] or '-'}\n"
            f"Chat ID: `{chat_id}`\n"
            f"Status: Pelanggan Aktif ⭐\n"
            f"Total Belanja: {orders.format_rupiah(total_spend)}\n"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Kembali", callback_data="menu_main")]])
        await edit_safe_message(query, text, markup)
        return

    # 11. Menu Bantuan & Garansi
    if data == "help_info":
        await query.answer("💡 Memuat info garansi & bantuan... ✨")
        menu_data = orders.load_menu()
        syarat = menu_data.get("syarat_ketentuan", "-")
        text = (
            "❗ *BANTUAN & KETENTUAN GARANSI*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{syarat}\n\n"
            "💬 *Bantuan Langsung:*\n"
            "Jikalau ada masalah hubungi akun Telegram username @Carlendra\n\n"
            "✅ *Cara Klaim Garansi:*\n"
            "Kirimkan chat nomor pesanan Anda dan kendala yang dialami."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Hubungi @Carlendra", url="https://t.me/Carlendra")],
            [InlineKeyboardButton("◀️ Kembali", callback_data="menu_main")]
        ])
        await edit_safe_message(query, text, markup)
        return

    # 12. Hubungi Admin / CS
    if data == "contact_admin":
        await query.answer("👨‍💼 Membuka kontak CS & Telegram @Carlendra... ✨")
        text = (
            "👨‍💼 *LAYANAN CUSTOMER SERVICE*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Jikalau ada masalah hubungi akun Telegram username @Carlendra\n\n"
            "Asisten AI kami juga siap menjawab pertanyaan seputar produk, stok, garansi, dan panduan lainnya 24/7 di chat ini! 💬"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Chat Langsung @Carlendra", url="https://t.me/Carlendra")],
            [InlineKeyboardButton("◀️ Kembali ke Menu", callback_data="menu_main")]
        ])
        await edit_safe_message(query, text, markup)
        return

    # Default fallback answer
    await query.answer()


# ==========================================
# MESSAGE HANDLER (CHAT TEKS & AI ASSISTANT)
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani setiap chat teks dari pengguna menggunakan AI Gemini Flash."""
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    user_text = update.message.text.strip()

    # Reaksi emoji lucu pada pesan chat
    await safe_react(update.message, "👀")
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

    user_info = {
        "chat_id": chat_id,
        "username": user.username if user else "",
        "full_name": user.full_name if user else "Pelanggan"
    }

    clean_lower = user_text.lower()

    # Deteksi komplain langsung
    is_direct_complaint = False
    complaint_keywords = [
        "komplain", "kecewa", "rusak", "tidak bisa login", "salah password",
        "kena banned", "garansi", "ganti akun", "bicara sama admin", "bicara sama pemilik"
    ]
    if any(k in clean_lower for k in complaint_keywords):
        is_direct_complaint = True

    # Simpan riwayat chat ke memori
    memory.add_message(chat_id, "user", user_text)

    # Siapkan payload untuk LLM
    messages_payload = [
        {"role": "system", "content": load_system_prompt()}
    ]
    messages_payload.extend(memory.get_history(chat_id))

    # Panggil LLM (Gemini Flash dengan fallback ke Groq)
    reply_text, provider = await call_llm(messages_payload)

    if not reply_text:
        fallback_msg = (
            "Duh, lagi ada sedikit gangguan jaringan nih kak. "
            "Coba kirim lagi sebentar ya, atau langsung hubungi admin @Carlendra. 🙏"
        )
        await send_safe_message(context, chat_id, fallback_msg)
        return

    cleaned_reply, raw_order, raw_escalate = extract_metadata_tags(reply_text)

    # Jika pelanggan komplain, kirim notifikasi ke pemilik
    if raw_escalate or is_direct_complaint:
        reason = (
            raw_escalate.get("alasan")
            if (raw_escalate and isinstance(raw_escalate, dict))
            else "Komplain / Butuh Bantuan Akun"
        )
        if OWNER_CHAT_ID and OWNER_CHAT_ID != "your_chat_id_here":
            escalation_msg = orders.format_owner_escalation(user_info, reason, user_text)
            try:
                await send_safe_message(context, OWNER_CHAT_ID, escalation_msg)
            except Exception as e:
                logger.error(f"Gagal mengirim eskalasi ke owner: {e}")

    # Kirim balasan AI ke pelanggan beserta tombol pintasan ke katalog
    shortcut_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Buka Katalog Produk", callback_data="view_catalog")],
        [InlineKeyboardButton("📋 Menu Utama", callback_data="menu_main")]
    ])

    memory.add_message(chat_id, "assistant", cleaned_reply)
    await send_safe_message(context, chat_id, cleaned_reply, reply_markup=shortcut_markup)


# ==========================================
# PHOTO HANDLER (BUKTI TRANSFER PELANGGAN)
# ==========================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Menangani pengiriman foto bukti transfer dari pelanggan."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    # Reaksi selebrasi lucu saat bukti transfer masuk
    if update.message:
        await safe_react(update.message, "🎉")

    user_info = {
        "chat_id": chat_id,
        "username": f"@{user.username}" if user and user.username else "-",
        "full_name": user.full_name if user else "Pelanggan"
    }

    # Teruskan foto bukti pembayaran ke pemilik toko
    if OWNER_CHAT_ID and OWNER_CHAT_ID != "your_chat_id_here":
        try:
            caption = (
                "📸 *BUKTI PEMBAYARAN BARU DITERIMA!*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Dari: *{user_info['full_name']}* ({user_info['username']})\n"
                f"🆔 Chat ID: `{chat_id}`\n\n"
                "⚠️ _Mohon segera cek mutasi rekening/QRIS dan kirimkan akun ke pelanggan ini._"
            )
            photo_file_id = update.message.photo[-1].file_id
            await context.bot.send_photo(
                chat_id=OWNER_CHAT_ID,
                photo=photo_file_id,
                caption=caption,
                parse_mode=constants.ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Gagal meneruskan bukti transfer ke pemilik: {e}")

    # Balasan ramah ke pelanggan
    reply_text = (
        "Terima kasih banyak kak! Foto bukti pembayaran sudah kami terima dan "
        "langsung diteruskan ke admin toko. 🙏\n\n"
        "Pesanan kakak sedang diverifikasi dan data akun/akses layanan akan segera dikirimkan ya! 😊"
    )
    await send_safe_message(context, chat_id, reply_text)


async def post_init(application: Application) -> None:
    """Mendaftarkan tombol menu native [ ☰ Menu ] di samping kiri kolom chat Telegram dan deskripsi bot."""
    commands = [
        BotCommand("menu", "💎 Buka Menu & Katalog Produk"),
        BotCommand("jasa", "🛠️ Layanan Jasa (Landing Page, Desain, 3D)"),
        BotCommand("grup", "📢 Gabung Elva Group (Info Restock)"),
        BotCommand("start", "🚀 Mulai / Dashboard Akun"),
        BotCommand("id", "🆔 Cek Chat ID Akun Saya"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        
        # Atur deskripsi bot di Telegram (Muncul saat chat pertama kali dibuka, maks 512 karakter)
        desc = (
            "Selamat datang di Elva Tech — Toko Digital & Jasa Kreatif UMKM!\n\n"
            "💎 Produk Digital: Akun AI (Gemini Pro, ChatGPT), Canva, Netflix, dll.\n"
            "🛠️ Layanan Jasa: Landing Page (Rp45rb), Desain PPT (Rp2rb/slide), 3D Modeling (Rp90rb).\n"
            "📢 Elva Group: Update restock & reset stok akun.\n"
            "🌐 Website Resmi: https://lynk.id/nellionel\n"
            "💬 Konsultasi & Bantuan: Hubungi Telegram @Carlendra"
        )
        short_desc = "Elva Tech: Jasa Kreatif, Akun Digital & Info Restock Elva Group. CS: @Carlendra"
        try:
            await application.bot.set_my_description(desc)
            await application.bot.set_my_short_description(short_desc)
        except Exception as e:
            logger.warning(f"Gagal mengatur deskripsi bot Telegram: {e}")

        logger.info("Tombol menu dan deskripsi bot Telegram berhasil dipasang!")
    except Exception as e:
        logger.warning(f"Gagal memasang tombol menu: {e}")


def main() -> None:
    """Fungsi utama menjalankan Telegram Bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("PERINGATAN: TELEGRAM_BOT_TOKEN belum diisi di file .env!")
        return

    print("=" * 60)
    print("🤖 Memulai Bot Telegram Elva Tech...")
    print(f"Owner Chat ID: {OWNER_CHAT_ID or 'Belum disetel (gunakan /id di bot)'}")
    print("Tekan Ctrl+C untuk menghentikan bot.")
    print("=" * 60)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("jasa", jasa_command))
    application.add_handler(CommandHandler("grup", grup_command))
    application.add_handler(CommandHandler("group", grup_command))
    application.add_handler(CommandHandler("restock", restock_command))
    application.add_handler(CommandHandler("id", id_command))

    # Callback query handler (Tombol Interaktif)
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Photo handler (Bukti pembayaran)
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Text message handler (AI Assistant)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
