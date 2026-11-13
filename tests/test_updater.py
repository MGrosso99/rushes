import hashlib

import pytest

from rushes import updater
from rushes.updater import UpdateError, is_newer, parse_version, pick_release, verify_sha256

REPO = "matias/rushes"
BASE = f"https://github.com/{REPO}/releases/download/v0.2.0/"


def _release(**over):
    data = {"tag_name": "v0.2.0", "draft": False, "prerelease": False, "assets": [
        {"name": "Rushes-Setup-0.2.0.exe", "browser_download_url": BASE + "Rushes-Setup-0.2.0.exe"},
        {"name": "Rushes-Setup-0.2.0.exe.sha256", "browser_download_url": BASE + "Rushes-Setup-0.2.0.exe.sha256"},
    ]}
    data.update(over)
    return data


def test_versions():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("1.2") is None
    assert is_newer("v0.2.0", "0.1.0") and is_newer("0.10.0", "0.9.9")
    assert not is_newer("v0.1.0", "0.1.0") and not is_newer("basura", "0.1.0")


def test_pick_release_ok():
    r = pick_release(_release(), REPO)
    assert r.version == "0.2.0" and r.installer_url.endswith(".exe")


def test_rejects_other_repo_urls():
    data = _release()
    data["assets"][0]["browser_download_url"] = "https://evil.example/Rushes-Setup-0.2.0.exe"
    assert pick_release(data, REPO) is None


def test_requires_sha256_asset():
    data = _release()
    data["assets"].pop()
    assert pick_release(data, REPO) is None


def test_skips_prerelease():
    assert pick_release(_release(prerelease=True), REPO) is None


def test_verify_sha256(tmp_path):
    f = tmp_path / "x.exe"
    f.write_bytes(b"instalador")
    good = hashlib.sha256(b"instalador").hexdigest()
    verify_sha256(f, f"{good}  Rushes-Setup-0.2.0.exe\n")
    with pytest.raises(UpdateError):
        verify_sha256(f, "0" * 64)
    with pytest.raises(UpdateError):
        verify_sha256(f, "no-es-un-hash")


def test_disabled_outside_installed_windows_app():
    assert not updater.updates_enabled(REPO)  # tests no corren "frozen" en Windows
    assert not updater.updates_enabled("")
    assert not updater.updates_enabled("no valido/../x")


def test_check_latest_offline_is_silent(monkeypatch):
    def boom(*a, **k):
        raise OSError("sin internet")
    monkeypatch.setattr(updater, "_get", boom)
    assert updater.check_latest(REPO) is None
