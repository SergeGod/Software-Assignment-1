from tabby.accounts.security import hash_password, hash_token, new_session_token, verify_password


def test_hash_password_stores_algorithm_and_settings():
    stored = hash_password("secret123")
    algorithm, n, r, p, salt, digest = stored.split("$")
    assert (algorithm, n, r, p) == ("scrypt", "16384", "8", "1")
    assert len(bytes.fromhex(salt)) == 16
    assert "secret123" not in stored


def test_verify_password_accepts_right_and_rejects_wrong_password():
    stored = hash_password("secret123")
    assert verify_password("secret123", stored)
    assert not verify_password("secret124", stored)


def test_same_password_gets_a_different_salt_each_time():
    assert hash_password("secret123") != hash_password("secret123")


def test_verify_password_rejects_malformed_or_foreign_hashes():
    assert not verify_password("secret123", "not-a-hash")
    assert not verify_password("secret123", "bcrypt$1$2$3$aa$bb")


def test_session_tokens_are_random_and_hash_is_stable():
    token = new_session_token()
    assert token != new_session_token()
    assert hash_token(token) == hash_token(token)
    assert len(hash_token(token)) == 64
