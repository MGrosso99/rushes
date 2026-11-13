"""Chequeo de salud de videos/audio con ffprobe (rápido) y ffmpeg (profundo, opcional)."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import AUDIO_EXTENSIONS, FFPROBE_UNSUPPORTED, VIDEO_EXTENSIONS
from .winutil import low_priority_popen_kwargs


@dataclass
class MediaCheck:
    path: str
    ok: bool
    kind: str = ""                 # "video" | "audio" | "otro"
    duration: float | None = None
    codec: str = ""
    width: int | None = None
    height: int | None = None
    fps: str = ""
    problems: list[str] = field(default_factory=list)
    skipped_reason: str = ""


def media_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    return "otro"


def _fps(rate: str) -> str:
    try:
        num, den = rate.split("/")
        return f"{int(num) / int(den):.2f}".rstrip("0").rstrip(".") if int(den) else ""
    except (ValueError, ZeroDivisionError):
        return ""


def interpret_ffprobe(path: str, kind: str, returncode: int, stdout: str, stderr: str) -> MediaCheck:
    check = MediaCheck(path=path, ok=False, kind=kind)
    if returncode != 0:
        check.problems.append(stderr.strip().splitlines()[-1] if stderr.strip() else "ffprobe no pudo abrir el archivo")
        return check
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        check.problems.append("Respuesta inválida de ffprobe")
        return check

    streams = data.get("streams") or []
    fmt = data.get("format") or {}
    try:
        check.duration = float(fmt.get("duration")) if fmt.get("duration") else None
    except ValueError:
        check.duration = None

    wanted = "video" if kind == "video" else "audio"
    main = next((s for s in streams if s.get("codec_type") == wanted), None)
    if not main:
        check.problems.append(f"No tiene pista de {wanted}")
        return check

    check.codec = main.get("codec_name", "")
    if wanted == "video":
        check.width, check.height = main.get("width"), main.get("height")
        check.fps = _fps(main.get("avg_frame_rate") or main.get("r_frame_rate") or "")
    if not check.duration or check.duration <= 0:
        check.problems.append("Duración 0 o desconocida (posible archivo truncado)")
    if stderr.strip():
        check.problems.append("Advertencias: " + stderr.strip().splitlines()[0][:200])

    check.ok = not any(p for p in check.problems if not p.startswith("Advertencias"))
    return check


def probe(ffprobe: str, path: Path, timeout: int = 120) -> MediaCheck:
    kind = media_kind(path)
    if kind == "otro":
        return MediaCheck(str(path), ok=True, kind=kind, skipped_reason="No es video/audio")
    if path.suffix.lower() in FFPROBE_UNSUPPORTED:
        return MediaCheck(str(path), ok=True, kind=kind, skipped_reason="Formato RAW: validado solo por MD5")
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "format=duration,format_name:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate",
             "-of", "json", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            stdin=subprocess.DEVNULL, **low_priority_popen_kwargs(),
        )
    except subprocess.TimeoutExpired:
        return MediaCheck(str(path), ok=False, kind=kind, problems=["ffprobe tardó demasiado"])
    return interpret_ffprobe(str(path), kind, proc.returncode, proc.stdout, proc.stderr)


def deep_check(ffmpeg: str, path: Path) -> list[str]:
    """Decodifica todo el archivo. Lento: solo si está activado en config."""
    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, **low_priority_popen_kwargs(),
    )
    lines = [l for l in proc.stderr.splitlines() if l.strip()]
    if proc.returncode != 0 and not lines:
        lines = ["ffmpeg no pudo decodificar el archivo"]
    return lines[:10]
