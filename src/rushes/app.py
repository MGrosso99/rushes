"""Ventana principal (tkinter, incluido en Python: sin dependencias externas).

Todo el trabajo pesado corre en un hilo; la GUI recibe eventos por una cola.
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import APP_TITLE, UPDATE_REPO, __version__
from . import updater
from .config import Config, config_path, find_binary, logs_dir, rclone_conf_path
from .disks import DiskError, NeedsDestination
from .drive_link import LinkError
from .job import Job, JobError, Plan, destination, set_destination
from .rclone import Progress, Rclone, RcloneError
from .report import JobResult, format_bytes
from .winutil import open_path

log = logging.getLogger("rushes.app")

ICON = {"ok": "✅", "aviso": "⚠️", "error": "❌"}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("720x620")
        self.minsize(640, 560)

        self.cfg = Config.load()
        rclone_exe = find_binary("rclone")
        if not rclone_exe:
            messagebox.showerror(APP_TITLE, "Falta rclone en la instalación. Reinstalá la app.")
            self.destroy()
            return
        self.rclone = Rclone(rclone_exe, rclone_conf_path(), self.cfg.rclone_remote)
        self.job: Job | None = None
        self.plan: Plan | None = None
        self.result: JobResult | None = None
        self.report_path: str | None = None
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.update_release: updater.Release | None = None

        self._build_menu()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_events)
        self.after(200, self._startup_checks)

    # ------------------------------------------------------------------ UI
    def _build_menu(self) -> None:
        bar = tk.Menu(self)
        help_menu = tk.Menu(bar, tearoff=False)
        help_menu.add_command(label="Conectar / reconectar Google", command=self._connect_google)
        help_menu.add_separator()
        help_menu.add_command(label="Abrir carpeta de logs", command=lambda: open_path(str(logs_dir())))
        help_menu.add_command(label="Editar configuración", command=lambda: open_path(str(config_path())))
        help_menu.add_separator()
        help_menu.add_command(label="Acerca de", command=lambda: messagebox.showinfo(
            APP_TITLE, f"{APP_TITLE} v{__version__}"))
        bar.add_cascade(label="Ayuda", menu=help_menu)
        self.config(menu=bar)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 11), padding=8)
        style.configure("Error.TLabel", foreground="#b3261e")
        style.configure("Ok.TLabel", foreground="#1e6b2e")

        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)

        # Aviso de actualización (oculto hasta que haya una)
        self.update_bar = ttk.Frame(root, padding=(10, 8), relief="solid", borderwidth=1)
        self.update_label = ttk.Label(self.update_bar, text="")
        self.update_label.pack(side="left")
        self.update_btn = ttk.Button(self.update_bar, text="Actualizar", command=self._apply_update)
        self.update_btn.pack(side="right")

        self.title_label = ttk.Label(root, text=APP_TITLE, style="Title.TLabel")
        self.title_label.pack(anchor="w")

        disk_row = ttk.Frame(root)
        disk_row.pack(fill="x", pady=(6, 14))
        self.disk_label = ttk.Label(disk_row, text="Buscando dónde guardar…", wraplength=520, justify="left")
        self.disk_label.pack(side="left")
        self.disk_choose = ttk.Button(disk_row, text="Elegir carpeta…", command=self._choose_destination)
        self.disk_choose.pack(side="right")
        self.disk_retry = ttk.Button(disk_row, text="Reintentar", command=self._refresh_disk)

        ttk.Label(root, text="1. Pegá el link de la carpeta de Drive").pack(anchor="w")
        link_row = ttk.Frame(root)
        link_row.pack(fill="x", pady=(2, 10))
        self.link_var = tk.StringVar()
        self.link_entry = ttk.Entry(link_row, textvariable=self.link_var, font=("Segoe UI", 10))
        self.link_entry.pack(side="left", fill="x", expand=True, ipady=4)
        ttk.Button(link_row, text="Pegar", command=self._paste).pack(side="left", padx=(6, 0))

        ttk.Label(root, text="2. Nombre del proyecto (opcional)").pack(anchor="w")
        self.name_var = tk.StringVar()
        ttk.Entry(root, textvariable=self.name_var, font=("Segoe UI", 10)).pack(fill="x", pady=(2, 10), ipady=4)

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(4, 8))
        self.check_btn = ttk.Button(actions, text="Revisar", style="Big.TButton", command=self._prepare)
        self.check_btn.pack(side="left")
        self.download_btn = ttk.Button(actions, text="Descargar", style="Big.TButton",
                                       command=self._start_download, state="disabled")
        self.download_btn.pack(side="left", padx=8)
        self.cancel_btn = ttk.Button(actions, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left")

        self.summary_label = ttk.Label(root, text="", justify="left", wraplength=660)
        self.summary_label.pack(anchor="w", pady=(4, 8))

        self.progress = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        self.status_label = ttk.Label(root, text="", wraplength=660, justify="left")
        self.status_label.pack(anchor="w", pady=(4, 8))

        cols = ("estado", "archivo", "detalle")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", height=8)
        self.tree.heading("estado", text="")
        self.tree.heading("archivo", text="Archivo")
        self.tree.heading("detalle", text="Detalle")
        self.tree.column("estado", width=40, anchor="center", stretch=False)
        self.tree.column("archivo", width=300)
        self.tree.column("detalle", width=320)
        self.tree.pack(fill="both", expand=True)

        bottom = ttk.Frame(root)
        bottom.pack(fill="x", pady=(10, 0))
        self.open_btn = ttk.Button(bottom, text="Abrir carpeta", command=self._open_dest, state="disabled")
        self.open_btn.pack(side="left")
        self.report_btn = ttk.Button(bottom, text="Ver reporte", command=self._open_report, state="disabled")
        self.report_btn.pack(side="left", padx=8)

    # ------------------------------------------------------------ helpers
    def _set_busy(self, busy: bool, running: bool = False) -> None:
        self.busy = busy
        self.check_btn.config(state="disabled" if busy else "normal")
        self.link_entry.config(state="disabled" if busy else "normal")
        self.download_btn.config(state="disabled" if busy or not self.plan else "normal")
        self.cancel_btn.config(state="normal" if running else "disabled")

    def _run_in_thread(self, fn) -> None:
        def wrapper():
            try:
                fn()
            except (JobError, LinkError, DiskError, RcloneError) as exc:
                self.events.put(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001 — nunca dejar la GUI colgada
                log.exception("Error inesperado")
                self.events.put(("error", "Pasó algo inesperado. Mandá los logs (menú Ayuda) "
                                          f"a quien te instaló la app.\n\nDetalle: {exc}"))
        threading.Thread(target=wrapper, daemon=True).start()

    def _paste(self) -> None:
        try:
            self.link_var.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    # ------------------------------------------------------------ startup
    def _startup_checks(self) -> None:
        if not self._refresh_disk() and not self.cfg.dest_folder and not self.cfg.disk_label:
            messagebox.showinfo(
                APP_TITLE,
                "Primero elegí dónde guardar el material. Conviene una carpeta en tu disco externo, "
                "por ejemplo una llamada «Rushes».\n\nLa app la recuerda para las próximas veces.")
            self._choose_destination()
        repo = self.cfg.update_repo or UPDATE_REPO
        if updater.updates_enabled(repo):
            threading.Thread(target=lambda: self.events.put(("update_available", updater.check_latest(repo))),
                             daemon=True).start()
        if not self.rclone.is_connected():
            if messagebox.askyesno(
                APP_TITLE,
                "Antes de empezar hay que conectar tu cuenta de Google (solo la primera vez).\n\n"
                "Se va a abrir el navegador: iniciá sesión y aceptá los permisos. "
                "La app solo puede LEER tu Drive, nunca borrar ni modificar.\n\n¿Conectar ahora?"):
                self._connect_google()

    def _refresh_disk(self) -> bool:
        """Muestra el destino actual. Devuelve True si está disponible."""
        try:
            disk, base = destination(self.cfg)
            self.disk_label.config(
                text=f"Se guarda en: {base}  ·  {format_bytes(disk.free_bytes)} libres", style="Ok.TLabel")
            self.disk_choose.config(text="Cambiar…")
            self.disk_retry.pack_forget()
            return True
        except NeedsDestination as exc:
            self.disk_label.config(text=str(exc), style="Error.TLabel")
            self.disk_choose.config(text="Elegir carpeta…")
            self.disk_retry.pack_forget()
        except DiskError as exc:
            self.disk_label.config(text=str(exc), style="Error.TLabel")
            self.disk_choose.config(text="Elegir otra carpeta…")
            self.disk_retry.pack(side="right", padx=8)
        return False

    def _choose_destination(self) -> None:
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Esperá a que termine lo que está haciendo y después cambiá la carpeta.")
            return
        folder = filedialog.askdirectory(
            parent=self, mustexist=True,
            title="Elegí dónde guardar el material (por ejemplo, una carpeta en tu disco externo)",
            initialdir=self.cfg.dest_folder or None,
        )
        if not folder:
            return
        try:
            disk = set_destination(self.cfg, folder)
        except DiskError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        if disk.is_system_drive and not messagebox.askyesno(
            APP_TITLE,
            "Esa carpeta está en el disco de Windows (C:). El material de una boda ocupa mucho y puede "
            "dejar la compu sin espacio.\n\n¿Usarla igual? (Lo recomendable es el disco externo.)"):
            self.cfg.dest_folder = ""
            self.cfg.save()
        self._refresh_disk()

    def _connect_google(self) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self.status_label.config(text="Esperando que inicies sesión en el navegador…")

        def work():
            self.rclone.connect(self.cfg.google_client_id, self.cfg.google_client_secret)
            self.events.put(("connected", None))
        self._run_in_thread(work)

    # ------------------------------------------------------------ flujo
    def _prepare(self) -> None:
        self.plan = None
        self.tree.delete(*self.tree.get_children())
        self.progress["value"] = 0
        self.open_btn.config(state="disabled")
        self.report_btn.config(state="disabled")
        self._set_busy(True)
        self.summary_label.config(text="Revisando la carpeta en Drive…", style="TLabel")
        self.status_label.config(text="")
        self.job = Job(self.cfg, self.rclone)
        link, name = self.link_var.get(), self.name_var.get()

        def work():
            self.events.put(("planned", self.job.prepare(link, name)))
        self._run_in_thread(work)

    def _start_download(self) -> None:
        if not self.plan or not self.job:
            return
        plan, job = self.plan, self.job
        self._set_busy(True, running=True)

        def work():
            result = job.run(plan, lambda kind, payload: self.events.put((kind, payload)))
            self.events.put(("done", result))
        self._run_in_thread(work)

    def _cancel(self) -> None:
        if self.job and messagebox.askyesno(APP_TITLE, "¿Cancelar la descarga? Lo que ya bajó queda guardado."):
            self.job.cancel.set()
            self.status_label.config(text="Cancelando…")

    # ------------------------------------------------------------ eventos
    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self.after(150, self._poll_events)

    def _handle(self, kind: str, payload) -> None:
        if kind == "planned":
            plan: Plan = payload
            problem = plan.space_problem(self.cfg.min_free_margin_gb)
            self.plan = None if problem else plan
            self._set_busy(False)
            if problem:
                self.summary_label.config(text=problem, style="Error.TLabel")
            else:
                self.summary_label.config(text=plan.summary() + "\n\nTocá Descargar para empezar.",
                                          style="TLabel")
        elif kind == "phase":
            self.status_label.config(text=str(payload))
        elif kind == "progress":
            p: Progress = payload
            self.progress["value"] = p.percent
            current = ", ".join(f"{n} ({pct}%)" for n, pct in p.current[:2])
            eta = f" · faltan ~{int(p.eta) // 60 + 1} min" if p.eta else ""
            self.status_label.config(
                text=f"Descargando: {format_bytes(p.bytes_done)} de {format_bytes(p.bytes_total)} "
                     f"· {format_bytes(p.speed)}/s{eta}\n{current}")
        elif kind == "media":
            i, n, name = payload
            self.progress["value"] = 100 * i / max(n, 1)
            self.status_label.config(text=f"Revisando videos ({i} de {n}): {name}")
        elif kind == "report":
            self.report_path = payload
        elif kind == "done":
            self._show_result(payload)
        elif kind == "update_available":
            if payload:
                self.update_release = payload
                self.update_label.config(text=f"Hay una versión nueva de Rushes ({payload.version}).")
                self.update_bar.pack(fill="x", pady=(0, 12), before=self.title_label)
        elif kind == "phase_update":
            self.update_label.config(text=f"Bajando la actualización… {payload:.0f}%")
        elif kind == "update_ready":
            updater.launch_installer(payload)
            self.destroy()
        elif kind == "update_failed":
            self.update_btn.config(state="normal")
            self.update_label.config(text=str(payload))
        elif kind == "connected":
            self._set_busy(False)
            self.status_label.config(text="Cuenta de Google conectada. ✅")
        elif kind == "error":
            self._set_busy(False)
            self.plan = None
            self.download_btn.config(state="disabled")
            self.status_label.config(text="")
            self.summary_label.config(text=str(payload), style="Error.TLabel")
            self._refresh_disk()

    def _show_result(self, result: JobResult) -> None:
        self.result = result
        self.plan = None
        self._set_busy(False)
        self.progress["value"] = 100
        order = {"error": 0, "aviso": 1, "ok": 2}
        for f in sorted(result.files, key=lambda f: (order[f.status], f.name.lower())):
            self.tree.insert("", "end", values=(ICON[f.status], f.name, f.detail))
        ok = result.counts["error"] == 0
        self.summary_label.config(text=result.summary, style="Ok.TLabel" if ok else "Error.TLabel")
        self.status_label.config(text="Cuando cierres DaVinci, podés expulsar el disco de forma segura.")
        self.open_btn.config(state="normal")
        self.report_btn.config(state="normal" if self.report_path else "disabled")
        self._refresh_disk()
        self.bell()

    def _apply_update(self) -> None:
        if not self.update_release:
            return
        if self.busy:
            messagebox.showinfo(APP_TITLE, "Esperá a que termine la descarga y después actualizá.")
            return
        release = self.update_release
        self.update_btn.config(state="disabled")
        self.update_label.config(text="Bajando la actualización…")

        def work():
            try:
                path = updater.download(release, lambda pct: self.events.put(
                    ("phase_update", pct)))
                self.events.put(("update_ready", path))
            except Exception as exc:  # noqa: BLE001
                log.exception("Falló la actualización")
                self.events.put(("update_failed", "No se pudo actualizar ahora. Podés seguir usando "
                                                  "esta versión y probar más tarde."))
        threading.Thread(target=work, daemon=True).start()

    def _open_dest(self) -> None:
        if self.result:
            open_path(self.result.dest)

    def _open_report(self) -> None:
        if self.report_path:
            open_path(self.report_path)

    def _on_close(self) -> None:
        if self.busy and self.job and not self.job.cancel.is_set():
            if not messagebox.askyesno(APP_TITLE, "Hay una descarga en curso. ¿Cerrar igual? "
                                                  "Lo descargado queda guardado y se puede retomar."):
                return
            self.job.cancel.set()
        self.destroy()


def run() -> None:
    App().mainloop()
