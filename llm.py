"""
llm.py - Integrasi AI menggunakan OpenAI-compatible client.
LLM Utama: Google Gemini (endpoint OpenAI-compatible).
LLM Cadangan: Groq API (otomatis fallback jika Gemini error/rate limit).
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Muat variabel lingkungan dari file .env
load_dotenv()

logger = logging.getLogger(__name__)

# Konfigurasi LLM dari .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_FILE = os.path.join(BASE_DIR, "prompts", "system_prompt.txt")
MENU_FILE = os.path.join(BASE_DIR, "data", "menu.json")


def load_system_prompt() -> str:
    """
    Membaca template prompts/system_prompt.txt dan menyisipkan data dari menu.json
    serta aturan teknis pelacakan pesanan dan komplain.
    """
    nama_usaha = "Warung Bu Sari"
    menu_content = "{}"

    # Muat data menu.json
    if os.path.exists(MENU_FILE):
        try:
            with open(MENU_FILE, "r", encoding="utf-8") as f:
                menu_data = json.load(f)
                nama_usaha = menu_data.get("nama_usaha", nama_usaha)
                menu_content = json.dumps(menu_data, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Gagal membaca menu.json: {e}")

    # Muat system prompt dasar
    base_prompt = ""
    if os.path.exists(PROMPT_FILE):
        try:
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        except Exception as e:
            logger.error(f"Gagal membaca system_prompt.txt: {e}")

    # Ganti placeholder {nama_usaha}
    base_prompt = base_prompt.replace("{nama_usaha}", nama_usaha)

    # Tambahkan instruksi data toko dan protokol order/eskalasi
    full_prompt = f"""{base_prompt}

DATA RESMI USAHA ({nama_usaha}):
Gunakan data JSON di bawah ini sebagai SATU-SATUNYA acuan informasi menu, harga, jam buka, alamat, ongkir, dan rekening pembayaran:
{menu_content}

PROTOKOL TEKNIS SISTEM (TIDAK DIBACA PELANGGAN):
1. JANGAN PERNAH menghitung total harga di dalam chat teks. Total harga akan dihitung secara otomatis oleh sistem Python.
2. Ketika informasi pesanan pelanggan sudah LENGKAP (mencakup: nama pelanggan, daftar item dan jumlah, metode antar/ambil, alamat pengantaran jika antar, waktu pengantaran/pengambilan, dan catatan jika ada), sertakan blok JSON pesanan di baris paling akhir balasanmu dengan format:
```json:order
{{
  "nama": "Nama Pelanggan",
  "metode": "antar" atau "ambil",
  "alamat": "Alamat Lengkap" atau "-",
  "waktu": "Waktu Antar/Ambil",
  "catatan": "Catatan khusus atau -",
  "items": [
    {{"nama": "Nama Menu Sesuai Menu.json", "qty": 1, "catatan": "-"}}
  ]
}}
```
3. Jika pelanggan komplain (misal makanan bermasalah, pesanan salah, pengantaran terlambat), meminta hal di luar kemampuanmu, atau kamu tidak yakin, tetap tenang, tunjukkan empati singkat, sampaikan bahwa kamu meneruskannya ke pemilik warung, dan sertakan tag eskalasi di akhir:
```json:escalate
{{
  "alasan": "Ringkasan komplain atau permintaan pelanggan"
}}
```
"""
    return full_prompt


def extract_metadata_tags(text: str) -> Tuple[str, Optional[dict], Optional[dict]]:
    """
    Mengekstrak blok ```json:order ... ``` dan ```json:escalate ... ``` dari respons LLM.
    Mengembalikan (cleaned_text, order_data, escalate_data).
    """
    order_data = None
    escalate_data = None
    cleaned_text = text

    # Cari blok json:order
    order_match = re.search(r"```json:order\s*([\s\S]*?)\s*```", cleaned_text, re.IGNORECASE)
    if order_match:
        try:
            order_data = json.loads(order_match.group(1))
            cleaned_text = cleaned_text.replace(order_match.group(0), "").strip()
        except Exception as e:
            logger.warning(f"Gagal mem-parse json:order: {e}")

    # Cari blok json:escalate
    escalate_match = re.search(r"```json:escalate\s*([\s\S]*?)\s*```", cleaned_text, re.IGNORECASE)
    if escalate_match:
        try:
            escalate_data = json.loads(escalate_match.group(1))
            cleaned_text = cleaned_text.replace(escalate_match.group(0), "").strip()
        except Exception as e:
            logger.warning(f"Gagal mem-parse json:escalate: {e}")

    return cleaned_text, order_data, escalate_data


async def call_llm(messages: List[Dict[str, str]]) -> Tuple[Optional[str], str]:
    """
    Memanggil LLM dengan logika fallback otomatis:
    1. Coba Google Gemini via OpenAI-compatible endpoint.
    2. Jika Gemini error / rate limit / gagal, beralih ke Groq.
    3. Jika kedua LLM gagal, mengembalikan (None, "none").
    Mengembalikan (teks_jawaban, provider_yang_berhasil).
    """
    # 1. Coba LLM Utama: Gemini
    if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            logger.info(f"Memanggil Gemini API (model: {GEMINI_MODEL})...")
            gemini_client = AsyncOpenAI(
                api_key=GEMINI_API_KEY,
                base_url=GEMINI_BASE_URL,
                timeout=30.0
            )
            response = await gemini_client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=messages,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            if content:
                logger.info("Sukses mendapatkan balasan dari Gemini.")
                return content, "gemini"
        except Exception as e:
            logger.warning(f"Gemini API gagal ({e}). Mengalihkan otomatis ke Groq...")

    # 2. Coba LLM Cadangan: Groq
    if GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here":
        try:
            logger.info(f"Memanggil Groq API cadangan (model: {GROQ_MODEL})...")
            groq_client = AsyncOpenAI(
                api_key=GROQ_API_KEY,
                base_url=GROQ_BASE_URL,
                timeout=30.0
            )
            response = await groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            if content:
                logger.info("Sukses mendapatkan balasan dari cadangan Groq.")
                return content, "groq"
        except Exception as e:
            logger.error(f"Groq API juga gagal ({e}). Semua LLM tidak merespons.")

    # 3. Keduanya gagal atau kunci API belum diisi
    return None, "none"
