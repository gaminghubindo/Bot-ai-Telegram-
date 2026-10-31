"""
tests/test_bot_handlers.py - Pengujian integrasi handler Telegram:
/start, /menu, /id, alur percakapan, konfirmasi pesanan, dan komplain.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
import memory
import orders


class TestBotHandlers(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        memory.clear_history(112233)
        orders.clear_pending_order(112233)

    async def test_start_command(self):
        update = MagicMock()
        update.effective_chat.id = 112233
        update.effective_user.first_name = "Budi"

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        await main.start_command(update, context)

        # Verifikasi pesan selamat datang dikirim
        context.bot.send_message.assert_called_once()
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("Halo Budi!", sent_text)
        self.assertIn("Warung Bu Sari", sent_text)
        self.assertIn("/menu", sent_text)

    async def test_menu_command(self):
        update = MagicMock()
        update.effective_chat.id = 112233

        context = MagicMock()
        context.bot.send_chat_action = AsyncMock()
        context.bot.send_message = AsyncMock()

        await main.menu_command(update, context)

        context.bot.send_chat_action.assert_called_once()
        context.bot.send_message.assert_called_once()
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("DAFTAR MENU WARUNG BU SARI", sent_text)
        self.assertIn("Rp18.000", sent_text)

    async def test_id_command(self):
        update = MagicMock()
        update.effective_chat.id = 112233
        update.effective_user.username = "budisantoso"
        update.effective_user.full_name = "Budi Santoso"

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        await main.id_command(update, context)

        sent_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("112233", sent_text)
        self.assertIn("Budi Santoso", sent_text)
        self.assertIn("@budisantoso", sent_text)

    async def test_order_flow_to_confirmation(self):
        """Simulasi alur order dari rekomendasi LLM hingga konfirmasi 'ya' pelanggan."""
        chat_id = 112233
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.username = "budisantoso"
        update.effective_user.full_name = "Budi Santoso"
        update.message.text = "ya"

        # Simulasikan ada pesanan yang sedang menunggu konfirmasi
        pending_order = {
            "nama": "Budi Santoso",
            "metode": "Antar (Delivery)",
            "alamat": "Jl. Sukajadi No. 10",
            "area_antar": "Sukajadi",
            "waktu": "13.00 WIB",
            "catatan": "Pedas manis",
            "items": [
                {
                    "nama": "Nasi Goreng Spesial",
                    "qty": 1,
                    "harga_satuan": 18000,
                    "subtotal": 18000,
                    "catatan": "-"
                }
            ],
            "subtotal": 18000,
            "ongkir": 5000,
            "total_harga": 23000
        }
        orders.set_pending_order(chat_id, pending_order)

        context = MagicMock()
        context.bot.send_chat_action = AsyncMock()
        context.bot.send_message = AsyncMock()

        with patch.object(main, "OWNER_CHAT_ID", "999888"):
            await main.handle_message(update, context)

        # Pastikan 2 pesan terkirim: 1 ke pemilik (rekap) dan 1 ke pelanggan (konfirmasi)
        self.assertEqual(context.bot.send_message.call_count, 2)

        # Cek rekap pemilik
        owner_call = [
            c for c in context.bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == "999888"
        ][0]
        self.assertIn("PESANAN BARU MASUK!", owner_call.kwargs["text"])
        self.assertIn("Rp23.000", owner_call.kwargs["text"])

        # Cek pesan sukses ke pelanggan
        cust_call = [
            c for c in context.bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == chat_id
        ][0]
        self.assertIn("pesanan kakak sudah kami terima dan dicatat!", cust_call.kwargs["text"])

        # Pastikan state pending order sudah di-clear
        self.assertIsNone(orders.get_pending_order(chat_id))

    async def test_complaint_escalation(self):
        """Simulasi pesan komplain dari pelanggan yang diteruskan ke pemilik."""
        chat_id = 112233
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.username = "budisantoso"
        update.effective_user.full_name = "Budi Santoso"
        update.message.text = "Min, makanannya basi nih tolong ganti dong!"

        context = MagicMock()
        context.bot.send_chat_action = AsyncMock()
        context.bot.send_message = AsyncMock()

        mock_llm_reply = (
            "Duh, maaf banget ya kak atas ketidaknyamanannya! 🙏 "
            "Hal ini langsung aku infokan ke pemilik warung ya kak.\n\n"
            "```json:escalate\n"
            "{\n"
            '  "alasan": "Komplain makanan basi dan minta ganti"\n'
            "}\n"
            "```"
        )

        with patch.object(main, "OWNER_CHAT_ID", "999888"), \
             patch("main.call_llm", AsyncMock(return_value=(mock_llm_reply, "gemini"))):
            await main.handle_message(update, context)

        # Harus ada notifikasi eskalasi ke OWNER_CHAT_ID
        owner_call = [
            c for c in context.bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == "999888"
        ][0]
        self.assertIn("NOTIFIKASI CS / KOMPLAIN PELANGGAN", owner_call.kwargs["text"])
        self.assertIn("Budi Santoso", owner_call.kwargs["text"])
        self.assertIn("makanannya basi nih", owner_call.kwargs["text"])

        # Dan pesan yang dikirim ke pelanggan bersih dari tag JSON
        cust_call = [
            c for c in context.bot.send_message.call_args_list
            if c.kwargs.get("chat_id") == chat_id
        ][0]
        self.assertNotIn("json:escalate", cust_call.kwargs["text"])
        self.assertIn("maaf banget ya kak", cust_call.kwargs["text"])


if __name__ == "__main__":
    unittest.main()
