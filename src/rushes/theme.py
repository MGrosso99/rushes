"""Estilo visual de la ventana: solo ttk (tema "clam") con colores y tipografía propios.

Sin imágenes ni dependencias externas: no suma peso al instalador ni consume recursos.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .winutil import IS_WINDOWS

# Paleta: neutros cálidos + un acento azul. Contraste AA para texto.
BG = "#F5F5F3"          # fondo de la ventana
CARD = "#FFFFFF"        # tarjetas
BORDER = "#E3E1DB"      # bordes suaves
TEXT = "#1F1F1D"        # texto principal
MUTED = "#6B6A65"       # texto secundario
ACCENT = "#2F6FED"      # botón principal, progreso
ACCENT_HOVER = "#2559C4"
ACCENT_TEXT = "#FFFFFF"
OK = "#1E7A3C"
ERROR = "#B3261E"
ERROR_BG = "#FDECEC"
WARN_BG = "#FFF6E0"
DISABLED_BG = "#ECEBE7"
DISABLED_TEXT = "#A3A29C"


def enable_dpi_awareness() -> None:
    """Texto nítido en pantallas con escalado (125%, 150%...). Llamar ANTES de crear Tk()."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — Windows viejo: sigue sin escalado nítido
        pass


def scale(root: tk.Misc) -> float:
    """Factor de escala respecto de 96 DPI (1.0, 1.25, 1.5...)."""
    try:
        return max(1.0, float(root.tk.call("tk", "scaling")) * 72 / 96)
    except tk.TclError:
        return 1.0


def apply(root: tk.Tk) -> dict[str, tkfont.Font]:
    family = "Segoe UI" if IS_WINDOWS else tkfont.nametofont("TkDefaultFont").actual("family")
    semibold = "Segoe UI Semibold" if IS_WINDOWS else family

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=family, size=10)

    fonts = {
        "title": tkfont.Font(root, family=semibold, size=18),
        "subtitle": tkfont.Font(root, family=family, size=10),
        "caption": tkfont.Font(root, family=semibold, size=9),
        "body": tkfont.Font(root, family=family, size=10),
        "strong": tkfont.Font(root, family=semibold, size=10),
        "button": tkfont.Font(root, family=semibold, size=10),
    }
    s = scale(root)
    root.configure(background=BG)

    st = ttk.Style(root)
    st.theme_use("clam")

    # Base
    st.configure(".", background=CARD, foreground=TEXT, font=fonts["body"],
                 bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, focuscolor=ACCENT)
    st.configure("TFrame", background=CARD)
    st.configure("Bg.TFrame", background=BG)
    st.configure("Banner.TFrame", background=WARN_BG)

    # Textos
    st.configure("TLabel", background=CARD, foreground=TEXT)
    st.configure("Title.TLabel", background=BG, font=fonts["title"])
    st.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=fonts["subtitle"])
    st.configure("Caption.TLabel", foreground=MUTED, font=fonts["caption"])
    st.configure("Muted.TLabel", foreground=MUTED)
    st.configure("Path.TLabel", font=fonts["strong"])
    st.configure("Ok.TLabel", foreground=OK, font=fonts["strong"])
    st.configure("Error.TLabel", foreground=ERROR)
    st.configure("Banner.TLabel", background=WARN_BG)

    # Campos de texto
    st.configure("TEntry", fieldbackground=CARD, foreground=TEXT, padding=(8, int(6 * s)),
                 bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, insertcolor=TEXT)
    st.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
           fieldbackground=[("disabled", DISABLED_BG)], foreground=[("disabled", DISABLED_TEXT)])

    # Botones
    pad = (14, int(7 * s))
    st.configure("TButton", background=CARD, foreground=TEXT, font=fonts["button"], padding=pad,
                 bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, relief="flat", focusthickness=0)
    st.map("TButton",
           background=[("disabled", DISABLED_BG), ("pressed", "#E9E8E3"), ("active", "#F1F0EC")],
           foreground=[("disabled", DISABLED_TEXT)],
           lightcolor=[("active", "#F1F0EC")], darkcolor=[("active", "#F1F0EC")])

    st.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_TEXT, bordercolor=ACCENT,
                 lightcolor=ACCENT, darkcolor=ACCENT)
    st.map("Accent.TButton",
           background=[("disabled", DISABLED_BG), ("pressed", ACCENT_HOVER), ("active", ACCENT_HOVER)],
           foreground=[("disabled", DISABLED_TEXT)],
           bordercolor=[("disabled", DISABLED_BG)],
           lightcolor=[("disabled", DISABLED_BG), ("active", ACCENT_HOVER)],
           darkcolor=[("disabled", DISABLED_BG), ("active", ACCENT_HOVER)])

    st.configure("Link.TButton", background=CARD, foreground=ACCENT, bordercolor=CARD,
                 lightcolor=CARD, darkcolor=CARD, padding=(6, int(4 * s)))
    st.map("Link.TButton", foreground=[("active", ACCENT_HOVER), ("disabled", DISABLED_TEXT)],
           background=[("active", CARD)], bordercolor=[("active", CARD)])

    # Progreso: barra fina con el acento
    st.configure("Accent.Horizontal.TProgressbar", troughcolor="#ECEBE7", background=ACCENT,
                 bordercolor="#ECEBE7", lightcolor=ACCENT, darkcolor=ACCENT, thickness=int(6 * s))

    # Tabla de resultados
    st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                 rowheight=int(28 * s), bordercolor=CARD, lightcolor=CARD, darkcolor=CARD, borderwidth=0)
    st.map("Treeview", background=[("selected", "#E7EEFD")], foreground=[("selected", TEXT)])
    st.configure("Treeview.Heading", background=CARD, foreground=MUTED, font=fonts["caption"],
                 relief="flat", bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, padding=(6, 4))
    st.map("Treeview.Heading", background=[("active", CARD)])
    st.configure("Vertical.TScrollbar", background=CARD, troughcolor=CARD, bordercolor=CARD,
                 lightcolor=CARD, darkcolor=CARD, arrowcolor=MUTED)
    return fonts


def card(parent: tk.Misc, padding: int = 16) -> ttk.Frame:
    """Tarjeta blanca con borde suave. Devuelve el frame interior donde poner el contenido."""
    outer = tk.Frame(parent, background=CARD, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=BORDER, bd=0)
    inner = ttk.Frame(outer, padding=padding)
    inner.pack(fill="both", expand=True)
    inner.outer = outer  # type: ignore[attr-defined]
    return inner
