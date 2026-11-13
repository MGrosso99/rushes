"""Flujo completo con un rclone falso y videos reales generados con ffmpeg."""
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from traer_material.config import Config
from traer_material.job import Job, JobError
from traer_material.rclone import Rclone

FID = "1AbCdEfGhIjKlMnOpQrStUvWxYz"
LINK = f"https://drive.google.com/drive/folders/{FID}?usp=sharing"
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    drive = tmp_path / "drive"
    (drive / "Camara B").mkdir(parents=True)
    if HAS_FFMPEG:
        for name in ("A001.mp4", "Camara B/B001.mp4"):
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "testsrc=duration=1:size=320x240:rate=25", "-pix_fmt", "yuv420p",
                            str(drive / name)], check=True)
    (drive / "guion.pdf").write_bytes(b"%PDF fake")
    monkeypatch.setenv("FAKE_DRIVE", str(drive))

    wrapper = tmp_path / "rclone"
    wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} {Path(__file__).parent / 'fake_rclone.py'} \"$@\"\n")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)

    cfg = Config(dest_override_path=str(tmp_path / "disco"), min_free_margin_gb=0)
    rclone = Rclone(str(wrapper), tmp_path / "appdata" / "TraerMaterial" / "rclone.conf")
    rclone.config_file.parent.mkdir(parents=True, exist_ok=True)
    rclone.connect()
    return cfg, rclone, tmp_path


def test_full_flow(env, monkeypatch):
    cfg, rclone, tmp = env
    monkeypatch.setattr("traer_material.job.find_binary",
                        lambda n: shutil.which(n))
    job = Job(cfg, rclone)
    plan = job.prepare(LINK, "Casamiento: Ana/Juan")
    assert plan.file_count == (3 if HAS_FFMPEG else 1)
    assert plan.dest.name.endswith("Casamiento AnaJuan")  # nombre saneado para Windows

    events = []
    result = job.run(plan, lambda k, p: events.append(k))
    assert result.counts["error"] == 0, [(f.name, f.md5, f.detail) for f in result.files]
    assert "progress" in events and "report" in events
    report_dir = plan.dest / "_reporte"
    manifest = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["ok"] == plan.file_count
    assert "reporte" in (report_dir / "reporte.html").name

    # Mismo link otra vez => misma carpeta (retomar)
    plan2 = Job(cfg, rclone).prepare(LINK, "otro nombre")
    assert plan2.dest == plan.dest and plan2.resumed


@pytest.mark.skipif(not HAS_FFMPEG, reason="sin ffmpeg")
def test_corrupt_file_detected(env, monkeypatch):
    cfg, rclone, tmp = env
    monkeypatch.setenv("FAKE_CORRUPT", "A001.mp4")
    job = Job(cfg, rclone)
    result = job.run(job.prepare(LINK, "x"), lambda k, p: None)
    bad = [f for f in result.files if f.status == "error"]
    assert [f.name for f in bad] == ["A001.mp4"] and bad[0].md5 == "distinto"


def test_not_enough_space(env):
    cfg, rclone, tmp = env
    plan = Job(cfg, rclone).prepare(LINK, "x")
    assert "No entra en el disco" in plan.space_problem(margin_gb=10_000_000)


def test_invalid_link(env):
    cfg, rclone, _ = env
    with pytest.raises(Exception, match="no es de Google Drive"):
        Job(cfg, rclone).prepare("https://wetransfer.com/x", "x")
