"""Actualización automática desde GitHub Releases (repo público, sin credenciales).

Flujo: al abrir, `check_latest` consulta la última release. Si hay una versión más nueva,
la GUI ofrece "Actualizar": se baja el instalador, se verifica su SHA256 contra el archivo
`.sha256` publicado en la misma release y se ejecuta en modo silencioso. El instalador
cierra Rushes, reemplaza los archivos y la vuelve a abrir. %APPDATA% no se toca.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__
from .winutil import IS_WINDOWS

log = logging.getLogger("rushes.updater")

API = "https://api.github.com/repos/{repo}/releases/latest"
_REPO_RE = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
_INSTALLER_RE = re.compile(r"^Rushes-Setup-(\d+\.\d+\.\d+)\.exe$")


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Release:
    version: str
    installer_url: str
    installer_name: str
    sha256_url: str


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def is_newer(candidate: str, current: str = __version__) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    return bool(a and b and a > b)


def pick_release(data: dict, repo: str) -> Release | None:
    """Extrae instalador + .sha256 de la respuesta de la API. Solo acepta URLs de ESTE repo."""
    if data.get("draft") or data.get("prerelease"):
        return None
    version = data.get("tag_name", "")
    if not parse_version(version):
        return None
    prefix = f"https://github.com/{repo}/releases/download/"
    assets = {a.get("name"): a.get("browser_download_url", "") for a in data.get("assets") or []}
    for name, url in assets.items():
        m = _INSTALLER_RE.match(name or "")
        if not m or not url.startswith(prefix):
            continue
        sha_url = assets.get(name + ".sha256", "")
        if not sha_url.startswith(prefix):
            return None  # sin hash publicado no se actualiza
        return Release(m.group(1), url, name, sha_url)
    return None


def _get(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={
        "User-Agent": f"Rushes/{__version__}",
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 (solo https, validado)


def updates_enabled(repo: str) -> bool:
    """Solo en la app instalada en Windows y con un repo válido configurado."""
    return IS_WINDOWS and getattr(sys, "frozen", False) and bool(_REPO_RE.match(repo or ""))


def check_latest(repo: str) -> Release | None:
    """Devuelve la release si es más nueva que la instalada; None si no hay o falla (silencioso)."""
    if not _REPO_RE.match(repo or ""):
        return None
    try:
        with _get(API.format(repo=repo), timeout=5) as resp:
            data = json.load(resp)
    except Exception as exc:  # noqa: BLE001 — sin internet no es un error para ella
        log.info("No se pudo consultar actualizaciones: %s", exc)
        return None
    release = pick_release(data, repo)
    if release and is_newer(release.version):
        log.info("Hay actualización: %s -> %s", __version__, release.version)
        return release
    return None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, expected_text: str) -> None:
    expected = (expected_text.strip().split() or [""])[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise UpdateError("El hash publicado no es válido.")
    if sha256_of(path) != expected:
        raise UpdateError("El instalador descargado no coincide con el hash publicado.")


def download(release: Release, on_progress: Callable[[float], None] | None = None) -> Path:
    folder = Path(tempfile.mkdtemp(prefix="rushes-update-"))
    target = folder / release.installer_name
    with _get(release.sha256_url) as resp:
        expected = resp.read(512).decode("ascii", "replace")
    with _get(release.installer_url, timeout=30) as resp, open(target, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        for chunk in iter(lambda: resp.read(1024 * 256), b""):
            out.write(chunk)
            done += len(chunk)
            if on_progress and total:
                on_progress(100 * done / total)
    verify_sha256(target, expected)
    log.info("Instalador %s verificado", release.installer_name)
    return target


def launch_installer(path: Path) -> None:
    """Instalación silenciosa; Inno Setup vuelve a abrir Rushes al terminar (ver installer.iss)."""
    subprocess.Popen(
        [str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
        close_fds=True,
    )
