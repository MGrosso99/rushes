"""Estilo visual de Rushes: fondo cálido, acento verde, tarjetas y botones redondeados.

Todo con tkinter/ttk + Canvas (incluidos en Python): sin imágenes ni dependencias externas,
así que no suma peso al instalador ni consume recursos.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .winutil import IS_WINDOWS

# Paleta
BG = "#F7F6F2"            # fondo de la ventana (cálido)
CARD = "#FFFFFF"
BORDER = "#E8E5DD"
TEXT = "#1C2A22"          # casi negro con tinte verde
MUTED = "#6F7570"
CAPTION = "#8A8F8A"
ACCENT = "#2F5E3B"        # verde principal
ACCENT_HOVER = "#244A2E"
ACCENT_SOFT = "#EAF2EC"   # fondo suave verde (selección, etiquetas)
ACCENT_TEXT = "#FFFFFF"
OK = "#2F7A44"
OK_BG = "#E7F3EA"
WARN = "#C2501A"
WARN_BG = "#FCEFE6"
ERROR = "#B3261E"
ERROR_BG = "#FCECEB"
INFO = "#3A4FB0"
INFO_BG = "#ECEFFB"
DISABLED_BG = "#EFEDE7"
DISABLED_TEXT = "#A6A9A3"

FONTS: dict[str, tkfont.Font] = {}


def enable_dpi_awareness() -> None:
    """Texto nítido en pantallas con escalado (125%, 150%...). Llamar ANTES de crear Tk()."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass


def scale(root: tk.Misc) -> float:
    """Factor respecto de 96 DPI (1.0, 1.25, 1.5...)."""
    try:
        return max(1.0, float(root.tk.call("tk", "scaling")) * 72 / 96)
    except tk.TclError:
        return 1.0


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw) -> int:
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def apply(root: tk.Tk) -> dict[str, tkfont.Font]:
    family = "Segoe UI" if IS_WINDOWS else tkfont.nametofont("TkDefaultFont").actual("family")
    semi = "Segoe UI Semibold" if IS_WINDOWS else family
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=family, size=10)

    FONTS.update({
        "brand": tkfont.Font(root, family=semi, size=13),
        "eyebrow": tkfont.Font(root, family=semi, size=8),
        "title": tkfont.Font(root, family=semi, size=20),
        "subtitle": tkfont.Font(root, family=family, size=10),
        "card_title": tkfont.Font(root, family=semi, size=11),
        "caption": tkfont.Font(root, family=semi, size=8),
        "body": tkfont.Font(root, family=family, size=10),
        "strong": tkfont.Font(root, family=semi, size=10),
        "button": tkfont.Font(root, family=semi, size=10),
        "badge": tkfont.Font(root, family=semi, size=9),
    })
    s = scale(root)
    root.configure(background=BG)

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=CARD, foreground=TEXT, font=FONTS["body"],
                 bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, focuscolor=ACCENT)
    st.configure("TFrame", background=CARD)
    st.configure("Bg.TFrame", background=BG)
    st.configure("Banner.TFrame", background=ACCENT_SOFT)

    st.configure("TLabel", background=CARD, foreground=TEXT)
    st.configure("Bg.TLabel", background=BG)
    st.configure("Brand.TLabel", background=BG, font=FONTS["brand"])
    st.configure("Eyebrow.TLabel", background=BG, foreground=ACCENT, font=FONTS["eyebrow"])
    st.configure("Title.TLabel", background=BG, font=FONTS["title"])
    st.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=FONTS["subtitle"])
    st.configure("CardTitle.TLabel", font=FONTS["card_title"])
    st.configure("Caption.TLabel", foreground=CAPTION, font=FONTS["caption"])
    st.configure("Muted.TLabel", foreground=MUTED)
    st.configure("Path.TLabel", font=FONTS["strong"])
    st.configure("Ok.TLabel", foreground=OK, font=FONTS["strong"])
    st.configure("Error.TLabel", foreground=ERROR)
    st.configure("Banner.TLabel", background=ACCENT_SOFT, foreground=ACCENT, font=FONTS["strong"])

    st.configure("Accent.Horizontal.TProgressbar", troughcolor=DISABLED_BG, background=ACCENT,
                 bordercolor=DISABLED_BG, lightcolor=ACCENT, darkcolor=ACCENT, thickness=int(6 * s))

    st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                 rowheight=int(32 * s), bordercolor=CARD, lightcolor=CARD, darkcolor=CARD, borderwidth=0)
    st.map("Treeview", background=[("selected", ACCENT_SOFT)], foreground=[("selected", TEXT)])
    st.configure("Treeview.Heading", background=CARD, foreground=CAPTION, font=FONTS["caption"],
                 relief="flat", bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, padding=(8, 6))
    st.map("Treeview.Heading", background=[("active", CARD)])
    st.configure("Vertical.TScrollbar", background=CARD, troughcolor=CARD, bordercolor=CARD,
                 lightcolor=CARD, darkcolor=CARD, arrowcolor=CAPTION)
    return FONTS


