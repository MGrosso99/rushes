# Rushes

App de escritorio para Windows que baja una carpeta compartida de Google Drive a un disco externo,
verifica que cada archivo llegó **idéntico** (MD5 contra Drive) y que cada video **se puede abrir** (ffprobe),
y deja un reporte. Se usa a demanda: no queda nada corriendo de fondo.

## Para ella

1. Conectar el disco externo.
2. Abrir **Rushes** desde el escritorio.
3. Pegar el link de Drive (y opcionalmente un nombre de proyecto) → **Revisar** → **Descargar**.
4. Al terminar: ✅/❌ por archivo, **Abrir carpeta**, **Ver reporte**.

Si se corta internet, se desconecta el disco o se cierra la app: abrir de nuevo con el **mismo link** retoma
donde quedó (va a la misma carpeta y solo baja lo que falta).

## Cómo funciona

```
Link de Drive ─► drive_link (valida, extrae ID)
              ─► disks      (carpeta elegida por ella; si cambia la letra del disco la encuentra por número de serie; rechaza FAT32)
              ─► rclone size (resumen + chequeo de espacio)
              ─► rclone copy (prioridad baja; 1 transferencia si DaVinci está abierto)
              ─► rclone check --one-way (MD5 Drive vs disco)
              ─► reintento: hasta 2 pasadas re-descargando SOLO los que fallaron
              ─► ffprobe     (cada video/audio se puede abrir, duración > 0)
              ─► _reporte/reporte.html + manifest.json
```

| Módulo | Qué hace |
|---|---|
| `app.py` | Ventana tkinter; el trabajo corre en un hilo y avisa por una cola |
| `job.py` | Orquesta prepare → run; historial link→carpeta para retomar |
| `rclone.py` | Wrapper de rclone, parseo de progreso JSON, errores traducidos a lenguaje simple |
| `verify.py` | ffprobe (rápido) y ffmpeg (profundo, opcional) |
| `disks.py` | Volúmenes de Windows por nombre, filesystem y espacio libre |
| `report.py` | Resultado, reporte HTML y manifest JSON |

Destino: `<carpeta elegida>\<AAAA-MM-DD> - <Nombre>\` (la primera vez la app pide elegirla; se cambia con «Cambiar…»). Datos locales en `%APPDATA%\Rushes\`
(`config.json`, `rclone.conf`, `history.json`, `logs\`).

## Desarrollo

```powershell
python -m venv .venv; .\.venv\Scripts\activate
pip install pytest
pytest                                    # incluye un e2e con rclone falso
.\scripts\fetch_vendor.ps1 -UpdatePins    # baja rclone/ffprobe verificando SHA256
python -m rushes                  # (con src en PYTHONPATH) abre la ventana
python -m rushes --cli "<link>"   # modo consola para debug
```

Para probar sin disco externo: en `config.json` poner `"dest_override_path": "C:\\temp\\prueba"`.

## Publicar una versión (desde la Mac, sin Windows)

1. Subir `__version__` en `src/rushes/__init__.py` (ej. `0.2.0`) y commitear.
2. `git tag v0.2.0 && git push origin main v0.2.0`
3. GitHub Actions (`.github/workflows/release.yml`) corre los tests en Windows, arma el instalador y crea
   la Release con `Rushes-Setup-0.2.0.exe` + `.sha256`.
4. La próxima vez que ella abra Rushes ve "Hay una versión nueva" → **Actualizar** (baja, verifica el
   SHA256, instala en silencio y reabre). Requiere `UPDATE_REPO = "usuario/rushes"` en `__init__.py`.

`ci.yml` corre los tests en cada push.

## Build local (en Windows)

```powershell
.\scripts\fetch_vendor.ps1          # usa los hashes fijados en vendor/checksums.txt
.\scripts\build.ps1                 # tests + PyInstaller + Inno Setup
# -> packaging\Output\Rushes-Setup-<versión>.exe
```

Ver [docs/SETUP.md](docs/SETUP.md) (montaje paso a paso) y [docs/SEGURIDAD.md](docs/SEGURIDAD.md).

## Pendiente / ideas

- Probar en Windows real: `config create` de rclone con el navegador y detección de volúmenes.
- Botón "Proyectos viejos" para liberar espacio (listar carpetas en `Rushes\` con peso y fecha).
- Soportar links de archivos sueltos (`rclone backend copyid`).
- Ícono propio (`--icon` en PyInstaller y `SetupIconFile` en Inno Setup).
