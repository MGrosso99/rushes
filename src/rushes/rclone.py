"""Wrapper de rclone: login, tamaño, copia con progreso y verificación MD5.

Reglas de seguridad:
  - Siempre `copy`, nunca `sync`/`move`/`delete`: no se borra nada ni en Drive ni en el disco.
  - Scope OAuth `drive.readonly`.
  - Argumentos como lista (sin shell=True). El folder_id ya viene validado por drive_link.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .drive_link import DriveFolder
from .winutil import CREATE_NO_WINDOW, IS_WINDOWS, low_priority_popen_kwargs

log = logging.getLogger("rushes.rclone")


class RcloneError(RuntimeError):
    """Error de rclone ya traducido a un mensaje para la usuaria."""

    def __init__(self, user_message: str, technical: str = ""):
        super().__init__(user_message)
        self.technical = technical


_FRIENDLY = [
    (("invalid_grant", "token expired", "couldn't fetch token", "oauth2: cannot fetch token",
      "empty token", "didn't find section in config file"),
     "La conexión con Google venció o no está configurada. Tocá 'Conectar Google' y volvé a iniciar sesión."),
    (("directory not found", "error 404", "notfound", "file not found", "dir not found"),
     "No encontré la carpeta. Revisá que el link esté completo y que la carpeta esté compartida con tu cuenta de Google."),
    (("insufficientfilepermissions", "error 403", "forbidden", "permission"),
     "Tu cuenta no tiene permiso para ver esa carpeta. Pedile al filmmaker que te la comparta."),
    (("no space left", "there is not enough space", "disk full"),
     "Se llenó el disco. Liberá espacio y volvé a intentar; lo que ya bajó no se vuelve a descargar."),
    (("no such host", "dial tcp", "network is unreachable", "connection refused", "i/o timeout",
      "tls handshake timeout"),
     "Se cortó la conexión (sin internet, o la compu se suspendió). Volvé a tocar Revisar y Descargar con el mismo link: retoma donde quedó."),
    (("ratelimitexceeded", "userratelimitexceeded", "quota"),
     "Google limitó la descarga por un rato. Esperá unos minutos y volvé a intentar."),
]


def friendly_error(technical: str) -> str:
    low = technical.lower()
    for needles, message in _FRIENDLY:
        if any(n in low for n in needles):
            return message
    return "Algo falló en la descarga. Probá de nuevo; si sigue pasando, mandá el reporte desde el menú Ayuda."


@dataclass
class Progress:
    bytes_done: int = 0
    bytes_total: int = 0
    speed: float = 0.0
    eta: int | None = None
    files_done: int = 0
    files_total: int = 0
    errors: int = 0
    current: list[tuple[str, int]] = field(default_factory=list)  # (nombre, %)

    @property
    def percent(self) -> float:
        return 100.0 * self.bytes_done / self.bytes_total if self.bytes_total else 0.0


def parse_stats_line(line: str) -> Progress | None:
    """Parsea una línea de --use-json-log; devuelve Progress si trae stats."""
    try:
        rec = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    stats = rec.get("stats") if isinstance(rec, dict) else None
    if not isinstance(stats, dict):
        return None
    return Progress(
        bytes_done=int(stats.get("bytes", 0) or 0),
        bytes_total=int(stats.get("totalBytes", 0) or 0),
        speed=float(stats.get("speed", 0) or 0),
        eta=stats.get("eta"),
        files_done=int(stats.get("transfers", 0) or 0),
        files_total=int(stats.get("totalTransfers", 0) or 0),
        errors=int(stats.get("errors", 0) or 0),
        current=[
            (t.get("name", "?"), int(t.get("percentage", 0) or 0))
            for t in (stats.get("transferring") or [])
        ],
    )


@dataclass
class CheckResult:
    ok: list[str] = field(default_factory=list)          # MD5 coincide
    missing: list[str] = field(default_factory=list)     # está en Drive, no en el disco
    differ: list[str] = field(default_factory=list)      # MD5 distinto
    errors: list[str] = field(default_factory=list)      # no se pudo leer

    @property
    def all_ok(self) -> bool:
        return not (self.missing or self.differ or self.errors)


def parse_combined(lines: Iterable[str]) -> CheckResult:
    """Parsea la salida de `rclone check --combined -`."""
    result = CheckResult()
    buckets = {"=": result.ok, "-": result.missing, "*": result.differ, "!": result.errors}
    for raw in lines:
        line = raw.rstrip("\r\n")
        if len(line) < 3 or line[1] != " ":
            continue
        bucket = buckets.get(line[0])  # "+" (solo en disco, ej. _reporte) se ignora
        if bucket is not None:
            bucket.append(line[2:])
    return result


class Rclone:
    def __init__(self, exe: str | list[str], config_file: Path, remote: str = "gdrive"):
        # exe puede ser una lista (ej. [python, fake_rclone.py]) para los tests en cualquier SO.
        self.cmd = [exe] if isinstance(exe, str) else list(exe)
        self.config_file = config_file
        self.remote = remote

    # ---------- helpers ----------
    def _base(self) -> list[str]:
        return [*self.cmd, "--config", str(self.config_file)]

    def _src(self) -> str:
        return f"{self.remote}:"

    @staticmethod
    def _folder_flags(folder: DriveFolder) -> list[str]:
        flags = ["--drive-root-folder-id", folder.folder_id, "--drive-skip-gdocs"]
        if folder.resource_key:
            flags += ["--drive-resource-key", folder.resource_key]
        return flags

    @staticmethod
    @contextmanager
    def _only(files: list[str] | None, force: bool = False):
        """Flags para limitar la operación a una lista de archivos (reintentos)."""
        if not files:
            yield []
            return
        fd, path = tempfile.mkstemp(prefix="rushes-", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write("\n".join(files) + "\n")
            yield ["--files-from-raw", path] + (["--ignore-times"] if force else [])
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _run(self, args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
        log.debug("rclone %s", " ".join(args[3:]))  # no loguea la ruta del config
        kwargs = {"creationflags": CREATE_NO_WINDOW} if IS_WINDOWS else {}
        return subprocess.run(
            self._base() + args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, stdin=subprocess.DEVNULL, **kwargs,
        )

    # ---------- cuenta ----------
    def is_connected(self) -> bool:
        if not self.config_file.exists():
            return False
        proc = self._run(["listremotes"])
        return f"{self.remote}:" in proc.stdout.split()

    def connect(self, client_id: str = "", client_secret: str = "") -> None:
        """Crea (o recrea) el remote. Abre el navegador para que ella inicie sesión."""
        if self.config_file.exists():
            self._run(["config", "delete", self.remote])
        args = ["config", "create", self.remote, "drive", "scope=drive.readonly"]
        if client_id:
            args.append(f"client_id={client_id}")
        if client_secret:
            args.append(f"client_secret={client_secret}")
        proc = self._run(args, timeout=600)  # espera a que termine el login en el navegador
        if proc.returncode != 0 or not self.is_connected():
            raise RcloneError("No se pudo conectar con Google. Probá de nuevo.", proc.stderr)
        log.info("Remote %s conectado", self.remote)

    # ---------- operaciones ----------
    def size(self, folder: DriveFolder) -> tuple[int, int]:
        """(cantidad de archivos, bytes totales) de la carpeta en Drive."""
        proc = self._run(["size", self._src(), "--json"] + self._folder_flags(folder), timeout=300)
        if proc.returncode != 0:
            raise RcloneError(friendly_error(proc.stderr), proc.stderr)
        data = json.loads(proc.stdout)
        return int(data.get("count", 0)), int(data.get("bytes", 0))

    def copy(
        self,
        folder: DriveFolder,
        dest: Path,
        transfers: int,
        on_progress: Callable[[Progress], None],
        cancel: threading.Event,
        bwlimit: str = "",
        only_files: list[str] | None = None,
    ) -> None:
        """Copia Drive -> disco. Con only_files fuerza re-descargar solo esos (reintento)."""
        with self._only(only_files, force=True) as only:
            self._copy(folder, dest, transfers, on_progress, cancel, bwlimit, only)

    def _copy(self, folder, dest, transfers, on_progress, cancel, bwlimit, only) -> None:
        args = self._base() + [
            "copy", self._src(), str(dest),
            *self._folder_flags(folder),
            "--transfers", str(max(1, transfers)),
            "--checkers", "4",
            "--retries", "5",
            "--low-level-retries", "20",
            "--use-json-log", "--stats", "1s", "--stats-log-level", "NOTICE",
            "--log-level", "NOTICE",
            *only,
        ]
        if bwlimit:
            args += ["--bwlimit", bwlimit]
        log.info("Copiando a %s (transfers=%s, bwlimit=%s)", dest, transfers, bwlimit or "-")

        proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", **low_priority_popen_kwargs(),
        )
        error_lines: list[str] = []
        assert proc.stderr is not None
        for line in proc.stderr:
            if cancel.is_set():
                proc.terminate()
                break
            progress = parse_stats_line(line)
            if progress:
                on_progress(progress)
                continue
            try:
                rec = json.loads(line)
                if rec.get("level") in {"error", "critical"}:
                    error_lines.append(rec.get("msg", line))
                    log.warning("rclone: %s", rec.get("msg"))
            except json.JSONDecodeError:
                if line.strip():
                    error_lines.append(line.strip())
        proc.wait()
        if cancel.is_set():
            return
        if proc.returncode != 0:
            technical = "\n".join(error_lines[-20:])
            raise RcloneError(friendly_error(technical), technical)

    def check(self, folder: DriveFolder, dest: Path, only_files: list[str] | None = None) -> CheckResult:
        """Compara MD5 de Drive vs archivos locales (solo en dirección Drive -> disco)."""
        with self._only(only_files) as only:
            return self._check(folder, dest, only)

    def _check(self, folder: DriveFolder, dest: Path, only: list[str]) -> CheckResult:
        args = self._base() + [
            "check", self._src(), str(dest), *self._folder_flags(folder),
            "--one-way", "--combined", "-", "--log-level", "ERROR", *only,
        ]
        proc = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, **low_priority_popen_kwargs(),
        )
        result = parse_combined(proc.stdout.splitlines())
        # check devuelve != 0 si hay diferencias; solo es error real si no hubo salida
        if proc.returncode != 0 and not (result.ok or result.missing or result.differ or result.errors):
            raise RcloneError(friendly_error(proc.stderr), proc.stderr)
        return result
