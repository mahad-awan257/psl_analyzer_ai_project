"""Local accounts: passwords, lockout, ownership and deletion."""
import os
import sqlite3
import stat

import pytest

from psl_selector.accounts import (LOCK_SECONDS, MAX_FAILURES, SHORT_SECONDS, STAY_SECONDS, AccountError,
                                   AccountStore)


class Clock:
    """A clock the test can move forward."""
    now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def store(tmp_path):
    return AccountStore(tmp_path / "a" / "accounts.db", clock=Clock())


def save(store, uid, name="My XI"):
    store.save_team(uid, name, "Greedy", 700.5, 99.5, ["p1", "p2"])


def test_create_and_login_ignores_username_case(store):
    uid = store.create("  Player_One ", "long password")
    assert store.login("PLAYER_ONE", "long password") == uid
    assert store.username(uid) == "player_one"


def test_password_is_not_stored(store):
    store.create("player1", "secret-words-here")
    assert b"secret-words-here" not in store.path.read_bytes()


def test_same_password_gets_different_hashes(store):
    store.create("player1", "same password"), store.create("player2", "same password")
    rows = sqlite3.connect(store.path).execute("SELECT salt, hash FROM users").fetchall()
    assert rows[0][0] != rows[1][0] and rows[0][1] != rows[1][1]


@pytest.mark.skipif(os.name == "nt", reason="Windows does not use POSIX file modes")
def test_database_is_private_to_this_user(store):
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600


@pytest.mark.parametrize("name", ["ab", "a" * 25, "has space", "semi;colon", "' OR 1=1 --", ""])
def test_bad_usernames_are_rejected(store, name):
    with pytest.raises(AccountError):
        store.create(name, "long password")


@pytest.mark.parametrize("password", ["short", "x" * 129, "player_one"])
def test_bad_passwords_are_rejected(store, password):
    with pytest.raises(AccountError):
        store.create("player_one", password)


def test_username_must_be_unique(store):
    store.create("player1", "long password")
    with pytest.raises(AccountError, match="taken"):
        store.create("PLAYER1", "another password")


def test_wrong_user_and_wrong_password_look_the_same(store):
    store.create("player1", "long password")
    with pytest.raises(AccountError) as a:
        store.login("player1", "wrong password")
    with pytest.raises(AccountError) as b:
        store.login("nobody", "wrong password")
    assert str(a.value) == str(b.value)


def test_lockout_then_recovery(store):
    uid = store.create("player1", "long password")
    for _ in range(MAX_FAILURES):
        with pytest.raises(AccountError, match="Wrong"):
            store.login("player1", "wrong password")
    with pytest.raises(AccountError, match="Too many"):
        store.login("player1", "long password")
    store.clock.now += LOCK_SECONDS + 1
    assert store.login("player1", "long password") == uid


def test_success_resets_the_failure_count(store):
    store.create("player1", "long password")
    for _ in range(3):
        for _ in range(MAX_FAILURES - 1):
            with pytest.raises(AccountError, match="Wrong"):
                store.login("player1", "wrong password")
        store.login("player1", "long password")


def test_change_password(store):
    uid = store.create("player1", "long password")
    with pytest.raises(AccountError):
        store.change_password(uid, "wrong password", "new password 1")
    store.change_password(uid, "long password", "new password 1")
    assert store.login("player1", "new password 1") == uid
    with pytest.raises(AccountError):
        store.login("player1", "long password")


def test_saved_teams_belong_to_one_user(store):
    a, b = store.create("player1", "long password"), store.create("player2", "long password")
    save(store, a)
    assert store.teams(a)[0]["player_ids"] == ["p1", "p2"] and store.teams(b) == []
    store.delete_team(b, store.teams(a)[0]["id"])
    assert len(store.teams(a)) == 1
    store.delete_team(a, store.teams(a)[0]["id"])
    assert store.teams(a) == []


def test_team_names(store):
    uid = store.create("player1", "long password")
    save(store, uid)
    for bad in ("My XI", "  ", "x" * 41):
        with pytest.raises(AccountError):
            save(store, uid, bad)


def test_delete_account_removes_teams(store):
    uid = store.create("player1", "long password")
    save(store, uid)
    with pytest.raises(AccountError):
        store.delete_account(uid, "wrong password")
    store.delete_account(uid, "long password")
    assert store.username(uid) is None and store.teams(uid) == []
    with pytest.raises(AccountError, match="no longer exists"):
        save(store, uid)


def test_a_deleted_id_is_never_reused(store):
    uid = store.create("player1", "long password")
    store.delete_account(uid, "long password")
    assert store.create("player2", "long password") != uid


def test_sessions_expire_and_end(store):
    uid = store.create("player1", "long password")
    short, stay = store.start_session(uid, False), store.start_session(uid, True)
    assert store.session_user(short) == (uid, "player1") == store.session_user(stay)
    store.clock.now += SHORT_SECONDS + 1
    assert store.session_user(short) is None and store.session_user(stay)
    store.end_session(stay)
    assert store.session_user(stay) is None
    again = store.start_session(uid, True)
    store.clock.now += STAY_SECONDS + 1
    assert store.session_user(again) is None


def test_bad_tokens_and_stored_hash(store):
    uid = store.create("player1", "long password")
    token = store.start_session(uid, True)
    assert store.session_user(None) is None and store.session_user("") is None and store.session_user("guess") is None
    assert token.encode() not in store.path.read_bytes()


def test_password_change_ends_other_sessions(store):
    uid, other = store.create("player1", "long password"), store.create("player2", "long password")
    here, elsewhere, theirs = (store.start_session(u, True) for u in (uid, uid, other))
    store.change_password(uid, "long password", "new password 1", keep_token=here)
    assert store.session_user(here) and store.session_user(theirs) and store.session_user(elsewhere) is None


def test_deleting_the_account_ends_its_sessions(store):
    uid = store.create("player1", "long password")
    token = store.start_session(uid, True)
    store.delete_account(uid, "long password")
    assert store.session_user(token) is None
    with pytest.raises(AccountError):
        store.start_session(uid, True)
