#!/usr/bin/env python3
"""rclone falso para tests end-to-end: 'Drive' es la carpeta $FAKE_DRIVE.

Soporta: listremotes, config create/delete, size --json, copy, check --combined -.
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

args = sys.argv[1:]
conf = Path(args[args.index("--config") + 1])
drive = Path(os.environ["FAKE_DRIVE"])
cmd = [a for a in args if not a.startswith("--")][1:]  # saca valor de --config
op = cmd[0]


ONLY = None
if "--files-from-raw" in args:
    ONLY = set(Path(args[args.index("--files-from-raw") + 1]).read_text(encoding="utf-8").split("\n")) - {""}


def files(root):
    fs = sorted(p for p in root.rglob("*") if p.is_file())
    if ONLY is not None:
        fs = [p for p in fs if p.relative_to(root).as_posix() in ONLY]
    return fs


def should_corrupt(name):
    if os.environ.get("FAKE_CORRUPT") == name:
        return True
    marker = conf.parent / f"corrupted-{name}"
    if os.environ.get("FAKE_CORRUPT_ONCE") == name and not marker.exists():
        marker.write_text("x")  # solo la primera vez (error transitorio)
        return True
    return False


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


if op == "listremotes":
    print("gdrive:" if conf.exists() else "")
elif op == "config":
    if cmd[1] == "create":
        conf.write_text("[gdrive]\ntype = drive\nscope = drive.readonly\n")
    elif cmd[1] == "delete" and conf.exists():
        conf.unlink()
elif op == "size":
    fs = files(drive)
    print(json.dumps({"count": len(fs), "bytes": sum(f.stat().st_size for f in fs)}))
elif op == "copy":
    dest = Path(cmd[2])
    fs = files(drive)
    total = sum(f.stat().st_size for f in fs)
    done = 0
    for i, f in enumerate(fs, 1):
        target = dest / f.relative_to(drive)
        target.parent.mkdir(parents=True, exist_ok=True)
        if should_corrupt(f.name):
            target.write_bytes(f.read_bytes()[:-10])
        else:
            shutil.copy2(f, target)
        done += f.stat().st_size
        print(json.dumps({"level": "notice", "msg": "stats", "stats": {
            "bytes": done, "totalBytes": total, "speed": 1000, "eta": 1,
            "transfers": i, "totalTransfers": len(fs), "errors": 0,
            "transferring": [{"name": f.name, "percentage": 100}]}}), file=sys.stderr, flush=True)
elif op == "check":
    dest = Path(cmd[2])
    diff = False
    for f in files(drive):
        rel = f.relative_to(drive).as_posix()
        local = dest / rel
        if not local.exists():
            print(f"- {rel}"); diff = True
        elif md5(local) != md5(f):
            print(f"* {rel}"); diff = True
        else:
            print(f"= {rel}")
    sys.exit(1 if diff else 0)
