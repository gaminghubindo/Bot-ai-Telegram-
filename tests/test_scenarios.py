"""
tests/test_scenarios.py - Pengujian otomatis logika Toko Digital UMKM:
1. Dashboard utama & perhitungan statistik belanja pengguna
2. Pembuatan keyboard katalog, varian, numpad jumlah, dan instruksi bayar
3. Penyimpanan pesanan ke data/orders.csv
4. Format notifikasi pesanan dan komplain ke pemilik toko
5. Fallback LLM (Gemini -> Groq -> Pesan gangguan)
6. Batasan memori riwayat chat (maksimal 10 pesan)
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm
import memory
import orders


class TestBotScenarios(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        memory.clear_history(12345)
        orders.clear_pending_order(12345)

    def test_scenario_1_menu_and_dashboard(self):
        """Uji Skenario 1: Tampilan Dashboard Akun (User ID, Saldo, Ringkasan)."""
        user_info = {"username": "tester", "full_name": "Testing User"}
        text, markup = orders.build_main_dashboard(12345, user_info)

        self.assertIn("ACCOUNT", text)
        self.assertIn("12345", text)
        self.assertIn("@tester", text)
        self.assertIn("RINGKASAN BELANJA", text)

        # Cek tombol utama
        btn_labels = [btn.text for row in markup.inline_keyboard for btn in row]
        self.assertIn("🪙 Katalog Produk", btn_labels)
        self.assertIn("📦 Pesanan Saya", btn_labels)
        self.assertIn("💳 Info Pembayaran", btn_labels)

    def test_scenario_2_catalog_and_variants(self):
        """Uji Skenario 2: Grid katalog dan pilihan varian produk."""
        # Katalog grid
        cat_text, cat_markup = orders.build_catalog_keyboard()
        self.assertIn("PRODUK TERSEDIA", cat_text)
        cat_btns = [btn.text for row in cat_markup.inline_keyboard for btn in row]
        self.assertTrue(any("Gemini" in b or "Google" in b for b in cat_btns))

        # Pilihan varian Google Gemini Pro
        var_text, var_markup = orders.build_product_variants_keyboard("google_gemini_pro")
        self.assertIn("PILIHAN VARIAN", var_text)
        var_btns = [btn.text for row in var_markup.inline_keyboard for btn in row]
        self.assertTrue(any("Gemini Pro 1 Bulan" in b for b in var_btns))
        self.assertTrue(any("Gemini Pro 3 Bulan" in b for b in var_btns))

    def test_scenario_3_quantity_and_checkout(self):
        """Uji Skenario 3: Pilihan jumlah numpad dan detail checkout pesanan."""
        # Numpad jumlah
        qty_text, qty_markup = orders.build_quantity_keyboard("google_gemini_pro", "gemini_3bln")
        self.assertIn("PILIH JUMLAH", qty_text)
        self.assertIn("Rp20.000", qty_text)

        # Numpad buttons 1..10
        qty_btns = [btn.text for row in qty_markup.inline_keyboard for btn in row]
        self.assertIn("1", qty_btns)
        self.assertIn("2", qty_btns)
        self.assertIn("10", qty_btns)

        # Detail checkout (1 item x 20.000 = 20.000)
        checkout_text, checkout_markup = orders.build_checkout_keyboard("google_gemini_pro", "gemini_3bln", 1)
        self.assertIn("DETAIL PESANAN", checkout_text)
        self.assertIn("Rp20.000", checkout_text)

        # Cek pilihan metode pembayaran
        pay_btns = [btn.text for row in checkout_markup.inline_keyboard for btn in row]
        self.assertTrue(any("QRIS" in b for b in pay_btns))
        self.assertTrue(any("BCA" in b for b in pay_btns))

    def test_scenario_4_payment_instruction_and_csv(self):
        """Uji Skenario 4: Pembentukan instruksi bayar dan pencatatan ke CSV."""
        user_info = {"username": "budi_crypto", "full_name": "Budi Santoso"}
        chat_id = 998877

        test_csv = os.path.join(orders.BASE_DIR, "data", "test_orders.csv")
        with patch.object(orders, "ORDERS_CSV", test_csv):
            if os.path.exists(test_csv):
                os.remove(test_csv)

            pay_text, markup, owner_msg = orders.build_payment_instruction(
                "google_gemini_pro", "gemini_3bln", 2, "bca", chat_id, user_info
            )

            # Cek teks instruksi bayar (2 x 20.000 = 40.000)
            self.assertIn("PESANAN BERHASIL DIBUAT", pay_text)
            self.assertIn("Rp40.000", pay_text)
            self.assertIn("BCA", pay_text)

            # Cek rekap untuk pemilik
            self.assertIn("PESANAN BARU MASUK!", owner_msg)
            self.assertIn("Rp40.000", owner_msg)
            self.assertIn("Budi Santoso", owner_msg)

            # Cek file CSV tersimpan
            self.assertTrue(os.path.exists(test_csv))
            with open(test_csv, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("40000", content)
                self.assertIn("998877", content)

            if os.path.exists(test_csv):
                os.remove(test_csv)

    def test_scenario_5_complaint_and_escalation(self):
        """Uji Skenario 5: Penanganan komplain dan pembuatan pesan eskalasi."""
        customer_user = {
            "chat_id": 998877,
            "username": "customer_marah",
            "full_name": "Budi Santoso"
        }
        reason = "Akun tidak bisa login / password salah"
        customer_msg = "Min tolong dong, akun Netflixnya gabisa login nih!"

        escalation_text = orders.format_owner_escalation(customer_user, reason, customer_msg)
        self.assertIn("NOTIFIKASI CS / KOMPLAIN PELANGGAN", escalation_text)
        self.assertIn("Budi Santoso", escalation_text)
        self.assertIn("998877", escalation_text)
        self.assertIn(reason, escalation_text)
        self.assertIn(customer_msg, escalation_text)

    async def test_scenario_6_llm_fallback_gemini_to_groq(self):
        """Uji Skenario 6: Jika Gemini rate limit/error, otomatis beralih ke Groq."""
        with patch.object(llm, "GEMINI_API_KEY", "mock_gemini_key"), \
             patch.object(llm, "GROQ_API_KEY", "mock_groq_key"):

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
        """Uji Skenario 7: Jika semua LLM gagal, mengembalikan (None, 'none')."""
        with patch.object(llm, "GEMINI_API_KEY", "mock_gemini_key"), \
             patch.object(llm, "GROQ_API_KEY", "mock_groq_key"):

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Semua API Down"))

            with patch("llm.AsyncOpenAI", return_value=mock_client):
                content, provider = await llm.call_llm([{"role": "user", "content": "Halo"}])
                self.assertIsNone(content)
                self.assertEqual(provider, "none")

    def test_scenario_8_memory_limit(self):
        """Uji Skenario 8: Memori riwayat percakapan dibatasi maksimal 10 pesan terakhir."""
        chat_id = 8888
        for i in range(15):
            memory.add_message(chat_id, "user", f"Pesan {i}")

        history = memory.get_history(chat_id)
        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]["content"], "Pesan 5")
        self.assertEqual(history[-1]["content"], "Pesan 14")


if __name__ == "__main__":
    unittest.main()
