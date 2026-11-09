"""Hardening: hashed sessions in an HttpOnly cookie, the checks on uploaded files and the security headers, login lockout
that survives a restart, and the health check, backups and request log."""

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.requests import Request

from loomtrack import config
from loomtrack.backup import main as backup_cli
from loomtrack.db import SCHEMA_VERSION, open_db
from loomtrack.deps import client_ip
from loomtrack.main import create_app
from loomtrack.routes.supervisor import _save, sniff_media
from loomtrack.security import hash_secret, hash_token, new_token
from loomtrack.services import backup, lockout
from loomtrack.util import HttpError

WEBM = bytes([0x1A, 0x45, 0xDF, 0xA3]) + bytes(32)
OGG = b"OggS" + bytes(34)
M4A = bytes([0, 0, 0, 0x18]) + b"ftypM4A " + bytes(16)
JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + bytes(16)
PNG = bytes([0x89]) + b"PNG\r\n" + bytes([0x1A]) + b"\n" + bytes(16)
WEBP = b"RIFF" + bytes(4) + b"WEBP" + bytes(8)


def _app(tmp_path, name="app.db", **overrides):
    db = open_db(str(tmp_path / name))
    if not db.execute("SELECT 1 FROM users WHERE login = 'm@x.in'").fetchone():
        db.execute("INSERT INTO users (name, role, login, secret_hash) VALUES ('M', 'merchandiser', 'm@x.in', ?)", (hash_secret("pass1234"),))
    app = create_app(db, today=lambda: "2026-11-05", upload_dir=tmp_path / "uploads", backup_dir=tmp_path / "backups", **overrides)
    return db, app


def _login(client, who="m@x.in", secret="pass1234"):
    return client.post("/api/auth/login", json={"login": who, "secret": secret})


# --- Sessions ---------------------------------------------------------------------------------------------


