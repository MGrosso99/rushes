"""Utilidades específicas de Windows (con fallback para desarrollar en otro SO)."""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager

IS_WINDOWS = os.name == "nt"

BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
CREATE_NO_WINDOW = 0x08000000


def low_priority_popen_kwargs() -> dict:
    """kwargs para subprocess: prioridad baja y sin ventana de consola."""
    if IS_WINDOWS:
        return {"creationflags": BELOW_NORMAL_PRIORITY_CLASS | CREATE_NO_WINDOW}
    return {"preexec_fn": lambda: os.nice(10)}


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


@contextmanager
def keep_awake():
    """Evita la suspensión por inactividad mientras dura el bloque (Windows).

    No impide la suspensión al CERRAR LA TAPA: eso depende de la configuración
    de energía de Windows ("Al cerrar la tapa: No hacer nada").
    Se llama desde el hilo que hace el trabajo (el estado es por hilo).
    """
    if not IS_WINDOWS:
        yield
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def is_process_running(image_name: str) -> bool:
    try:
        if IS_WINDOWS:
            out = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"],
                capture_output=True, text=True, timeout=10,
                creationflags=CREATE_NO_WINDOW,
            ).stdout
            return image_name.lower() in out.lower()
        out = subprocess.run(["pgrep", "-f", image_name], capture_output=True, timeout=10)
        return out.returncode == 0
    except Exception:
        return False


def is_resolve_open() -> bool:
    return is_process_running("Resolve.exe")


def open_path(path: str) -> None:
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
