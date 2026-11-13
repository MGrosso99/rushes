"""Resultado del trabajo + reporte HTML y manifest JSON en <destino>/_reporte/."""
from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .verify import MediaCheck

REPORT_DIRNAME = "_reporte"

MD5_LABELS = {
    "ok": "Íntegro",
    "distinto": "Llegó distinto",
    "falta": "No se descargó",
    "error": "No se pudo verificar",
}


@dataclass
class FileResult:
    name: str
    size: int = 0
    md5: str = "ok"                       # ok | distinto | falta | error
    media: MediaCheck | None = None

    @property
    def status(self) -> str:
        """ok | aviso | error"""
        if self.md5 != "ok":
            return "error"
        if self.media and not self.media.ok:
            return "error"
        if self.media and self.media.problems:
            return "aviso"
        return "ok"

    @property
    def detail(self) -> str:
        if self.md5 != "ok":
            return MD5_LABELS.get(self.md5, self.md5)
        if self.media is None:
            return ""
        if self.media.problems:
            return "; ".join(self.media.problems)
        if self.media.skipped_reason:
            return self.media.skipped_reason
        bits = []
        if self.media.width and self.media.height:
            bits.append(f"{self.media.width}×{self.media.height}")
        if self.media.fps:
            bits.append(f"{self.media.fps} fps")
        if self.media.codec:
            bits.append(self.media.codec)
        if self.media.duration:
            bits.append(format_duration(self.media.duration))
        return " · ".join(bits)


@dataclass
class JobResult:
    project_name: str
    dest: str
    drive_folder_id: str
    started: str
    finished: str = ""
    files: list[FileResult] = field(default_factory=list)
    fatal_error: str = ""

    @property
    def counts(self) -> dict[str, int]:
        c = {"ok": 0, "aviso": 0, "error": 0}
        for f in self.files:
            c[f.status] += 1
        return c

    @property
    def summary(self) -> str:
        if self.fatal_error:
            return self.fatal_error
        c = self.counts
        total = len(self.files)
        if c["error"] == 0 and c["aviso"] == 0:
            return f"Listo. Los {total} archivos llegaron bien."
        parts = [f"{c['ok']} OK"]
        if c["aviso"]:
            parts.append(f"{c['aviso']} con avisos")
        if c["error"]:
            parts.append(f"{c['error']} con problemas")
        return "Terminó: " + ", ".join(parts) + "."


def format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def format_duration(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


_ICON = {"ok": "✅", "aviso": "⚠️", "error": "❌"}


def render_html(result: JobResult) -> str:
    e = html.escape
    order = {"error": 0, "aviso": 1, "ok": 2}
    rows = "\n".join(
        f"<tr class='{f.status}'><td>{_ICON[f.status]}</td><td>{e(f.name)}</td>"
        f"<td class='num'>{e(format_bytes(f.size))}</td><td>{e(f.detail)}</td></tr>"
        for f in sorted(result.files, key=lambda f: (order[f.status], f.name.lower()))
    )
    c = result.counts
    help_block = ""
    transfer_failed = any(f.md5 != "ok" for f in result.files)
    origin_failed = any(f.md5 == "ok" and f.status == "error" for f in result.files)
    tips = []
    if transfer_failed:
        tips.append("Los que dicen <b>No se descargó / Llegó distinto</b> ya se reintentaron automáticamente. "
                    "Volvé a abrir <b>Traer material</b> con el mismo link más tarde (baja solo esos); "
                    "si siguen fallando, pedile al filmmaker que los vuelva a subir.")
    if origin_failed:
        tips.append("Los que llegaron <b>íntegros pero no se pueden abrir</b> son idénticos al archivo de Drive: "
                    "el problema está en el original. Pedile al filmmaker que los vuelva a exportar o subir.")
    if tips:
        help_block = "".join(f"<p class='help'>{t}</p>" for t in tips)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Reporte – {e(result.project_name)}</title>
<style>
body{{font-family:Segoe UI,system-ui,sans-serif;margin:32px auto;max-width:960px;color:#222;padding:0 16px}}
h1{{font-size:22px;font-weight:600;margin-bottom:4px}} .meta{{color:#666;font-size:13px;margin-bottom:20px}}
.cards{{display:flex;gap:12px;margin-bottom:20px}}
.card{{flex:1;border-radius:10px;padding:12px 16px;background:#f4f4f2}}
.card b{{display:block;font-size:24px}} .card.err{{background:#fdecec}} .card.warn{{background:#fdf5e6}} .card.good{{background:#eaf5ea}}
table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{text-align:left;padding:8px;border-bottom:1px solid #eee}}
th{{color:#666;font-weight:500}} td.num{{white-space:nowrap;text-align:right}}
tr.error td{{background:#fff6f6}} tr.aviso td{{background:#fffbf2}}
.help{{background:#f4f4f2;border-radius:10px;padding:12px 16px}}
</style></head><body>
<h1>{e(result.project_name)}</h1>
<div class="meta">{e(result.summary)}<br>Carpeta: {e(result.dest)}<br>
Inicio: {e(result.started)} · Fin: {e(result.finished)}</div>
<div class="cards">
<div class="card good"><b>{c['ok']}</b>OK</div>
<div class="card warn"><b>{c['aviso']}</b>Con avisos</div>
<div class="card err"><b>{c['error']}</b>Con problemas</div>
</div>
{help_block}
<table><thead><tr><th></th><th>Archivo</th><th>Tamaño</th><th>Detalle</th></tr></thead>
<tbody>
{rows}
</tbody></table>
</body></html>"""


def write_report(result: JobResult) -> Path:
    """Escribe reporte.html y manifest.json. Devuelve la ruta del HTML."""
    out = Path(result.dest) / REPORT_DIRNAME
    out.mkdir(parents=True, exist_ok=True)
    result.finished = result.finished or datetime.now().strftime("%Y-%m-%d %H:%M")
    manifest = asdict(result)
    manifest["counts"] = result.counts
    for f, src in zip(manifest["files"], result.files):
        f["status"] = src.status
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path = out / "reporte.html"
    html_path.write_text(render_html(result), encoding="utf-8")
    return html_path
