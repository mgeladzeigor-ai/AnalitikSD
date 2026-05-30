# tests/auth/test_password.py
from analitiksd.auth.password import hash_password, verify_password


def test_hash_differs_from_plaintext():
    h = hash_password("secret123")
    assert h != "secret123"
    assert isinstance(h, str)


def test_verify_accepts_correct_password():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True


def test_verify_rejects_wrong_password():
    h = hash_password("secret123")
    assert verify_password("wrong", h) is False


def test_hash_is_salted_unique():
    assert hash_password("same") != hash_password("same")


def test_verify_rejects_empty_against_real_hash():
    # пустой пароль не должен проходить против хеша непустого пароля (security footgun)
    h = hash_password("non-empty")
    assert verify_password("", h) is False


def test_verify_rejects_malformed_hash():
    # битый/некорректный хеш -> False, без исключения наружу
    assert verify_password("secret123", "not-a-bcrypt-hash") is False


def test_hash_rejects_password_over_72_bytes():
    # явная ValueError вместо сырой ошибки bcrypt / 500 в будущем flow регистрации
    import pytest

    with pytest.raises(ValueError):
        hash_password("a" * 73)


def test_hash_accepts_exactly_72_bytes():
    h = hash_password("a" * 72)
    assert verify_password("a" * 72, h) is True
