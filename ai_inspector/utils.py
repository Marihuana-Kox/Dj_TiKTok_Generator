from cryptography.fernet import Fernet
from django.conf import settings


def get_fernet():
    """Возвращает экземпляр Fernet с ключом из настроек."""
    key = getattr(settings, 'AI_ENCRYPTION_KEY', None)
    if not key:
        raise ValueError(
            "AI_ENCRYPTION_KEY not found in settings. Please add it to .env")
    return Fernet(key.encode())


def encrypt_key(raw_key: str) -> str:
    """Шифрует строку."""
    if not raw_key:
        return ''
    return get_fernet().encrypt(raw_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    """Дешифрует строку."""
    if not encrypted_key:
        return ''
    try:
        return get_fernet().decrypt(encrypted_key.encode()).decode()
    except Exception:
        return None