def test_a_sign_in_gives_an_http_only_cookie_and_the_database_keeps_only_its_hash(tmp_path):
    db, app = _app(tmp_path)
    client = TestClient(app)
    r = _login(client)
    assert r.status_code == 200 and "token" not in r.json()
    assert "httponly" in r.headers["set-cookie"].lower()
    token = r.cookies["loomtrack_session"]
    assert [row["token"] for row in db.execute("SELECT token FROM sessions")] == [hash_token(token)]
    assert token not in json.dumps([list(row) for row in db.execute("SELECT * FROM sessions")])

    assert client.get("/api/auth/me").status_code == 200  # the cookie alone is enough
    other = TestClient(app)
    assert other.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200  # scripts may still send it as a header
    assert other.get("/api/auth/me", headers={"Authorization": f"Bearer {hash_token(token)}"}).status_code == 401  # the stored hash is not a key

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_sessions_saved_in_plain_text_are_hashed_when_the_database_opens_and_nobody_is_signed_out(tmp_path):
    db, _ = _app(tmp_path)
    plain = new_token()
    db.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, 1, '2999-01-01T00:00:00+00:00')", (plain,))
    db.close()

    db, app = _app(tmp_path)
    assert [r["token"] for r in db.execute("SELECT token FROM sessions")] == [hash_token(plain)]
    client = TestClient(app)
    client.cookies.set("loomtrack_session", plain)
    assert client.get("/api/auth/me").status_code == 200
    db.close()
    db, _ = _app(tmp_path)  # opening again changes nothing
    assert [r["token"] for r in db.execute("SELECT token FROM sessions")] == [hash_token(plain)]
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_a_change_the_browser_says_came_from_another_site_is_refused_for_a_cookie_session(tmp_path):
    _, app = _app(tmp_path)
    client = TestClient(app)
    token = _login(client).cookies["loomtrack_session"]
    change = {"current": "wrong-password", "new": "another-password"}
    assert client.post("/api/auth/password", json=change, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/auth/password", json=change, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 400  # got as far as the password check
    assert client.get("/api/auth/me", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200  # reading is not the risk
    script = TestClient(app)
    assert script.post("/api/auth/password", json=change, headers={"Authorization": f"Bearer {token}", "Sec-Fetch-Site": "cross-site"}).status_code == 400


# --- Login lockout ----------------------------------------------------------------------------------------


def test_five_wrong_tries_lock_a_name_and_the_lock_survives_a_restart(tmp_path):
    db, app = _app(tmp_path)
    client = TestClient(app)
    assert [_login(client, secret="nope-nope").status_code for _ in range(5)] == [401] * 5
    locked = _login(client)  # even the right password is refused while locked
    assert locked.status_code == 429 and "5 minutes" in locked.json()["error"]
    db.close()

    db, app = _app(tmp_path)  # the app was restarted
    client = TestClient(app)
    assert _login(client).status_code == 429
    lockout.check(db, "someone-else@x.in", "198.51.100.1")  # other names are not affected
    db.execute("UPDATE login_attempts SET locked_until = 0")  # the five minutes pass
    assert _login(client).status_code == 200
    assert db.execute("SELECT COUNT(*) FROM login_attempts WHERE scope = 'login' AND key = 'm@x.in'").fetchone()[0] == 0  # a right password clears the name


def test_twenty_wrong_tries_from_one_address_lock_that_address_whatever_names_it_tries(tmp_path):
    db, app = _app(tmp_path)
    client = TestClient(app)
    for i in range(20):
        assert _login(client, who=f"nobody{i}@x.in", secret="nope-nope").status_code == 401
    refused = _login(client)  # a real account, the right password, the same address
    assert refused.status_code == 429 and "15 minutes" in refused.json()["error"]

    with pytest.raises(HttpError):
        lockout.check(db, "m@x.in", "testclient")
    lockout.check(db, "m@x.in", "testclient", now=time.time() + 901)  # locked for fifteen minutes, then free
    lockout.check(db, "m@x.in", "198.51.100.77")  # another address is not affected


def test_a_right_password_does_not_wipe_the_addresss_count(tmp_path):
    db, app = _app(tmp_path)
    client = TestClient(app)
    for _ in range(3):
        _login(client, who="ghost@x.in", secret="nope-nope")
    assert _login(client).status_code == 200
    assert db.execute("SELECT fails FROM login_attempts WHERE scope = 'ip'").fetchone()["fails"] == 3


def test_the_address_comes_from_the_proxy_only_when_the_connection_is_from_this_machine():
    def request(peer, **headers):
        return Request({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()], "client": (peer, 1234)})

    assert client_ip(request("127.0.0.1", **{"cf-connecting-ip": "203.0.113.7"})) == "203.0.113.7"
    assert client_ip(request("127.0.0.1", **{"x-forwarded-for": "203.0.113.8, 10.0.0.1"})) == "203.0.113.8"
    assert client_ip(request("198.51.100.9", **{"cf-connecting-ip": "1.2.3.4"})) == "198.51.100.9"  # a caller cannot pick its own address
    assert client_ip(request("127.0.0.1")) == "127.0.0.1"


# --- Uploaded files ---------------------------------------------------------------------------------------


def test_the_type_of_a_photo_or_voice_note_comes_from_its_first_bytes():
    assert sniff_media(JPEG)[:2] == ("image", "image/jpeg")
    assert sniff_media(PNG)[:2] == ("image", "image/png")
    assert sniff_media(WEBP)[:2] == ("image", "image/webp")
    assert sniff_media(WEBM)[:2] == ("audio", "audio/webm")
    assert sniff_media(OGG)[:2] == ("audio", "audio/ogg")
    assert sniff_media(M4A)[:2] == ("audio", "audio/mp4")
    assert sniff_media(b"<html><script>alert(1)</script>") is None
    assert sniff_media(b"") is None


def _upload(data: bytes, claimed: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="whatever", headers={"content-type": claimed})  # type: ignore[arg-type]


def test_a_file_that_is_not_what_it_says_is_refused_and_the_stored_type_is_the_real_one(tmp_path):
    for data, claimed, kind in [(b"<script>alert(1)</script>", "image/jpeg", "image"), (JPEG, "audio/webm", "audio"), (OGG, "image/png", "image"), (b"MZ" + bytes(20), "audio/ogg", "audio")]:
        with pytest.raises(HttpError) as e:
            asyncio.run(_save(_upload(data, claimed), kind, tmp_path))
        assert e.value.status == 400
    assert list(tmp_path.iterdir()) == []  # nothing was written

    path, mime = asyncio.run(_save(_upload(OGG, "image/png"), "audio", tmp_path))  # the phone's claim is ignored
    assert mime == "audio/ogg" and path.endswith(".ogg") and open(path, "rb").read() == OGG


# --- Security headers -------------------------------------------------------------------------------------


def test_every_response_has_the_security_headers_and_a_request_number(tmp_path):
    _, app = _app(tmp_path)
    r = TestClient(app).get("/api/health")
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and "object-src 'none'" in h["content-security-policy"]
    assert "strict-transport-security" not in h  # only over HTTPS
    assert len(h["x-request-id"]) == 12
    assert "strict-transport-security" in TestClient(app, base_url="https://testserver").get("/api/health").headers
    assert "content-security-policy" not in TestClient(app).get("/api/docs").headers  # the docs page loads its own scripts


def test_the_policy_allows_only_the_pages_own_inline_script_by_its_hash_and_follows_a_rebuild(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)

    def build(inline):
        (dist / "index.html").write_text(f'<html><script>{inline}</script><script type="module" src="/assets/app.js"></script></html>', encoding="utf-8")
        os.utime(dist / "index.html", ns=(time.time_ns() + 10**9, time.time_ns() + 10**9 * len(inline)))

    def sha(text):
        return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"

    build("var theme = 1;")
    monkeypatch.setattr(config, "WEB_DIST", dist)
    _, app = _app(tmp_path)
    client = TestClient(app)
    policy = client.get("/").headers["content-security-policy"]
    assert f"script-src 'self' {sha('var theme = 1;')};" in policy and "unsafe-eval" not in policy and "script-src 'self' 'unsafe-inline'" not in policy
    build("var theme = 2; // after a rebuild")
    assert sha("var theme = 2; // after a rebuild") in client.get("/some/page").headers["content-security-policy"]


# --- Health check, request log, backups ---------------------------------------------------------------------


def test_the_health_check_says_what_works_and_fails_when_the_database_is_gone(tmp_path):
    db, app = _app(tmp_path)
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["database"] == "ok" and body["uploads"] == "ok" and body["schema"] == SCHEMA_VERSION
    assert body["translation"] in ("indictrans2", "keywords") and body["speech"] in ("whisper", "off") and body["lastBackup"] is None
    assert "no-store" in r.headers["cache-control"]

    asyncio.run(backup.run_once(db, tmp_path / "backups", tmp_path / "uploads", 3))
    assert TestClient(app).get("/api/health").json()["lastBackup"]

    db.close()
    down = TestClient(app).get("/api/health")
    assert down.status_code == 503 and down.json()["ok"] is False and down.json()["database"] == "unreachable"


def test_each_request_is_logged_with_its_number_and_duration_and_without_secrets(tmp_path, caplog):
    _, app = _app(tmp_path)
    caplog.set_level(logging.INFO, logger="loomtrack.access")
    link = new_token()
    client = TestClient(app)
    r = client.get(f"/api/b/{link}", headers={"Authorization": "Bearer top-secret-session"})
    client.get("/api/media/photos/1?exp=123&sig=abcdef")
    client.get("/api/health")

    lines = [json.loads(rec.getMessage()) for rec in caplog.records if rec.name == "loomtrack.access"]
    first = lines[0]
    assert first["path"] == "/api/b/<link>" and first["status"] == 404 and first["id"] == r.headers["x-request-id"]
    assert isinstance(first["ms"], int) and first["method"] == "GET" and first["ip"] == "testclient"
    assert lines[1]["path"] == "/api/media/photos/1"  # the signed query string is not logged
    assert all(line["path"] != "/api/health" for line in lines)  # a monitor calling every minute would drown the log
    assert link not in caplog.text and "top-secret-session" not in caplog.text and "sig=" not in caplog.text


def test_an_unexpected_error_is_logged_with_its_traceback_and_the_person_gets_the_same_number(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(config, "WEB_DIST", tmp_path / "no-web-app")  # without it the built page's catch-all route answers first
    _, app = _app(tmp_path)

    @app.get("/api/boom")
    async def boom():
        raise RuntimeError("database exploded")

    caplog.set_level(logging.INFO, logger="loomtrack.access")
    r = TestClient(app, raise_server_exceptions=False).get("/api/boom")
    assert r.status_code == 500
    record = next(rec for rec in caplog.records if rec.levelno == logging.ERROR)
    request_id = json.loads(record.getMessage())["id"]
    assert request_id in r.json()["error"] and "database exploded" not in r.text
    assert record.exc_info and "database exploded" in str(record.exc_info[1])


def test_a_backup_copies_the_database_and_the_uploads_and_the_copy_opens(tmp_path):
    db, _ = _app(tmp_path)
    uploads, folder = tmp_path / "uploads", tmp_path / "backups"
    (uploads / "attachments").mkdir(parents=True)
    (uploads / "attachments" / "design.pdf").write_bytes(b"%PDF-1")
    (uploads / "voice.ogg").write_bytes(OGG)

    copy = backup.backup_database(db, folder, keep=3, now=datetime(2026, 11, 9, 2, 0, 0))
    assert copy.name == "daily-20261109-020000.db" and not list(folder.glob("*.part"))
    restored = open_db(str(copy))
    assert restored.execute("SELECT login FROM users").fetchone()["login"] == "m@x.in"
    assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    assert backup.mirror_uploads(uploads, folder) == 2
    assert (folder / "uploads" / "attachments" / "design.pdf").read_bytes() == b"%PDF-1"
    assert backup.mirror_uploads(uploads, folder) == 0  # nothing new: nothing copied
    (uploads / "photo.jpg").write_bytes(JPEG)
    (uploads / "voice.ogg").unlink()
    assert backup.mirror_uploads(uploads, folder) == 1
    assert (folder / "uploads" / "voice.ogg").exists()  # a file removed later is still in the copy


def test_only_the_newest_copies_are_kept_and_other_files_in_the_folder_are_left_alone(tmp_path):
    db, _ = _app(tmp_path)
    folder = tmp_path / "backups"
    folder.mkdir()
    (folder / "before-reset-20261101-090000.db").write_bytes(b"made by the reset button")
    start = datetime(2026, 11, 1, 2, 0, 0)
    for day in range(4):
        backup.backup_database(db, folder, keep=2, now=start + timedelta(days=day))
    assert [p.name for p in backup.snapshots(folder)] == ["daily-20261103-020000.db", "daily-20261104-020000.db"]
    assert (folder / "before-reset-20261101-090000.db").exists()


def test_a_backup_is_due_once_the_newest_copy_is_a_day_old(tmp_path):
    db, _ = _app(tmp_path)
    folder = tmp_path / "backups"
    assert backup.due(folder)  # none yet
    backup.backup_database(db, folder, keep=3)
    assert not backup.due(folder)
    assert backup.due(folder, now=time.time() + 25 * 3600)


def test_the_backup_command_copies_to_the_configured_folder(tmp_path, monkeypatch, capsys):
    db, _ = _app(tmp_path, "live.db")
    db.close()
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "a.jpg").write_bytes(JPEG)
    monkeypatch.setattr(config, "DB_FILE", str(tmp_path / "live.db"))
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "elsewhere")
    backup_cli()
    assert "1 new uploaded file" in capsys.readouterr().out
    copy = backup.snapshots(tmp_path / "elsewhere")[0]
    assert sqlite3.connect(copy).execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert (tmp_path / "elsewhere" / "uploads" / "a.jpg").exists()
