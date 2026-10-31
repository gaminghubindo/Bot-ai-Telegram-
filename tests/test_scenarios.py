"""
tests/test_scenarios.py - Pengujian otomatis untuk semua skenario bot:
1. Tanya menu dan harga
2. Pemesanan lengkap sampai konfirmasi & penyimpanan orders.csv
3. Pertanyaan di luar menu
4. Komplain & eskalasi ke pemilik
5. Fallback LLM (Gemini -> Groq -> Pesan Gangguan)
6. Batasan memori riwayat chat (maksimal 10 pesan)
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Tambahkan direktori root project ke sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm
import memory
import orders


class TestBotScenarios(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Bersihkan memori sebelum setiap tes
        memory.clear_history(12345)
        orders.clear_pending_order(12345)

    def test_scenario_1_menu_and_display(self):
        """Uji Skenario 1: Tanya menu dan kesesuaian data menu.json."""
        menu_text = orders.get_menu_display_text()
        self.assertIn("DAFTAR MENU WARUNG BU SARI", menu_text)
        self.assertIn("Nasi Goreng Spesial", menu_text)
        self.assertIn("18.000", menu_text)
        self.assertIn("Ayam Geprek", menu_text)
        self.assertIn("Es Jeruk Peras", menu_text)
        self.assertIn("Sukajadi", menu_text)

    def test_scenario_2_complete_order_and_calculation(self):
        """
        Uji Skenario 2: Pemesanan lengkap sampai konfirmasi.
        Memastikan total harga dihitung oleh Python dari menu.json,
        BUKAN oleh LLM, dan tersimpan rapi ke data/orders.csv.
        """
        raw_order_from_llm = {
            "nama": "Andi Pratama",
            "metode": "antar",
            "alamat": "Jl. Sukajadi No. 45 Bandung",
            "waktu": "12.30 WIB",
            "catatan": "Jangan terlalu pedas, es teh manisnya dipisah",
            "items": [
                {"nama": "Nasi Goreng Spesial", "qty": 2, "catatan": "Sedang"},
                {"nama": "Es Teh Manis", "qty": 2, "catatan": "Es dipisah"}
            ]
        }

        # 1. Perhitungan oleh kode Python dari data/menu.json
        calculated = orders.calculate_order_total(raw_order_from_llm)

        # Cek item dan subtotal
        # 2x Nasgor (18.000) = 36.000
        # 2x Es Teh (5.000) = 10.000
        # Subtotal = 46.000
        self.assertEqual(calculated["subtotal"], 46000)

        # Area Sukajadi tarif ongkir = 5.000
        self.assertEqual(calculated["ongkir"], 5000)

        # Total Bayar = 46.000 + 5.000 = 51.000
        self.assertEqual(calculated["total_harga"], 51000)

        # 2. Format ringkasan untuk konfirmasi pelanggan
        summary_text = orders.format_order_summary_for_customer(calculated)
        self.assertIn("RINGKASAN PESANAN KAK ANDI PRATAMA", summary_text)
        self.assertIn("Rp51.000", summary_text)
        self.assertIn("Ketik *'ya'* untuk konfirmasi", summary_text)

        # 3. Format notifikasi untuk pemilik toko
        user_info = {"chat_id": 12345, "username": "andipratama", "full_name": "Andi Pratama"}
        owner_recap, order_id = orders.format_owner_order_recap(calculated, 12345, user_info)
        self.assertIn("PESANAN BARU MASUK!", owner_recap)
        self.assertIn("Rp51.000", owner_recap)
        self.assertIn(order_id, owner_recap)

        # 4. Simpan ke orders.csv
        test_csv = os.path.join(orders.BASE_DIR, "data", "test_orders.csv")
        with patch.object(orders, "ORDERS_CSV", test_csv):
            if os.path.exists(test_csv):
                os.remove(test_csv)
            orders.save_order_to_csv(calculated, 12345, order_id, user_info)
            self.assertTrue(os.path.exists(test_csv))

            with open(test_csv, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn(order_id, content)
                self.assertIn("Andi Pratama", content)
                self.assertIn("51000", content)
                self.assertIn("Dikonfirmasi", content)

            if os.path.exists(test_csv):
                os.remove(test_csv)

    def test_scenario_3_out_of_topic_and_persona(self):
        """Uji Skenario 3: System prompt memuat aturan penolakan hal di luar menu."""
        prompt = llm.load_system_prompt()
        self.assertIn("Kalau pelanggan tanya hal di luar urusan usaha ini, tolak dengan ramah", prompt)
        self.assertIn("Warung Bu Sari", prompt)
        self.assertIn("Jangan menyebut dirimu model AI buatan perusahaan tertentu", prompt)

    def test_scenario_4_complaint_and_escalation(self):
        """Uji Skenario 4: Penanganan komplain dan pembuatan pesan eskalasi ke pemilik."""
        customer_user = {
            "chat_id": 998877,
            "username": "customer_marah",
            "full_name": "Budi Santoso"
        }
        reason = "Makanan yang dikirim dingin dan pesanan kurang 1 porsi"
        customer_msg = "Min gimana nih, sotonya dingin dan kerupuknya ga ada!"

        escalation_text = orders.format_owner_escalation(customer_user, reason, customer_msg)
        self.assertIn("NOTIFIKASI CS / KOMPLAIN PELANGGAN", escalation_text)
        self.assertIn("Budi Santoso", escalation_text)
        self.assertIn("998877", escalation_text)
        self.assertIn(reason, escalation_text)
        self.assertIn(customer_msg, escalation_text)

    def test_scenario_5_metadata_extraction(self):
        """Uji ekstraksi tag json:order dan json:escalate dari teks respons LLM."""
        llm_response = (
            "Siap kak Budi! Ini rekap pesanan kakak ya, mohon dicek dulu.\n\n"
            "```json:order\n"
            "{\n"
            '  "nama": "Budi",\n'
            '  "metode": "ambil",\n'
            '  "alamat": "-",\n'
            '  "waktu": "13.00 WIB",\n'
            '  "catatan": "-",\n'
            '  "items": [\n'
            '    {"nama": "Soto Ayam Lamongan", "qty": 1, "catatan": "-"}\n'
            "  ]\n"
            "}\n"
            "```"
        )
        cleaned, order_data, escalate_data = llm.extract_metadata_tags(llm_response)
        self.assertNotIn("json:order", cleaned)
        self.assertEqual(order_data["nama"], "Budi")
        self.assertEqual(order_data["items"][0]["nama"], "Soto Ayam Lamongan")
        self.assertIsNone(escalate_data)

    async def test_scenario_6_llm_fallback_gemini_to_groq(self):
        """Uji Skenario 5a: Jika Gemini gagal/error, otomatis fallback ke Groq."""
        # Mock Gemini gagal, Groq berhasil
        with patch.object(llm, "GEMINI_API_KEY", "mock_gemini_key"), \
             patch.object(llm, "GROQ_API_KEY", "mock_groq_key"):

            # Simulasi AsyncOpenAI
            mock_gemini_client = MagicMock()
            mock_gemini_client.chat.completions.create = AsyncMock(side_effect=Exception("Gemini Rate Limit 429"))

            mock_groq_client = MagicMock()
            mock_groq_resp = MagicMock()
            mock_groq_resp.choices = [MagicMock(message=MagicMock(content="Halo kak dari Groq!"))]
            mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_groq_resp)

            def mock_async_openai(api_key, base_url, timeout=30.0):
                if api_key == "mock_gemini_key":
                    return mock_gemini_client
                return mock_groq_client

            with patch("llm.AsyncOpenAI", side_effect=mock_async_openai):
                content, provider = await llm.call_llm([{"role": "user", "content": "Halo"}])
                self.assertEqual(provider, "groq")
                self.assertEqual(content, "Halo kak dari Groq!")

    async def test_scenario_7_all_llms_failed(self):
        """Uji Skenario 5b: Jika semua LLM gagal, mengembalikan (None, 'none')."""
        with patch.object(llm, "GEMINI_API_KEY", "mock_gemini_key"), \
             patch.object(llm, "GROQ_API_KEY", "mock_groq_key"):

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Semua API Down"))

            with patch("llm.AsyncOpenAI", return_value=mock_client):
                content, provider = await llm.call_llm([{"role": "user", "content": "Halo"}])
                self.assertIsNone(content)
                self.assertEqual(provider, "none")

    def test_scenario_8_memory_limit(self):
        """Uji Skenario 6: Memori riwayat percakapan dibatasi maksimal 10 pesan terakhir."""
        chat_id = 8888
        for i in range(15):
            memory.add_message(chat_id, "user", f"Pesan {i}")

        history = memory.get_history(chat_id)
        self.assertEqual(len(history), 10)
        # Harus pesan 5 sampai 14
        self.assertEqual(history[0]["content"], "Pesan 5")
        self.assertEqual(history[-1]["content"], "Pesan 14")


if __name__ == "__main__":
    unittest.main()
