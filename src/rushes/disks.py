"""Destino de las descargas: una carpeta elegida por la usuaria, recordada aunque cambie la letra.

La primera vez ella elige la carpeta (por ejemplo `E:\\Rushes`). Se guarda la ruta y el número
de serie del volumen. Si otro día Windows le asigna otra letra al disco (F:, G:...), se busca el
volumen con ese número de serie y se rearma la ruta con la letra nueva.
"""
from __future__ import annotations

import os
import shutil
import string
import tempfile
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
    serial: int = 0

    @property
    def is_fat32(self) -> bool:
        return self.filesystem.upper() in {"FAT32", "FAT"}

    @property
    def is_connected(self) -> bool:
        return os.path.exists(self.root)

    @property
    def is_system_drive(self) -> bool:
        system = os.environ.get("SystemDrive", "C:").upper()
        return IS_WINDOWS and self.root.upper().startswith(system)

    @property
    def display_name(self) -> str:
        letter = self.root.rstrip("\\/")
        return f"{self.label} ({letter})" if self.label else letter


class DiskError(RuntimeError):
    """Problema con el destino; mensaje apto para la usuaria."""


class NeedsDestination(DiskError):
    """Todavía no se eligió dónde guardar."""


def _volume_info(root: str) -> tuple[str, str, int] | None:
    import ctypes
    from ctypes import wintypes

    label_buf = ctypes.create_unicode_buffer(261)
    fs_buf = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD(0)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
        ctypes.c_wchar_p(root), label_buf, 261, ctypes.byref(serial), None, None, fs_buf, 261
    )
    if not ok:
        return None
    return label_buf.value, fs_buf.value, serial.value


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
        result.append(DiskInfo(root, info[0], info[1], usage.free, usage.total, info[2]))
    return result


def volume_of(path: Path) -> DiskInfo:
    """Información del volumen que contiene `path` (que debe existir)."""
    usage = shutil.disk_usage(path)
    if IS_WINDOWS:
        root = Path(path).anchor
        info = _volume_info(root)
        if info:
            return DiskInfo(root, info[0], info[1], usage.free, usage.total, info[2])
    return DiskInfo(Path(path).anchor or str(path), "", "", usage.free, usage.total, 0)


def check_destination(path: str | Path) -> DiskInfo:
    """Valida una carpeta elegida: existe, se puede escribir y no es FAT32."""
    p = Path(path)
    if not p.is_dir():
        raise DiskError("Esa carpeta no existe. Elegí otra.")
    try:
        with tempfile.NamedTemporaryFile(dir=p, prefix=".rushes-test-"):
            pass
    except OSError:
        raise DiskError("No se puede guardar en esa carpeta (sin permiso o disco protegido). Elegí otra.")
    info = volume_of(p)
    if info.is_fat32:
        raise DiskError(
            f"El disco {info.display_name} está en formato FAT32, que no admite archivos de más de 4 GB. "
            "Elegí otro disco o hay que formatearlo en NTFS o exFAT (pedile ayuda a quien te instaló la app)."
        )
    return info


def resolve_destination(
    dest_folder: str = "",
    serial: int = 0,
    label: str = "",
    legacy_disk_label: str = "",
    legacy_base_dir: str = "Rushes",
    override_path: str = "",
) -> tuple[DiskInfo, Path]:
    """Devuelve (volumen, carpeta base) o lanza DiskError / NeedsDestination.

    Orden: override de desarrollo → carpeta elegida → misma carpeta en otra letra (por serie)
    → configuración vieja por nombre de volumen → pedir que elija.
    """
    if override_path:
        p = Path(override_path)
        p.mkdir(parents=True, exist_ok=True)
        return volume_of(p), p

    if dest_folder:
        p = Path(dest_folder)
        if p.is_dir():
            return check_destination(p), p
        if serial:
            for vol in list_volumes():
                if vol.serial == serial:
                    moved = Path(vol.root) / p.relative_to(p.anchor)
                    moved.mkdir(parents=True, exist_ok=True)
                    return check_destination(moved), moved
        name = label or p.anchor.rstrip("\\/") or str(p)
        raise DiskError(
            f"No encuentro el disco donde guardás el material ({name}). "
            "Conectalo y tocá Reintentar, o elegí otra carpeta."
        )

    if legacy_disk_label:
        for vol in list_volumes():
            if vol.label.strip().lower() == legacy_disk_label.strip().lower():
                p = Path(vol.root) / legacy_base_dir
                p.mkdir(parents=True, exist_ok=True)
                return check_destination(p), p

    raise NeedsDestination("Elegí dónde guardar el material: tocá «Elegir carpeta».")
