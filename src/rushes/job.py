"""Orquesta un trabajo: preparar (resumen) -> descargar -> verificar -> reportar.

No depende de la GUI: recibe callbacks, así se puede testear y usar desde CLI.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .config import Config, app_data_dir, find_binary
from .disks import DiskInfo, find_disk
from .drive_link import DriveFolder, parse_drive_link
from .rclone import Progress, Rclone, RcloneError
from .report import FileResult, JobResult, format_bytes, write_report
from .verify import deep_check, media_kind, probe
from .winutil import is_resolve_open

log = logging.getLogger("rushes.job")

EventFn = Callable[[str, object], None]
MAX_RETRY_PASSES = 2  # pasadas extra para archivos que fallaron el MD5 o faltan
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class JobError(RuntimeError):
    """Error con mensaje para la usuaria."""


def sanitize_name(name: str) -> str:
    name = _INVALID.sub("", name).strip().rstrip(". ")
    return name[:80] or "Material"


# ---------- historial: mismo link => misma carpeta (para poder retomar) ----------
def _history_path() -> Path:
    return app_data_dir() / "history.json"


def _load_history() -> dict:
    try:
        return json.loads(_history_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_history(folder_id: str, entry: dict) -> None:
    data = _load_history()
    data[folder_id] = entry
    _history_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _dir_size(path: Path) -> int:
    total = 0
    if path.exists():
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except OSError:
                    pass
    return total


@dataclass
class Plan:
    folder: DriveFolder
    disk: DiskInfo
    dest: Path
    project_name: str
    file_count: int
    total_bytes: int
    existing_bytes: int
    resumed: bool

    @property
    def needed_bytes(self) -> int:
        return max(0, self.total_bytes - self.existing_bytes)

    def space_problem(self, margin_gb: int) -> str:
        margin = margin_gb * 1024**3
        if self.needed_bytes + margin > self.disk.free_bytes:
            return (
                f"No entra en el disco: hacen falta {format_bytes(self.needed_bytes)} "
                f"(+{margin_gb} GB de margen) y hay {format_bytes(self.disk.free_bytes)} libres. "
                "Liberá espacio en el disco externo y volvé a intentar."
            )
        return ""

    def summary(self) -> str:
        text = (
            f"{self.file_count} archivos, {format_bytes(self.total_bytes)}.\n"
            f"Destino: {self.dest}\n"
            f"Libre en el disco: {format_bytes(self.disk.free_bytes)}"
        )
        if self.resumed and self.existing_bytes:
            text += f"\nYa hay {format_bytes(self.existing_bytes)} descargados: se baja solo lo que falta."
        return text


class Job:
    def __init__(self, cfg: Config, rclone: Rclone):
        self.cfg = cfg
        self.rclone = rclone
        self.cancel = threading.Event()

    def prepare(self, link: str, project_name: str) -> Plan:
        folder = parse_drive_link(link)
        disk = find_disk(self.cfg.disk_label, self.cfg.dest_override_path)

        history = _load_history().get(folder.folder_id)
        if history and Path(history["dest"]).drive.upper() == Path(disk.root).drive.upper():
            dest, name, resumed = Path(history["dest"]), history["project_name"], True
        else:
            name = sanitize_name(project_name or "Material")
            stamp = datetime.now().strftime("%Y-%m-%d")
            dest = Path(disk.root) / self.cfg.base_dir / f"{stamp} - {name}"
            resumed = False

        try:
            count, total = self.rclone.size(folder)
        except RcloneError as exc:
            log.error("size falló: %s", exc.technical)
            raise JobError(str(exc)) from exc
        if count == 0:
            raise JobError("La carpeta está vacía (o solo tiene documentos de Google, que no se descargan).")

        return Plan(folder, disk, dest, name, count, total, _dir_size(dest), resumed)

    def run(self, plan: Plan, on_event: EventFn) -> JobResult:
        result = JobResult(
            project_name=plan.project_name, dest=str(plan.dest),
            drive_folder_id=plan.folder.folder_id,
            started=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        plan.dest.mkdir(parents=True, exist_ok=True)
        _save_history(plan.folder.folder_id, {"dest": str(plan.dest), "project_name": plan.project_name})

        # 1) Descargar
        resolve_open = is_resolve_open()
        transfers = self.cfg.transfers_when_resolve_open if resolve_open else self.cfg.transfers
        bwlimit = self.cfg.bwlimit_when_resolve_open if resolve_open else ""
        on_event("phase", "Descargando" + (" (modo liviano: DaVinci está abierto)" if resolve_open else "") + "…")
        try:
            self.rclone.copy(plan.folder, plan.dest, transfers, lambda p: on_event("progress", p),
                             self.cancel, bwlimit)
        except RcloneError as exc:
            log.error("copy falló: %s", exc.technical)
            if not plan.disk.is_connected:
                raise JobError("Se desconectó el disco. Volvé a conectarlo y abrí la app de nuevo: "
                               "retoma donde quedó.") from exc
            raise JobError(str(exc)) from exc
        if self.cancel.is_set():
            raise JobError("Descarga cancelada. Lo que ya bajó queda guardado; con el mismo link retoma.")

        # 2) Verificar MD5 contra Drive
        on_event("phase", "Verificando que todo llegó completo…")
        try:
            check = self.rclone.check(plan.folder, plan.dest)
        except RcloneError as exc:
            log.error("check falló: %s", exc.technical)
            raise JobError(str(exc)) from exc

        # 2b) Reintentar SOLO los que fallaron (re-descarga forzada + nuevo MD5)
        for attempt in range(1, MAX_RETRY_PASSES + 1):
            failed = check.missing + check.differ + check.errors
            if not failed or self.cancel.is_set():
                break
            log.warning("Reintento %s: %s archivos (%s)", attempt, len(failed), failed[:5])
            on_event("phase", f"Reintentando {len(failed)} archivo(s) que no llegaron bien "
                              f"(intento {attempt} de {MAX_RETRY_PASSES})…")
            try:
                self.rclone.copy(plan.folder, plan.dest, transfers, lambda p: on_event("progress", p),
                                 self.cancel, bwlimit, only_files=failed)
                recheck = self.rclone.check(plan.folder, plan.dest, only_files=failed)
            except RcloneError as exc:
                log.error("reintento falló: %s", exc.technical)
                if not plan.disk.is_connected:
                    raise JobError("Se desconectó el disco. Volvé a conectarlo y abrí la app de nuevo: "
                                   "retoma donde quedó.") from exc
                break  # se reporta lo que quedó mal; no se pierde lo bueno
            check.ok += recheck.ok
            check.missing, check.differ, check.errors = recheck.missing, recheck.differ, recheck.errors

        for name, md5 in ([(n, "ok") for n in check.ok] + [(n, "falta") for n in check.missing]
                          + [(n, "distinto") for n in check.differ] + [(n, "error") for n in check.errors]):
            local = plan.dest / name
            size = local.stat().st_size if local.exists() else 0
            result.files.append(FileResult(name=name, size=size, md5=md5))

        # 3) Salud de videos/audio
        ffprobe = find_binary("ffprobe")
        ffmpeg = find_binary("ffmpeg") if self.cfg.deep_check else None
        media = [f for f in result.files if f.md5 == "ok" and media_kind(Path(f.name)) != "otro"]
        if ffprobe:
            for i, f in enumerate(media, 1):
                if self.cancel.is_set():
                    break
                on_event("media", (i, len(media), f.name))
                f.media = probe(ffprobe, plan.dest / f.name)
                if ffmpeg and f.media.ok and not f.media.skipped_reason:
                    problems = deep_check(ffmpeg, plan.dest / f.name)
                    if problems:
                        f.media.ok = False
                        f.media.problems += ["Frames dañados: " + problems[0][:150]]
        else:
            log.warning("ffprobe no encontrado: se omite el chequeo de videos")

        # 4) Reporte
        result.finished = datetime.now().strftime("%Y-%m-%d %H:%M")
        report = write_report(result)
        on_event("report", str(report))
        log.info("Trabajo terminado: %s", result.summary)
        return result
