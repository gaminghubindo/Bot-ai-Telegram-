"""
main.py - Entry point bot Telegram AI untuk UMKM kuliner.
Menggunakan python-telegram-bot (async) dengan integrasi LLM dan manajemen pesanan.
"""

import logging
import os
import re
import sys

# Dukungan UTF-8 di Windows Console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
from telegram import Update, constants
from telegram.ext import (
    Application,
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

# Konfigurasi logging ke konsol
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Kunci rahasia dan konfigurasi dari .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()


async def send_safe_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, text: str) -> None:
    """
    Mengirim pesan dengan Markdown. Jika format Markdown gagal, otomatis kirim sebagai teks biasa.
    """
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.warning(f"Gagal kirim format Markdown ({e}), mengirim sebagai teks biasa...")
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=None
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk perintah /start: Memberikan sapaan ramah kepada pelanggan.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Reset riwayat dan status pesanan sebelumnya jika ada
    memory.clear_history(chat_id)
    orders.clear_pending_order(chat_id)

    nama_panggilan = user.first_name if user else "Kak"
    menu_data = orders.load_menu()
    nama_usaha = menu_data.get("nama_usaha", "Warung Kami")

    greeting = (
        f"Halo {nama_panggilan}! Selamat datang di *{nama_usaha}* 👋\n\n"
        "Aku asisten virtual yang siap bantu kakak pesan makanan, cek menu, info ongkir, "
        "jam operasional, atau tanya-tanya seputar warung kami.\n\n"
        "Mau pesan apa hari ini kak?\n"
        "• Ketik /menu untuk melihat daftar menu lengkap\n"
        "• Atau langsung ketik pesan kakak di sini ya! 😊"
    )

    await send_safe_message(context, chat_id, greeting)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk perintah /menu: Menampilkan daftar menu, harga, dan info toko dari menu.json.
    """
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

    menu_text = orders.get_menu_display_text()
    await send_safe_message(context, chat_id, menu_text)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk perintah /id: Menampilkan Chat ID pengguna agar bisa diisi di OWNER_CHAT_ID.
    """
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
        "💡 *Tips Pemilik Warung:*\n"
        f"Salin angka `{chat_id}` di atas dan masukkan ke file `.env` pada variabel "
        "`OWNER_CHAT_ID` agar bot dapat meneruskan pesanan dan notifikasi penting ke akun ini."
    )

    await send_safe_message(context, chat_id, id_info)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler utama untuk setiap percakapan teks dari pelanggan.
    """
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    user_text = update.message.text.strip()

    # Tampilkan indikator "sedang mengetik"
    await context.bot.send_chat_action(chat_id=chat_id, action=constants.ChatAction.TYPING)

    user_info = {
        "chat_id": chat_id,
        "username": user.username if user else "",
        "full_name": user.full_name if user else "Pelanggan"
    }

    # 1. Cek apakah pengguna sedang memiliki pesanan yang menunggu konfirmasi "ya"
    pending_order = orders.get_pending_order(chat_id)
    clean_lower = user_text.lower().strip()

    if pending_order:
        # Kata kunci persetujuan konfirmasi
        confirm_words = ["ya", "iya", "benar", "betul", "ok", "oke", "siap", "sip", "yes", "deal", "sudah benar"]
        cancel_words = ["tidak", "batal", "bukan", "salah", "ganti", "cancel", "jangan"]

        # Jika pengguna konfirmasi "ya"
        if any(re.search(rf"\b{w}\b", clean_lower) for w in confirm_words):
            # Format rekap untuk pemilik dan buat nomor pesanan
            owner_text, order_id = orders.format_owner_order_recap(pending_order, chat_id, user_info)

            # Simpan data pesanan ke data/orders.csv
            orders.save_order_to_csv(pending_order, chat_id, order_id, user_info)

            # Kirim notifikasi pesanan ke OWNER_CHAT_ID
            if OWNER_CHAT_ID and OWNER_CHAT_ID != "your_chat_id_here":
                try:
                    await send_safe_message(context, OWNER_CHAT_ID, owner_text)
                except Exception as e:
                    logger.error(f"Gagal mengirim notifikasi pesanan ke pemilik: {e}")

            # Balasan konfirmasi sukses ke pelanggan
            menu_data = orders.load_menu()
            info_bayar = menu_data.get("info_pembayaran", {})
            rekening = info_bayar.get("rekening", "BCA: 1234567890 a/n Sari Wahyuni")

            success_reply = (
                f"Alhamdulillah, pesanan kakak sudah kami terima dan dicatat! 🎉\n"
                f"Nomor Pesanan: `{order_id}`\n\n"
                f"Pesanan langsung kami teruskan ke dapur/pemilik warung untuk disiapkan.\n\n"
                f"💳 *Pembayaran:*\n"
                f"• {rekening}\n"
                f"• Atau via QRIS / Tunai saat pesanan sampai.\n"
                f"Jika bayar non-tunai, silakan kirim foto bukti transfer ke sini ya kak.\n\n"
                f"Terima kasih banyak sudah memesan! 😊"
            )

            orders.clear_pending_order(chat_id)
            memory.add_message(chat_id, "user", user_text)
            memory.add_message(chat_id, "assistant", success_reply)

            await send_safe_message(context, chat_id, success_reply)
            return

        # Jika pengguna membatalkan atau ingin mengubah pesanan
        if any(re.search(rf"\b{w}\b", clean_lower) for w in cancel_words):
            orders.clear_pending_order(chat_id)
            cancel_reply = (
                "Baik kak, pesanan sebelumnya dibatalkan. "
                "Ada yang ingin diubah menunya, atau mau pesan menu lainnya? 😊"
            )
            memory.add_message(chat_id, "user", user_text)
            memory.add_message(chat_id, "assistant", cancel_reply)

            await send_safe_message(context, chat_id, cancel_reply)
            return

    # 2. Deteksi langsung komplain keras sebagai jaring pengaman tambahan
    is_direct_complaint = False
    complaint_keywords = [
        "komplain", "kecewa", "basi", "rambut", "lalat", "keracunan",
        "bicara sama pemilik", "bicara sama owner", "kontak bos", "mana pesanan",
        "lama banget", "belum datang", "salah antar"
    ]
    if any(k in clean_lower for k in complaint_keywords):
        is_direct_complaint = True

    # 3. Masukkan pesan pelanggan ke memori
    memory.add_message(chat_id, "user", user_text)

    # Siapkan riwayat pesan untuk dikirim ke LLM
    messages_payload = [
        {"role": "system", "content": load_system_prompt()}
    ]
    messages_payload.extend(memory.get_history(chat_id))

    # Panggil LLM (Gemini dengan fallback otomatis ke Groq)
    reply_text, provider = await call_llm(messages_payload)

    # 4. Tangani jika semua LLM gagal merespons
    if not reply_text:
        fallback_msg = (
            "Duh, lagi ada gangguan nih. Coba kirim lagi sebentar ya, "
            "atau tunggu dibalas langsung sama pemilik."
        )
        # Notifikasi ke pemilik jika bot mengalami kendala teknis / offline
        if OWNER_CHAT_ID and OWNER_CHAT_ID != "your_chat_id_here":
            try:
                alert_text = (
                    "⚠️ *NOTIFIKASI KENDALA BOT*\n"
                    f"Pengguna `{chat_id}` ({user_info['full_name']}) mengirim pesan tetapi "
                    "koneksi LLM (Gemini & Groq) gagal merespons."
                )
                await send_safe_message(context, OWNER_CHAT_ID, alert_text)
            except Exception:
                pass

        await send_safe_message(context, chat_id, fallback_msg)
        return

    # 5. Ekstrak tag teknis dari LLM (json:order atau json:escalate)
    cleaned_reply, raw_order, raw_escalate = extract_metadata_tags(reply_text)

    # 6. Skenario A: LLM mendeteksi data pesanan sudah LENGKAP
    if raw_order and raw_order.get("items"):
        # Hitung total harga & ongkir menggunakan kode Python murni berdasarkan menu.json
        calculated_order = orders.calculate_order_total(raw_order)
        summary_text = orders.format_order_summary_for_customer(calculated_order)

        # Gabungkan ucapan ramah bot dengan ringkasan harga resmi dari Python
        if cleaned_reply:
            full_response = f"{cleaned_reply}\n\n{summary_text}"
        else:
            full_response = summary_text

        # Simpan ke state pesanan yang menunggu konfirmasi "ya"
        orders.set_pending_order(chat_id, calculated_order)

        memory.add_message(chat_id, "assistant", full_response)
        await send_safe_message(context, chat_id, full_response)
        return

    # 7. Skenario B: Pelanggan komplain atau butuh eskalasi ke pemilik
    if raw_escalate or is_direct_complaint:
        reason = (
            raw_escalate.get("alasan")
            if (raw_escalate and isinstance(raw_escalate, dict))
            else "Keluhan / Bantuan Pelanggan"
        )
        if OWNER_CHAT_ID and OWNER_CHAT_ID != "your_chat_id_here":
            escalation_msg = orders.format_owner_escalation(user_info, reason, user_text)
            try:
                await send_safe_message(context, OWNER_CHAT_ID, escalation_msg)
            except Exception as e:
                logger.error(f"Gagal mengirim eskalasi ke pemilik: {e}")

    # 8. Skenario C: Balasan percakapan biasa (tanya menu, alamat, dsb.)
    memory.add_message(chat_id, "assistant", cleaned_reply)
    await send_safe_message(context, chat_id, cleaned_reply)


def main() -> None:
    """
    Fungsi utama untuk menginisialisasi dan menjalankan Telegram Bot.
    """
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("=" * 60)
        print("PERINGATAN: TELEGRAM_BOT_TOKEN belum diisi di file .env!")
        print("Silakan salin .env.example menjadi .env lalu isi token bot Telegram Anda.")
        print("=" * 60)
        return

    print("=" * 60)
    print("🤖 Memulai Bot Telegram AI Kuliner...")
    print(f"Owner Chat ID: {OWNER_CHAT_ID or 'Belum disetel (gunakan /id di bot)'}")
    print("Tekan Ctrl+C untuk menghentikan bot.")
    print("=" * 60)

    # Buat aplikasi Telegram Bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Daftarkan handler perintah
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("id", id_command))

    # Daftarkan handler pesan teks percakapan biasa
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Jalankan bot dengan polling
    application.run_polling()


if __name__ == "__main__":
    main()
