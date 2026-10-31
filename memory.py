"""
memory.py - Pengelolaan riwayat percakapan per pengguna di memori (RAM).
Maksimal menyimpan 10 pesan terakhir per pengguna.
"""

from typing import Dict, List

# Penyimpanan riwayat chat dalam bentuk dictionary: {chat_id: [pesan, ...]}
_chat_history: Dict[str, List[dict]] = {}
MAX_HISTORY = 10


def get_history(chat_id: int | str) -> List[dict]:
    """
    Mengambil riwayat pesan untuk chat_id tertentu.
    Mengembalikan maksimal 10 pesan terakhir.
    """
    key = str(chat_id)
    return _chat_history.get(key, [])


def add_message(chat_id: int | str, role: str, content: str) -> None:
    """
    Menambahkan pesan baru (role: 'user' atau 'assistant') ke riwayat chat.
    Secara otomatis membatasi riwayat agar tidak melebihi MAX_HISTORY (10 pesan).
    """
    key = str(chat_id)
    if key not in _chat_history:
        _chat_history[key] = []

    _chat_history[key].append({"role": role, "content": content})

    # Pangkas riwayat jika melebihi batas maksimal (10 pesan terakhir)
    if len(_chat_history[key]) > MAX_HISTORY:
        _chat_history[key] = _chat_history[key][-MAX_HISTORY:]


def clear_history(chat_id: int | str) -> None:
    """
    Menghapus riwayat percakapan untuk chat_id tertentu (misal saat /start atau reset).
    """
    key = str(chat_id)
    if key in _chat_history:
        _chat_history[key] = []