# ---------------------------------------------------------------- widgets redondeados
class Card(tk.Canvas):
    """Tarjeta blanca con esquinas redondeadas. Poné el contenido en `card.inner`."""

    def __init__(self, master, padding: int = 18, radius: int = 14, outer_bg: str = BG, fill: bool = False):
        super().__init__(master, background=outer_bg, highlightthickness=0, bd=0)
        self._radius, self._fill = radius, fill
        self.inner = ttk.Frame(self, padding=padding)
        self._win = self.create_window(1, 1, window=self.inner, anchor="nw")
        self.bind("<Configure>", self._redraw)
        self.inner.bind("<Configure>", self._fit)

    def _fit(self, _event=None) -> None:
        h = self.inner.winfo_reqheight() + 2
        if not self._fill or self.winfo_height() < h:
            super().configure(height=h)

    def _redraw(self, event) -> None:
        w, h = event.width, event.height
        self.itemconfigure(self._win, width=max(1, w - 2))
        if self._fill:
            self.itemconfigure(self._win, height=max(1, h - 2))
        self.delete("bg")
        round_rect(self, 0, 0, w - 1, h - 1, self._radius, fill=CARD, outline=BORDER, tags="bg")
        self.tag_lower("bg")


class PillButton(tk.Canvas):
    """Botón redondeado. kind: primary (verde), secondary (blanco con borde), link (solo texto)."""

    COLORS = {
        "primary": (ACCENT, ACCENT_HOVER, ACCENT, ACCENT_TEXT),
        "secondary": (CARD, "#F3F2EE", BORDER, TEXT),
        "link": (CARD, CARD, CARD, ACCENT),
    }

    def __init__(self, master, text: str = "", command=None, kind: str = "secondary",
                 state: str = "normal", bg: str = CARD, padx: int = 16, pady: int = 7):
        super().__init__(master, background=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._text, self._command, self._kind, self._state = text, command, kind, state
        self._padx, self._pady, self._hover = padx, pady, False
        if kind == "link":
            self.COLORS = dict(self.COLORS, link=(bg, bg, bg, ACCENT))
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)
        self._draw()

    def _set_hover(self, value: bool) -> None:
        self._hover = value
        self._draw()

    def _click(self, _event) -> None:
        if self._state != "disabled" and self._command:
            self._command()

    def _draw(self) -> None:
        f = FONTS.get("button") or tkfont.nametofont("TkDefaultFont")
        w = f.measure(self._text) + 2 * self._padx
        h = f.metrics("linespace") + 2 * self._pady
        super().configure(width=w, height=h, cursor="arrow" if self._state == "disabled" else "hand2")
        self.delete("all")
        fill, hover, border, fg = self.COLORS[self._kind]
        if self._state == "disabled":
            if self._kind == "link":
                fill = border = self.COLORS["link"][0]
            else:
                fill, border = DISABLED_BG, DISABLED_BG
            fg = DISABLED_TEXT
        elif self._hover:
            fill = hover
            if self._kind == "link":
                fg = ACCENT_HOVER
        round_rect(self, 0, 0, w - 1, h - 1, h / 2, fill=fill, outline=border)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=f)

    def configure(self, cnf=None, **kw):  # compatible con .config(state=..., text=...)
        kw = dict(cnf or {}, **kw)
        changed = False
        for key, attr in (("text", "_text"), ("state", "_state"), ("command", "_command")):
            if key in kw:
                setattr(self, attr, kw.pop(key))
                changed = True
        if kw:
            super().configure(**kw)
        if changed:
            self._draw()

    config = configure


