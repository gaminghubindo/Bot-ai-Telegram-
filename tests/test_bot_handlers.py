"""
tests/test_bot_handlers.py - Pengujian integrasi handler Telegram:
/start, /menu, /id, callback button clicks, photo upload bukti transfer, dan chat AI.
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
        orders.save_verified_user(112233)

    async def test_start_command(self):
        """Uji /start menampilkan dashboard akun & tombol interaktif."""
        update = MagicMock()
        update.effective_chat.id = 112233
        update.effective_user.first_name = "Lnel"
        update.effective_user.username = "lnel_user"
        update.effective_user.full_name = "Lnel"

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        await main.start_command(update, context)

        context.bot.send_message.assert_called_once()
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        markup = context.bot.send_message.call_args.kwargs["reply_markup"]

        self.assertIn("ACCOUNT", sent_text)
        self.assertIn("112233", sent_text)
        self.assertIsNotNone(markup)

    async def test_menu_command(self):
        """Uji /menu menampilkan dashboard akun."""
        update = MagicMock()
        update.effective_chat.id = 112233
        update.effective_user.username = "lnel_user"
        update.effective_user.full_name = "Lnel"

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        await main.menu_command(update, context)

        context.bot.send_message.assert_called_once()
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("ACCOUNT", sent_text)

    async def test_id_command(self):
        """Uji /id menampilkan informasi chat ID pengguna."""
        update = MagicMock()
        update.effective_chat.id = 112233
        update.effective_user.username = "lnel_user"
        update.effective_user.full_name = "Lnel"

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        await main.id_command(update, context)

        sent_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("112233", sent_text)
        self.assertIn("Lnel", sent_text)

    async def test_callback_navigation_flow(self):
        """Uji alur navigasi tombol callback: view_catalog -> prod -> var -> qty -> pay."""
        chat_id = 112233
        user = MagicMock(username="lnel_user", full_name="Lnel")

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        # 1. Klik view_catalog
        update1 = MagicMock()
        update1.effective_chat.id = chat_id
        update1.effective_user = user
        update1.callback_query.data = "view_catalog"
        update1.callback_query.answer = AsyncMock()
        update1.callback_query.edit_message_text = AsyncMock()

        await main.handle_callback_query(update1, context)
        update1.callback_query.edit_message_text.assert_called_once()
        cat_text = update1.callback_query.edit_message_text.call_args.kwargs["text"]
        self.assertIn("PRODUK TERSEDIA", cat_text)

        # 2. Klik prod:google_gemini_pro
        update2 = MagicMock()
        update2.effective_chat.id = chat_id
        update2.effective_user = user
        update2.callback_query.data = "prod:google_gemini_pro"
        update2.callback_query.answer = AsyncMock()
        update2.callback_query.edit_message_text = AsyncMock()

        await main.handle_callback_query(update2, context)
        update2.callback_query.edit_message_text.assert_called_once()
        prod_text = update2.callback_query.edit_message_text.call_args.kwargs["text"]
        self.assertIn("PILIHAN VARIAN", prod_text)

        # 3. Klik pay:google_gemini_pro:gemini_3bln:1:bca
        update3 = MagicMock()
        update3.effective_chat.id = chat_id
        update3.effective_user = user
        update3.callback_query.data = "pay:google_gemini_pro:gemini_3bln:1:bca"
        update3.callback_query.answer = AsyncMock()
        update3.callback_query.edit_message_text = AsyncMock()

        with patch.object(main, "OWNER_CHAT_ID", "999888"):
            await main.handle_callback_query(update3, context)

        # Pesan instruksi bayar dikirim ke user
        pay_text = update3.callback_query.edit_message_text.call_args.kwargs["text"]
        self.assertIn("PESANAN BERHASIL DIBUAT", pay_text)
        self.assertIn("BCA", pay_text)

        # Notifikasi pesanan dikirim ke owner
        context.bot.send_message.assert_called_once()
        owner_call = context.bot.send_message.call_args.kwargs
        self.assertEqual(owner_call["chat_id"], "999888")
        self.assertIn("PESANAN BARU MASUK!", owner_call["text"])

    async def test_photo_proof_upload(self):
        """Uji pengiriman foto bukti pembayaran oleh pelanggan."""
        chat_id = 112233
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user.username = "lnel_user"
        update.effective_user.full_name = "Lnel"
        photo_obj = MagicMock(file_id="photo_123_abc")
        update.message.photo = [photo_obj]

        context = MagicMock()
        context.bot.send_photo = AsyncMock()
        context.bot.send_message = AsyncMock()

        with patch.object(main, "OWNER_CHAT_ID", "999888"):
            await main.handle_photo(update, context)

        # Pastikan foto diteruskan ke owner
        context.bot.send_photo.assert_called_once()
        owner_photo_call = context.bot.send_photo.call_args.kwargs
        self.assertEqual(owner_photo_call["chat_id"], "999888")
        self.assertEqual(owner_photo_call["photo"], "photo_123_abc")
        self.assertIn("BUKTI PEMBAYARAN BARU DITERIMA!", owner_photo_call["caption"])

        # Dan pesan konfirmasi dikirim ke pelanggan
        context.bot.send_message.assert_called_once()
        cust_call = context.bot.send_message.call_args.kwargs
        self.assertEqual(cust_call["chat_id"], chat_id)
        self.assertIn("Foto bukti pembayaran sudah kami terima", cust_call["text"])

    async def test_stepper_interaction(self):
        """Uji interaktivitas tombol Stepper (+) dan (-) pada layar checkout."""
        chat_id = 112233
        user = MagicMock(username="lnel_user", full_name="Lnel")
        context = MagicMock()

        # Step ke 2 item
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user = user
        update.callback_query.data = "step:google_gemini_pro:gemini_1bln:2"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        await main.handle_callback_query(update, context)

        update.callback_query.answer.assert_called_once()
        toast_text = update.callback_query.answer.call_args.args[0]
        self.assertIn("2 item", toast_text)

        update.callback_query.edit_message_text.assert_called_once()
        edited_text = update.callback_query.edit_message_text.call_args.kwargs["text"]
        self.assertIn("2 item", edited_text)

    async def test_jasa_command_and_detail(self):
        """Uji /jasa dan navigasi detail jasa."""
        chat_id = 112233
        user = MagicMock(username="lnel_user", full_name="Lnel")
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user = user
        update.message.set_reaction = AsyncMock()

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        # Command /jasa
        await main.jasa_command(update, context)
        context.bot.send_message.assert_called_once()
        jasa_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("LAYANAN JASA PROFESIONAL", jasa_text)
        self.assertIn("lynk.id/nellionel", jasa_text)

        # Detail jasa landing page
        update_detail = MagicMock()
        update_detail.effective_chat.id = chat_id
        update_detail.effective_user = user
        update_detail.callback_query.data = "jasa_detail:jasa_landing_page"
        update_detail.callback_query.answer = AsyncMock()
        update_detail.callback_query.edit_message_text = AsyncMock()

        await main.handle_callback_query(update_detail, context)
        update_detail.callback_query.edit_message_text.assert_called_once()
        detail_text = update_detail.callback_query.edit_message_text.call_args.kwargs["text"]
        self.assertIn("LANDING PAGE", detail_text)
        self.assertIn("Rp45.000", detail_text)

    async def test_grup_command_and_callback(self):
        """Uji /grup dan callback view_group untuk Elva Group."""
        chat_id = 112233
        user = MagicMock(username="lnel_user", full_name="Lnel")
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user = user
        update.message.set_reaction = AsyncMock()

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        # Command /grup
        await main.grup_command(update, context)
        context.bot.send_message.assert_called_once()
        grup_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("ELVA GROUP", grup_text)
        self.assertIn("RESTOCK", grup_text)

        # Callback view_group
        update_grp = MagicMock()
        update_grp.effective_chat.id = chat_id
        update_grp.effective_user = user
        update_grp.callback_query.data = "view_group"
        update_grp.callback_query.answer = AsyncMock()
        update_grp.callback_query.edit_message_text = AsyncMock()

        await main.handle_callback_query(update_grp, context)
        update_grp.callback_query.edit_message_text.assert_called_once()
        edit_text = update_grp.callback_query.edit_message_text.call_args.kwargs["text"]
        self.assertIn("ELVA GROUP", edit_text)

    async def test_restock_command_owner(self):
        """Uji perintah /restock oleh pemilik toko."""
        chat_id = "5803366133"
        update = MagicMock()
        update.effective_chat.id = chat_id
        context = MagicMock()
        context.args = ["Gemini", "Pro", "sudah", "restock", "20", "akun!"]
        context.bot.send_message = AsyncMock()

        with patch.object(main, "OWNER_CHAT_ID", "5803366133"):
            await main.restock_command(update, context)

        context.bot.send_message.assert_called_once()
        sent_msg = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("NOTIFIKASI RESTOCK", sent_msg)
        self.assertIn("Gemini Pro sudah restock 20 akun!", sent_msg)


    async def test_gatekeeper_unverified_user(self):
        """Uji gerbang verifikasi Elva Group: user belum gabung diblokir sampai klik check_joined."""
        unverified_id = 778899
        orders.clear_verified_users()

        user = MagicMock(username="newbie", full_name="User Baru")
        update = MagicMock()
        update.effective_chat.id = unverified_id
        update.effective_chat.type = "private"
        update.effective_user = user
        update.message.set_reaction = AsyncMock()
        update.message.text = "Halo bot saya mau beli akun"

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        # 1. User belum gabung coba /start -> Diberi tampilan Gerbang Verifikasi
        await main.start_command(update, context)
        context.bot.send_message.assert_called_once()
        msg_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("AKSES TERKUNCI", msg_text)
        self.assertIn("ELVA GROUP", msg_text)

        # 2. User klik tombol 'Saya Sudah Bergabung' (check_joined)
        update_cb = MagicMock()
        update_cb.effective_chat.id = unverified_id
        update_cb.effective_user = user
        update_cb.callback_query.data = "check_joined"
        update_cb.callback_query.answer = AsyncMock()
        update_cb.callback_query.edit_message_text = AsyncMock()

        await main.handle_callback_query(update_cb, context)
        update_cb.callback_query.edit_message_text.assert_called_once()
        dash_text = update_cb.callback_query.edit_message_text.call_args.kwargs["text"]
        self.assertIn("ACCOUNT", dash_text)

        # 3. Sekarang user sudah terverifikasi
        self.assertTrue(orders.load_verified_users().__contains__(str(unverified_id)))

    async def test_freelance_preview_and_anti_tergocek(self):
        """Uji fitur /freelance: preview job aktif, jaminan anti-tergocek jika kosong, dan alur bayar Rp5.000."""
        chat_id = 112233
        orders.clear_unlocked_freelance_users()
        user = MagicMock(username="freelancer_pro", full_name="Freelancer Pro")
        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_user = user
        update.message.set_reaction = AsyncMock()

        context = MagicMock()
        context.bot.send_message = AsyncMock()

        # 1. Buka /freelance saat ada job aktif -> Tampilkan teaser & tombol bayar Rp5.000
        await main.freelance_command(update, context)
        context.bot.send_message.assert_called_once()
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        markup = context.bot.send_message.call_args.kwargs["reply_markup"]

        self.assertIn("INFORMASI LOWONGAN FREELANCE", sent_text)
        self.assertIn("TERSEDIA", sent_text)
        self.assertIn("Rp5.000", sent_text)

        btn_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        self.assertTrue(any("QRIS" in b for b in btn_texts))

        # 2. Klik Bayar Rp5.000 via QRIS (fl_pay:qris)
        update_pay = MagicMock()
        update_pay.effective_chat.id = chat_id
        update_pay.effective_user = user
        update_pay.callback_query.data = "fl_pay:qris"
        update_pay.callback_query.answer = AsyncMock()
        update_pay.callback_query.message.delete = AsyncMock()
        update_pay.callback_query.edit_message_text = AsyncMock()
        context.bot.send_photo = AsyncMock()

        with patch.object(main, "OWNER_CHAT_ID", "5803366133"):
            await main.handle_callback_query(update_pay, context)

        # Foto QR Code GoPay berhasil dikirim ke pelanggan
        context.bot.send_photo.assert_called_once()
        call_kwargs = context.bot.send_photo.call_args.kwargs
        self.assertEqual(call_kwargs["chat_id"], chat_id)
        self.assertIn("PEMESANAN AKSES INFO FREELANCE", call_kwargs["caption"])
        self.assertIn("Rp5.000", call_kwargs["caption"])
        self.assertIn("GoPay", call_kwargs["caption"])

        # 3. Owner buka akses lewat /unlock 112233
        owner_update = MagicMock()
        owner_update.effective_chat.id = "5803366133"
        context_owner = MagicMock()
        context_owner.args = ["112233"]
        context_owner.bot.send_message = AsyncMock()

        with patch.object(main, "OWNER_CHAT_ID", "5803366133"):
            await main.unlock_command(owner_update, context_owner)

        self.assertTrue(orders.is_freelance_unlocked(chat_id))

        # 4. User buka lagi /freelance -> Sekarang sudah TERBUKA lengkap dengan kontak klien
        context.bot.send_message.reset_mock()
        await main.freelance_command(update, context)
        context.bot.send_message.assert_called_once()
        unlocked_text = context.bot.send_message.call_args.kwargs["text"]
        self.assertIn("AKSES LENGKAP INFO FREELANCER (VIP)", unlocked_text)
        self.assertIn("WhatsApp", unlocked_text)

        # 5. Uji Jaminan Anti-Tergocek: Jika status job kosong, tombol bayar non-aktif
        orders.clear_unlocked_freelance_users()
        fl_data = orders.load_freelance_data()
        for j in fl_data.get("daftar_job", []):
            j["status"] = "non-aktif"
        orders.save_freelance_data(fl_data)

        context.bot.send_message.reset_mock()
        await main.freelance_command(update, context)
        empty_text = context.bot.send_message.call_args.kwargs["text"]
        empty_markup = context.bot.send_message.call_args.kwargs["reply_markup"]

        self.assertIn("SEDANG KOSONG", empty_text)
        self.assertIn("Anti-Tergocek", empty_text)

        empty_btn_texts = [btn.text for row in empty_markup.inline_keyboard for btn in row]
        self.assertFalse(any("Bayar" in b for b in empty_btn_texts))

        # Kembalikan job ke aktif
        for j in fl_data.get("daftar_job", []):
            j["status"] = "aktif"
        orders.save_freelance_data(fl_data)

    async def test_admin_direct_link_and_command(self):
        """Memverifikasi bahwa tombol Hubungi Admin dan perintah /admin langsung mengarah ke t.me/Carlendra."""
        # 1. Cek tombol di main dashboard
        user_info = {"chat_id": "123", "username": "testuser", "full_name": "Test User"}
        _, markup = orders.build_main_dashboard("123", user_info)
        admin_btns = [b for row in markup.inline_keyboard for b in row if "Hubungi Admin" in b.text]
        self.assertEqual(len(admin_btns), 1)
        self.assertEqual(admin_btns[0].url, "https://t.me/Carlendra")

        # 2. Cek handler /admin
        update = MagicMock()
        update.effective_chat.id = "12345"
        update.effective_user.username = "testuser"
        update.effective_user.full_name = "Test User"
        update.message.set_reaction = AsyncMock()
        context = MagicMock()
        context.bot.send_message = AsyncMock()

        with patch.object(main, "OWNER_CHAT_ID", "5803366133"):
            await main.admin_command(update, context)

        # Memastikan mengirim balasan dengan tombol ke @Carlendra
        context.bot.send_message.assert_called()
        call_kwargs = context.bot.send_message.call_args.kwargs
        self.assertIn("@Carlendra", call_kwargs["text"])
        btn_urls = [b.url for row in call_kwargs["reply_markup"].inline_keyboard for b in row if b.url]
        self.assertIn("https://t.me/Carlendra", btn_urls)


    async def test_group_purchase_notification_and_topbuyer(self):
        """Memverifikasi kartu notifikasi NEW PURCHASE ke Elva Group dan perintah /topbuyer."""
        # 1. Cek pembentukan kartu NEW PURCHASE
        sample_order = {
            "items": [{"nama": "Google Pro 3 Bulan", "qty": 1, "harga": 20000}],
            "total_harga": 20000,
            "metode": "QRIS Dinamis"
        }
        card_text, card_markup = orders.build_group_purchase_notification(
            sample_order, "5803366133", "ORD-20261031170109"
        )
        self.assertIn("NEW PURCHASE", card_text)
        self.assertIn("580*****33", card_text)
        self.assertIn("Google Pro 3 Bulan", card_text)
        self.assertIn("Total Pembelian", card_text)

        btn_urls = [b.url for row in card_markup.inline_keyboard for b in row if b.url]
        self.assertTrue(any("start=katalog" in u for u in btn_urls))
        self.assertTrue(any("start=menu" in u for u in btn_urls))

        # 2. Cek broadcast ke grup
        context = MagicMock()
        context.bot.send_message = AsyncMock()

        with patch.dict("os.environ", {"ELVA_GROUP_CHAT_ID": "-100123456789"}):
            await main.broadcast_group_purchase(context, sample_order, "5803366133", "ORD-20261031170109")

        context.bot.send_message.assert_called_once()
        b_kwargs = context.bot.send_message.call_args.kwargs
        self.assertEqual(b_kwargs["chat_id"], -100123456789)
        self.assertIn("NEW PURCHASE", b_kwargs["text"])

        # 3. Cek perintah /topbuyer
        update = MagicMock()
        update.effective_chat.id = "12345"
        update.message.set_reaction = AsyncMock()
        context.bot.send_message.reset_mock()

        await main.topbuyer_command(update, context)
        context.bot.send_message.assert_called_once()
        t_kwargs = context.bot.send_message.call_args.kwargs
        self.assertIn("LEADERBOARD PEMBELIAN TERBANYAK", t_kwargs["text"])

if __name__ == "__main__":
    unittest.main()
