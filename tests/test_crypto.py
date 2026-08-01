"""Refresh-token encryption. A bug here either leaks tokens in plaintext or
makes every stored token permanently undecryptable."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from volley.db import crypto


def test_round_trip(monkeypatch):
    monkeypatch.setattr(crypto, "FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(crypto, "_fernet", None)

    ciphertext = crypto.encrypt("a-refresh-token")
    assert ciphertext != b"a-refresh-token"
    assert crypto.decrypt(ciphertext) == "a-refresh-token"


def test_missing_key_raises(monkeypatch):
    monkeypatch.setattr(crypto, "FERNET_KEY", "")
    monkeypatch.setattr(crypto, "_fernet", None)

    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        crypto.encrypt("whatever")


def test_wrong_key_cannot_decrypt(monkeypatch):
    monkeypatch.setattr(crypto, "FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(crypto, "_fernet", None)
    ciphertext = crypto.encrypt("secret")

    monkeypatch.setattr(crypto, "FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(crypto, "_fernet", None)

    with pytest.raises(InvalidToken):
        crypto.decrypt(ciphertext)
