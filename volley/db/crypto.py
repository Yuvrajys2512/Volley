from cryptography.fernet import Fernet

from volley.config import FERNET_KEY

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not FERNET_KEY:
            raise RuntimeError(
                "FERNET_KEY is not set — cannot encrypt/decrypt refresh tokens. "
                "Generate one with: python -c "
                "\"from cryptography.fernet import Fernet; "
                'print(Fernet.generate_key().decode())"'
            )
        _fernet = Fernet(FERNET_KEY.encode())
    return _fernet


def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
