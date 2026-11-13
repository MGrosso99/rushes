# Traer material

App de escritorio para Windows que baja una carpeta compartida de Google Drive a un disco externo,
verifica que cada archivo llegó **idéntico** (MD5 contra Drive) y que cada video **se puede abrir** (ffprobe),
y deja un reporte. Se usa a demanda: no queda nada corriendo de fondo.

## Para ella

1. Conectar el disco externo.
2. Abrir **Traer material** desde el escritorio.
3. Pegar el link de Drive (y opcionalmente un nombre de proyecto) → **Revisar** → **Descargar**.
4. Al terminar: ✅/❌ por archivo, **Abrir carpeta**, **Ver reporte**.

Si se corta internet, se desconecta el disco o se cierra la app: abrir de nuevo con el **mismo link** retoma
donde quedó (va a la misma carpeta y solo baja lo que falta).

## Cómo funciona

```
Link de Drive ─► drive_link (valida, extrae ID)
              ─► disks      (busca el disco por NOMBRE de volumen, rechaza FAT32)
              ─► rclone size (resumen + chequeo de espacio)
              ─► rclone copy (prioridad baja; 1 transferencia si DaVinci está abierto)
              ─► rclone check --one-way (MD5 Drive vs disco)
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

Destino: `<Disco>:\Material\<AAAA-MM-DD> - <Nombre>\`. Datos locales en `%APPDATA%\TraerMaterial\`
(`config.json`, `rclone.conf`, `history.json`, `logs\`).

## Desarrollo

```powershell
python -m venv .venv; .\.venv\Scripts\activate
pip install pytest
pytest                                    # incluye un e2e con rclone falso
.\scripts\fetch_vendor.ps1 -UpdatePins    # baja rclone/ffprobe verificando SHA256
python -m traer_material                  # (con src en PYTHONPATH) abre la ventana
python -m traer_material --cli "<link>"   # modo consola para debug
```

Para probar sin disco externo: en `config.json` poner `"dest_override_path": "C:\\temp\\prueba"`.

## Build e instalación

```powershell
.\scripts\fetch_vendor.ps1          # usa los hashes fijados en vendor/checksums.txt
.\scripts\build.ps1                 # tests + PyInstaller + Inno Setup
# -> packaging\Output\TraerMaterial-Setup-<versión>.exe
```

Ver [docs/SETUP.md](docs/SETUP.md) (montaje paso a paso) y [docs/SEGURIDAD.md](docs/SEGURIDAD.md).

## Pendiente / ideas

- Probar en Windows real: `config create` de rclone con el navegador y detección de volúmenes.
- Botón "Proyectos viejos" para liberar espacio (listar carpetas en `Material\` con peso y fecha).
- Soportar links de archivos sueltos (`rclone backend copyid`).
- Ícono propio (`--icon` en PyInstaller y `SetupIconFile` en Inno Setup).
- Chequeo de actualizaciones contra GitHub Releases.
