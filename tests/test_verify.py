import json
import shutil
import subprocess

import pytest

from rushes.verify import interpret_ffprobe, probe


def _out(streams, duration="12.5"):
    return json.dumps({"streams": streams, "format": {"duration": duration}})


def test_ok_video():
    c = interpret_ffprobe("a.mp4", "video", 0, _out([
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "25/1"}
    ]), "")
    assert c.ok and c.fps == "25" and c.width == 1920


def test_no_video_stream():
    c = interpret_ffprobe("a.mp4", "video", 0, _out([{"codec_type": "audio"}]), "")
    assert not c.ok and "pista de video" in c.problems[0]


def test_truncated():
    c = interpret_ffprobe("a.mp4", "video", 0, _out([{"codec_type": "video"}], duration="0"), "")
    assert not c.ok


def test_ffprobe_failure():
    c = interpret_ffprobe("a.mp4", "video", 1, "", "moov atom not found")
    assert not c.ok and "moov" in c.problems[0]


def test_raw_skipped(tmp_path):
    f = tmp_path / "clip.braw"
    f.write_bytes(b"x")
    assert probe("ffprobe", f).skipped_reason


@pytest.mark.skipif(not (shutil.which("ffprobe") and shutil.which("ffmpeg")), reason="sin ffmpeg")
def test_real_files(tmp_path):
    good = tmp_path / "good.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
                    "-pix_fmt", "yuv420p", str(good)], check=True)
    assert probe("ffprobe", good).ok
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(good.read_bytes()[: good.stat().st_size // 3])
    assert not probe("ffprobe", broken).ok
