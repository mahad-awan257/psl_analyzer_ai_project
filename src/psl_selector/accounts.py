"""Local accounts and saved teams in a SQLite file on this computer.

Passwords are never stored: each account keeps a random salt and a scrypt hash. The database
lives in data/local/, which git ignores, so no personal data reaches the repository.
This is sign-in for a local app. It is not meant for a public server without HTTPS.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from . import config as C

USERNAME = re.compile(r"[a-z0-9_]{3,24}")
MIN_PASSWORD, MAX_PASSWORD = 8, 128
MAX_FAILURES, LOCK_SECONDS = 5, 300
MAX_TEAMS = 50
STAY_SECONDS = 30 * 24 * 3600     # "Stay logged in"
SHORT_SECONDS = 12 * 3600         # this browser tab only
SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1, "maxmem": 64 * 1024 * 1024, "dklen": 32}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, salt BLOB NOT NULL, hash BLOB NOT NULL,
    failures INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL, method TEXT NOT NULL, score REAL NOT NULL, cost REAL NOT NULL,
    player_ids TEXT NOT NULL, created REAL NOT NULL, UNIQUE (user_id, name));
CREATE TABLE IF NOT EXISTS sessions (
    token_hash BLOB PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires REAL NOT NULL);
"""


class AccountError(ValueError):
    """A problem to show to the person, such as a wrong password."""


def default_path() -> Path:
    """Database location. PSL_DUGOUT_DB overrides it (used by the tests)."""
    return Path(os.environ.get("PSL_DUGOUT_DB") or C.DATA_DIR / "local" / "accounts.db")


def hash_password(password: str, salt: bytes) -> bytes:
    """Slow, salted hash that is expensive to guess."""
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, **SCRYPT)


def hash_token(token: str) -> bytes:
    """Tokens are long and random, so a fast hash is enough."""
    return hashlib.sha256(token.encode("utf-8")).digest()


