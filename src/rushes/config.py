"""Rutas de la app y configuración local.

Todo lo que es local de la usuaria vive en %APPDATA%\\Rushes:
  config.json   -> preferencias (sin secretos críticos)
  rclone.conf   -> token OAuth de Google (SENSIBLE, nunca sale de acá)
  logs\\         -> logs técnicos rotativos
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from . import APP_NAME

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mxf", ".avi", ".mkv", ".m4v", ".mts", ".m2ts",
    ".braw", ".r3d", ".crm", ".webm", ".wmv", ".mpg", ".mpeg", ".3gp",
}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".aac", ".m4a", ".flac", ".aif", ".aiff"}
# Formatos RAW que ffprobe no sabe abrir: se validan solo por MD5.
FFPROBE_UNSUPPORTED = {".braw", ".r3d", ".crm"}


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def rclone_conf_path() -> Path:
    return app_data_dir() / "rclone.conf"


def config_path() -> Path:
    return app_data_dir() / "config.json"


def vendor_dir() -> Path:
    """Carpeta con rclone.exe / ffprobe.exe.

    - Empaquetado con PyInstaller: junto al ejecutable (sys._MEIPASS/vendor).
    - En desarrollo: <repo>/vendor.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "vendor"
    return Path(__file__).resolve().parents[2] / "vendor"


def find_binary(name: str) -> str | None:
    """Busca primero en vendor/, después en el PATH (útil para desarrollo)."""
    import shutil

    exe = name + (".exe" if os.name == "nt" else "")
    candidate = vendor_dir() / exe
    if candidate.is_file():
        return str(candidate)
    return shutil.which(name)


@dataclass
class Config:
    disk_label: str = "MATERIAL"
    base_dir: str = "Material"
    # Solo para desarrollo/pruebas: si se setea, ignora el disco y usa esta ruta.
    dest_override_path: str = ""
    rclone_remote: str = "gdrive"
    google_client_id: str = ""
    google_client_secret: str = ""
    transfers: int = 3
    transfers_when_resolve_open: int = 1
    bwlimit_when_resolve_open: str = ""
    min_free_margin_gb: int = 10
    deep_check: bool = False
    extra: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_path()
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)} - {"extra"}
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        cfg.extra = {k: v for k, v in data.items() if k not in known}
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        data = asdict(self)
        extra = data.pop("extra", {})
        data.update(extra)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
