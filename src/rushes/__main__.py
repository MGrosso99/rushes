"""Punto de entrada.

  rushes              -> abre la ventana
  rushes --cli LINK   -> modo consola (para vos, para debug)
"""
from __future__ import annotations

import argparse
import sys

from .logging_setup import setup_logging


def _cli(link: str, name: str) -> int:
    from .config import Config, find_binary, rclone_conf_path
    from .job import Job, JobError
    from .rclone import Rclone

    cfg = Config.load()
    rclone = Rclone(find_binary("rclone") or "rclone", rclone_conf_path(), cfg.rclone_remote)
    if not rclone.is_connected():
        print("Conectando Google (se abre el navegador)…")
        rclone.connect(cfg.google_client_id, cfg.google_client_secret)
    job = Job(cfg, rclone)
    try:
        plan = job.prepare(link, name)
        print(plan.summary())
        problem = plan.space_problem(cfg.min_free_margin_gb)
        if problem:
            print(problem)
            return 2

        def on_event(kind, payload):
            if kind == "phase":
                print(payload)
            elif kind == "progress":
                print(f"\r{payload.percent:5.1f}%", end="", flush=True)
            elif kind == "media":
                print(f"\rRevisando {payload[0]}/{payload[1]}: {payload[2]}", end="", flush=True)

        result = job.run(plan, on_event)
    except JobError as exc:
        print(f"\nError: {exc}")
        return 1
    print("\n" + result.summary)
    return 0 if result.counts["error"] == 0 else 1


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(prog="rushes")
    parser.add_argument("--cli", metavar="LINK", help="modo consola con el link de Drive")
    parser.add_argument("--name", default="", help="nombre del proyecto (modo consola)")
    args = parser.parse_args()
    if args.cli:
        sys.exit(_cli(args.cli, args.name))
    from .app import run
    run()


if __name__ == "__main__":
    main()