class AccountStore:
    """Create accounts, check passwords and keep each user's saved teams."""

    def __init__(self, path: Path | None = None, clock=time.time):
        """Open (or create) the database. ``clock`` is replaceable for tests."""
        self.path = Path(path) if path else default_path()
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            # Readable by this computer user only.
            os.close(os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600))
        with closing(self._connect()) as db, db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        """Connection with foreign keys on, so deleting a user deletes their teams."""
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @staticmethod
    def _check_password_rules(username: str, password: str) -> None:
        """Raise AccountError if a new password is not acceptable."""
        if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise AccountError(f"Use a password of {MIN_PASSWORD} to {MAX_PASSWORD} characters.")
        if password.strip().lower() == username:
            raise AccountError("The password cannot be the same as the username.")

    # ------------------------------------------------------------ accounts
    def create(self, username: str, password: str) -> int:
        """Create an account and return its id."""
        username = username.strip().lower()
        if not USERNAME.fullmatch(username):
            raise AccountError("Use 3 to 24 letters, numbers or underscores for the username.")
        self._check_password_rules(username, password)
        salt = secrets.token_bytes(16)
        try:
            with closing(self._connect()) as db, db:
                return db.execute("INSERT INTO users (username, salt, hash, created) VALUES (?, ?, ?, ?)",
                                  (username, salt, hash_password(password, salt), self.clock())).lastrowid
        except sqlite3.IntegrityError as err:
            raise AccountError("That username is taken.") from err

    def login(self, username: str, password: str) -> int:
        """Return the user id, or raise AccountError. Locks after repeated failures."""
        username = username.strip().lower()
        if len(password) > MAX_PASSWORD:
            raise AccountError("Wrong username or password.")
        with closing(self._connect()) as db, db:
            user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user is None:
                hash_password(password, b"0" * 16)  # same work, so timing does not reveal usernames
                raise AccountError("Wrong username or password.")
            now = self.clock()
            if user["locked_until"] > now:
                minutes = int((user["locked_until"] - now) // 60) + 1
                raise AccountError(f"Too many wrong passwords. Try again in {minutes} min.")
            ok = hmac.compare_digest(hash_password(password, user["salt"]), user["hash"])
            if ok:
                db.execute("UPDATE users SET failures = 0, locked_until = 0 WHERE id = ?", (user["id"],))
            else:
                # Counted in SQL so parallel attempts cannot overwrite each other.
                db.execute("UPDATE users SET failures = failures + 1 WHERE id = ?", (user["id"],))
                db.execute("UPDATE users SET locked_until = ?, failures = 0 WHERE id = ? AND failures >= ?",
                           (now + LOCK_SECONDS, user["id"], MAX_FAILURES))
        if not ok:
            raise AccountError("Wrong username or password.")
        return user["id"]

    def username(self, user_id: int) -> str | None:
        """Username for an id, or None if the account no longer exists."""
        with closing(self._connect()) as db:
            row = db.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["username"] if row else None

    # ------------------------------------------------------------ sessions
    def start_session(self, user_id: int, stay: bool) -> str:
        """Create a login session and return its token. Only the token's hash is stored."""
        token = secrets.token_urlsafe(32)
        now = self.clock()
        try:
            with closing(self._connect()) as db, db:
                db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
                db.execute("INSERT INTO sessions (token_hash, user_id, expires) VALUES (?, ?, ?)",
                           (hash_token(token), user_id, now + (STAY_SECONDS if stay else SHORT_SECONDS)))
        except sqlite3.IntegrityError as err:
            raise AccountError("This account no longer exists.") from err
        return token

    def session_user(self, token: str | None) -> tuple[int, str] | None:
        """(id, username) for a live session token, or None."""
        if not token:
            return None
        with closing(self._connect()) as db:
            row = db.execute("SELECT u.id, u.username FROM sessions s JOIN users u ON u.id = s.user_id "
                             "WHERE s.token_hash = ? AND s.expires > ?", (hash_token(token), self.clock())).fetchone()
        return (row["id"], row["username"]) if row else None

    def end_session(self, token: str | None) -> None:
        """Log out one session."""
        if token:
            with closing(self._connect()) as db, db:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))

    def _confirm(self, user_id: int, password: str) -> str:
        """Check the password of a signed-in user (counts toward the lockout)."""
        name = self.username(user_id)
        if name is None:
            raise AccountError("This account no longer exists.")
        self.login(name, password)
        return name

    def change_password(self, user_id: int, old: str, new: str, keep_token: str | None = None) -> None:
        """Replace the password after checking the current one, and log out every other session."""
        name = self._confirm(user_id, old)
        self._check_password_rules(name, new)
        salt = secrets.token_bytes(16)
        with closing(self._connect()) as db, db:
            db.execute("UPDATE users SET salt = ?, hash = ? WHERE id = ?", (salt, hash_password(new, salt), user_id))
            db.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                       (user_id, hash_token(keep_token or "")))

    def delete_account(self, user_id: int, password: str) -> None:
        """Delete the account and its saved teams after checking the password."""
        self._confirm(user_id, password)
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM users WHERE id = ?", (user_id,))

    # --------------------------------------------------------------- teams
    def save_team(self, user_id: int, name: str, method: str, score: float, cost: float,
                  player_ids: list[str]) -> None:
        """Save a team under a name that is unique for this user."""
        name = " ".join(name.split())
        if not 1 <= len(name) <= 40:
            raise AccountError("Give the team a name of up to 40 characters.")
        try:
            with closing(self._connect()) as db, db:
                n = db.execute("SELECT COUNT(*) FROM teams WHERE user_id = ?", (user_id,)).fetchone()[0]
                if n >= MAX_TEAMS:
                    raise AccountError(f"You can save up to {MAX_TEAMS} teams. Delete one first.")
                db.execute("INSERT INTO teams (user_id, name, method, score, cost, player_ids, created) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (user_id, name, method, score, cost, json.dumps(list(player_ids)), self.clock()))
        except sqlite3.IntegrityError as err:
            if self.username(user_id) is None:
                raise AccountError("This account no longer exists.") from err
            raise AccountError("You already have a team with that name.") from err

    def teams(self, user_id: int) -> list[dict]:
        """This user's saved teams, newest first."""
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM teams WHERE user_id = ? ORDER BY created DESC, id DESC",
                              (user_id,)).fetchall()
        return [{**dict(r), "player_ids": json.loads(r["player_ids"])} for r in rows]

    def delete_team(self, user_id: int, team_id: int) -> None:
        """Delete one of this user's own teams."""
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM teams WHERE id = ? AND user_id = ?", (team_id, user_id))
