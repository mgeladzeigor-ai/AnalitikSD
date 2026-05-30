# tests/auth/test_tokens.py
import jwt
import pytest

from analitiksd.auth.tokens import create_access_token, decode_access_token


def test_roundtrip_returns_subject(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    token = create_access_token("42")
    assert decode_access_token(token) == "42"


def test_expired_token_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    token = create_access_token("42", expires_minutes=-1)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_tampered_signature_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-key")
    token = create_access_token("42")
    monkeypatch.setenv("JWT_SECRET", "different-secret")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
