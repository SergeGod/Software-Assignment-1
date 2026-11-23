import pytest

from tabby.accounts import service
from tabby.errors import Conflict, InvalidInput, NotFound, Unauthorized


def test_sign_up_normalizes_username(conn):
    user = service.sign_up(conn, "  Alice ", " Alice A ", "secret123")
    assert user["username"] == "alice"
    assert user["display_name"] == "Alice A"


def test_username_is_unique_ignoring_case(conn):
    service.sign_up(conn, "alice", "Alice", "secret123")
    with pytest.raises(Conflict):
        service.sign_up(conn, "ALICE", "Other", "secret123")


@pytest.mark.parametrize(
    "username, display_name, password",
    [("a b", "A", "secret123"), ("ab", "A", "secret123"), ("alice", "  ", "secret123"),
     ("alice", "A", "short")],
)
def test_sign_up_rejects_invalid_input(conn, username, display_name, password):
    with pytest.raises(InvalidInput):
        service.sign_up(conn, username, display_name, password)


def test_log_in_with_right_password(conn):
    created = service.sign_up(conn, "alice", "Alice", "secret123")
    assert service.log_in(conn, "ALICE", "secret123") == created


@pytest.mark.parametrize("username, password", [("alice", "wrongpass"), ("nobody", "secret123")])
def test_log_in_fails_the_same_way_for_wrong_password_and_unknown_user(conn, username, password):
    service.sign_up(conn, "alice", "Alice", "secret123")
    with pytest.raises(Unauthorized, match="wrong username or password"):
        service.log_in(conn, username, password)


def test_session_identifies_user_until_logout(conn):
    user = service.sign_up(conn, "alice", "Alice", "secret123")
    token = service.start_session(conn, user["id"], days=30)
    assert service.user_for_session(conn, token) == user
    service.end_session(conn, token)
    assert service.user_for_session(conn, token) is None


def test_only_the_token_hash_is_stored(conn):
    user = service.sign_up(conn, "alice", "Alice", "secret123")
    token = service.start_session(conn, user["id"], days=30)
    stored = [row["token_hash"] for row in conn.execute("SELECT token_hash FROM sessions")]
    assert token not in stored


def test_expired_or_unknown_session_is_rejected(conn):
    user = service.sign_up(conn, "alice", "Alice", "secret123")
    expired = service.start_session(conn, user["id"], days=-1)
    assert service.user_for_session(conn, expired) is None
    assert service.user_for_session(conn, "made-up-token") is None


def test_friendship_is_mutual(conn, users):
    assert service.are_friends(conn, users["alice"], users["bob"])
    assert service.are_friends(conn, users["bob"], users["alice"])
    assert not service.are_friends(conn, users["alice"], users["dave"])
    assert [f["username"] for f in service.list_friends(conn, users["bob"])] == ["alice"]


def test_add_friend_rejects_self_unknown_and_duplicates(conn, users):
    with pytest.raises(InvalidInput):
        service.add_friend(conn, users["alice"], "alice")
    with pytest.raises(NotFound):
        service.add_friend(conn, users["alice"], "ghost")
    with pytest.raises(Conflict):
        service.add_friend(conn, users["bob"], "alice")  # already friends, other direction


def test_get_users_returns_public_profiles_only(conn, users):
    profiles = service.get_users(conn, [users["bob"], users["alice"]])
    assert [p["username"] for p in profiles] == ["alice", "bob"]
    assert all("password_hash" not in p for p in profiles)
    assert service.get_users(conn, []) == []
