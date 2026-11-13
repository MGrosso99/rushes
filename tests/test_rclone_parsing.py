import json

from traer_material.rclone import friendly_error, parse_combined, parse_stats_line


def test_stats_line():
    line = json.dumps({"level": "notice", "msg": "...", "stats": {
        "bytes": 50, "totalBytes": 200, "speed": 10.5, "eta": 15, "transfers": 1,
        "totalTransfers": 4, "errors": 0,
        "transferring": [{"name": "A001.mov", "percentage": 42}]}})
    p = parse_stats_line(line)
    assert p.percent == 25.0
    assert p.current == [("A001.mov", 42)]


def test_non_stats_lines():
    assert parse_stats_line('{"level":"info","msg":"Copied (new)"}') is None
    assert parse_stats_line("no json") is None


def test_combined():
    r = parse_combined(["= a.mov", "- dir/b.mov", "* c.mov", "! d.mov", "+ _reporte/reporte.html", ""])
    assert r.ok == ["a.mov"] and r.missing == ["dir/b.mov"]
    assert r.differ == ["c.mov"] and r.errors == ["d.mov"]
    assert not r.all_ok


def test_friendly_errors():
    assert "Conectar Google" in friendly_error("oauth2: cannot fetch token: invalid_grant")
    assert "No encontré la carpeta" in friendly_error("directory not found")
    assert "internet" in friendly_error("dial tcp: lookup www.googleapis.com: no such host")
    assert "Probá de nuevo" in friendly_error("algo rarísimo")