class Badge(tk.Canvas):
    """Etiqueta tipo píldora con color (ej. contador, estado)."""

    TONES = {"ok": (OK_BG, OK), "warn": (WARN_BG, WARN), "error": (ERROR_BG, ERROR),
             "info": (INFO_BG, INFO), "accent": (ACCENT_SOFT, ACCENT), "muted": ("#F1F0EC", MUTED)}

    def __init__(self, master, text: str = "", tone: str = "accent", bg: str = CARD):
        super().__init__(master, background=bg, highlightthickness=0, bd=0)
        self._text, self._tone = text, tone
        self._draw()

    def set(self, text: str, tone: str | None = None) -> None:
        self._text, self._tone = text, tone or self._tone
        self._draw()

    def _draw(self) -> None:
        f = FONTS.get("badge") or tkfont.nametofont("TkDefaultFont")
        w = max(f.measure(self._text) + 18, 26)
        h = f.metrics("linespace") + 6
        super().configure(width=w, height=h)
        self.delete("all")
        bg, fg = self.TONES[self._tone]
        round_rect(self, 0, 0, w - 1, h - 1, h / 2, fill=bg, outline=bg)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=f)


class RoundedEntry(tk.Canvas):
    """Campo de texto con borde redondeado que se pone verde al tener foco. Usá `.entry`."""

    def __init__(self, master, textvariable=None, placeholder: str = "", bg: str = CARD):
        super().__init__(master, background=bg, highlightthickness=0, bd=0)
        f = FONTS.get("body") or tkfont.nametofont("TkDefaultFont")
        self._h = f.metrics("linespace") + 18
        super().configure(height=self._h)
        self._focus = False
        self.entry = tk.Entry(self, textvariable=textvariable, relief="flat", bd=0, font=f,
                              background=CARD, foreground=TEXT, insertbackground=TEXT,
                              disabledbackground=DISABLED_BG, disabledforeground=DISABLED_TEXT,
                              highlightthickness=0)
        self._win = self.create_window(14, self._h / 2, window=self.entry, anchor="w")
        self.bind("<Configure>", self._redraw)
        self.entry.bind("<FocusIn>", lambda e: self._set_focus(True), add="+")
        self.entry.bind("<FocusOut>", lambda e: self._set_focus(False), add="+")

    def _set_focus(self, value: bool) -> None:
        self._focus = value
        self._redraw()

    def configure(self, cnf=None, **kw):  # .config(state=...) se aplica al campo
        kw = dict(cnf or {}, **kw)
        if "state" in kw:
            self.entry.configure(state=kw.pop("state"))
            self._redraw()
        if kw:
            super().configure(**kw)

    config = configure

    def _redraw(self, _event=None) -> None:
        w = self.winfo_width()
        if w <= 1:
            return
        self.itemconfigure(self._win, width=max(1, w - 28))
        self.delete("bg")
        disabled = str(self.entry.cget("state")) == "disabled"
        fill = DISABLED_BG if disabled else CARD
        outline = ACCENT if self._focus else BORDER
        round_rect(self, 0, 0, w - 1, self._h - 1, 10, fill=fill, outline=outline, width=1.5 if self._focus else 1,
                   tags="bg")
        self.tag_lower("bg")


def logo(master, size: int = 30, bg: str = BG) -> tk.Canvas:
    c = tk.Canvas(master, width=size, height=size, background=bg, highlightthickness=0, bd=0)
    round_rect(c, 0, 0, size - 1, size - 1, size * 0.28, fill=ACCENT, outline=ACCENT)
    c.create_text(size / 2, size / 2, text="R", fill=ACCENT_TEXT,
                  font=FONTS.get("brand") or tkfont.nametofont("TkDefaultFont"))
    return c
