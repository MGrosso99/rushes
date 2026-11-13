"""Encuentra el disco externo por nombre de volumen (no por letra)."""
from __future__ import annotations

import os
import shutil
import string
from dataclasses import dataclass
from pathlib import Path

from .winutil import IS_WINDOWS


@dataclass
class DiskInfo:
    root: str          # "E:\\"
    label: str
    filesystem: str    # "NTFS", "exFAT", "FAT32"...
    free_bytes: int
    total_bytes: int

    @property
    def is_fat32(self) -> bool:
        return self.filesystem.upper() in {"FAT32", "FAT"}

    @property
    def is_connected(self) -> bool:
        return os.path.exists(self.root)


class DiskError(RuntimeError):
    """Problema con el disco; mensaje apto para la usuaria."""


def _volume_info(root: str) -> tuple[str, str] | None:
    import ctypes

    label_buf = ctypes.create_unicode_buffer(261)
    fs_buf = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
        ctypes.c_wchar_p(root), label_buf, 261, None, None, None, fs_buf, 261
    )
    if not ok:
        return None
    return label_buf.value, fs_buf.value


def list_volumes() -> list[DiskInfo]:
    if not IS_WINDOWS:
        return []
    import ctypes

    bitmask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
    result = []
    for i, letter in enumerate(string.ascii_uppercase):
        if not bitmask & (1 << i):
            continue
        root = f"{letter}:\\"
        info = _volume_info(root)
        if not info:
            continue
        usage = shutil.disk_usage(root)
        result.append(DiskInfo(root, info[0], info[1], usage.free, usage.total))
    return result


def find_disk(label: str, override_path: str = "") -> DiskInfo:
    """Devuelve el disco con ese nombre de volumen o lanza DiskError."""
    if override_path:
        path = Path(override_path)
        path.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(path)
        return DiskInfo(str(path), label, "override", usage.free, usage.total)

    for disk in list_volumes():
        if disk.label.strip().lower() == label.strip().lower():
            if disk.is_fat32:
                raise DiskError(
                    f"El disco '{disk.label}' está en formato FAT32, que no admite archivos de más de 4 GB. "
                    "Hay que formatearlo en NTFS o exFAT (pedile ayuda a quien te instaló la app)."
                )
            return disk
    raise DiskError(f"No encuentro el disco '{label}'. Conectalo por USB y tocá Reintentar.")
