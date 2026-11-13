"""Extrae el ID de carpeta (y resource key) de un link de Google Drive."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")


class LinkError(ValueError):
    """Link inválido; el mensaje está pensado para mostrarse a la usuaria."""


@dataclass(frozen=True)
class DriveFolder:
    folder_id: str
    resource_key: str | None = None


def parse_drive_link(link: str) -> DriveFolder:
    link = (link or "").strip()
    if not link:
        raise LinkError("Pegá el link de la carpeta de Google Drive.")

    if _ID_RE.match(link):  # pegaron el ID directo
        return DriveFolder(link)

    url = urlparse(link if "://" in link else "https://" + link)
    if url.hostname not in {"drive.google.com", "docs.google.com"}:
        raise LinkError("Ese link no es de Google Drive. Copiá el link de la carpeta que te compartieron.")

    query = parse_qs(url.query)
    resource_key = (query.get("resourcekey") or [None])[0]
    parts = [p for p in url.path.split("/") if p]

    if "file" in parts and "d" in parts:
        raise LinkError(
            "Ese link es de un archivo suelto, no de una carpeta. "
            "Pedile al filmmaker el link de la carpeta."
        )

    folder_id = None
    if "folders" in parts:
        idx = parts.index("folders")
        if idx + 1 < len(parts):
            folder_id = parts[idx + 1]
    elif "id" in query:
        folder_id = query["id"][0]

    if not folder_id or not _ID_RE.match(folder_id):
        raise LinkError("No pude leer la carpeta en ese link. Copiá el link completo desde Drive.")

    return DriveFolder(folder_id, resource_key)
