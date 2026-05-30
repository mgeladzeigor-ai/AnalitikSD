# tests/auth/test_tokens.py
import jwt
import pytest

from analitiksd.auth.tokens import create_access_token, decode_access_token

# >=32 байта: HS256 по RFC 7518 требует ключ не короче длины хеша,
# иначе PyJWT шлёт InsecureKeyLengthWarning.
TEST_SECRET = "test-secret-key-at-least-32-bytes!!"


def test_roundtrip_returns_subject(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    token = create_access_token("42")
    assert decode_access_token(token) == "42"


def test_expired_token_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    token = create_access_token("42", expires_minutes=-1)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_tampered_signature_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    token = create_access_token("42")
    monkeypatch.setenv("JWT_SECRET", "different-secret-also-32-bytes-long")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_missing_sub_claim_raises(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    token = jwt.encode({"foo": "bar"}, TEST_SECRET, algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)
