# Montaje paso a paso (lo hacés vos, una vez)

## 1. Google Cloud (≈15 min, sin costo)

> Opcional pero recomendado. Sin Client ID propio, rclone usa el suyo compartido, que funciona
> pero tiene cuota compartida con todos los usuarios de rclone y puede ir más lento.

1. <https://console.cloud.google.com> → crear proyecto `rushes`.
2. **APIs y servicios → Biblioteca** → habilitar **Google Drive API**.
3. **Pantalla de consentimiento OAuth** (Google Auth Platform):
   - Tipo de usuario: **Externo**.
   - Nombre de la app, mail de soporte = el tuyo.
   - Permisos: agregar `.../auth/drive.readonly`.
   - **Publicar la app → En producción.** ⚠️ En "Prueba" el token vence a los 7 días.
   - No hace falta enviarla a verificación: con menos de 100 usuarios funciona; Google solo
     muestra una pantalla de "app no verificada" la primera vez.
4. **Credenciales → Crear ID de cliente OAuth → App de escritorio.** Copiá Client ID y Client secret.

## 2. Preparar el disco externo

- Ponerle un nombre de volumen fijo, por ejemplo `RUSHES` (clic derecho en el disco → Cambiar nombre).
- Verificar el formato (Propiedades): **NTFS** ideal, exFAT ok, **FAT32 no** (máx. 4 GB por archivo).
- Conectarlo a un puerto **USB 3**.
- Panel de control → Opciones de energía → Configuración avanzada → USB → **Suspensión selectiva: Deshabilitada**.

## 3. Generar el instalador

**Recomendado: GitHub Actions** (no necesitás Windows):

1. Crear el repo **público** en GitHub y subirlo.
2. En `src/rushes/__init__.py`: `UPDATE_REPO = "<tu-usuario>/rushes"` (para las actualizaciones automáticas).
3. `git tag v0.1.0 && git push origin main v0.1.0` → en unos minutos, la Release tiene el instalador.

**Alternativa: en una PC Windows**

```powershell
git clone <repo>; cd rushes
.\scripts\fetch_vendor.ps1 -UpdatePins   # primera vez; commiteá vendor/checksums.txt
.\scripts\build.ps1
```

Necesitás Python 3.11+ e [Inno Setup 6](https://jrsoftware.org/isdl.php).

## 4. Instalar en la compu de ella

1. Copiar `Rushes-Setup-x.y.z.exe` y ejecutarlo. Si aparece SmartScreen:
   **Más información → Ejecutar de todas formas** (el instalador no está firmado).
2. Se instala por usuario en `%LOCALAPPDATA%\Programs\Rushes` (no pide admin) y crea el acceso directo.
3. Abrir la app una vez y cerrarla (crea `%APPDATA%\Rushes\config.json`).
4. Editar `config.json` (menú Ayuda → Editar configuración):
   ```json
   "disk_label": "RUSHES",
   "google_client_id": "xxxx.apps.googleusercontent.com",
   "google_client_secret": "GOCSPX-xxxx"
   ```
5. Abrir la app → **Conectar Google** → ella inicia sesión con SU cuenta (la que recibe las carpetas).
   En "Google no verificó esta app": **Avanzado → Ir a rushes** → Permitir.
6. **Moverle la caché de DaVinci al externo**: DaVinci → Preferencias → Media Storage → agregar una
   carpeta del disco externo arriba de todo (y sacar C: si está primero).

## 5. Prueba de humo

- Compartirle una carpeta de prueba con 2–3 videos y un PDF.
- Descargar, verificar que todo da ✅, abrir el reporte.
- Repetir con el mismo link → debería decir "ya hay X descargados" y terminar rápido.
- Desconectar el USB a mitad de una descarga → mensaje claro; reconectar y retomar.
- Con DaVinci abierto → el estado debe decir "modo liviano".

## Configuración (`config.json`)

| Clave | Default | Para qué |
|---|---|---|
| `disk_label` | `RUSHES` | Nombre de volumen del disco externo |
| `base_dir` | `Rushes` | Carpeta raíz dentro del disco |
| `dest_override_path` | `""` | Solo pruebas: ignora el disco y usa esta ruta |
| `transfers` | `3` | Descargas en paralelo |
| `transfers_when_resolve_open` | `1` | Ídem con DaVinci abierto |
| `bwlimit_when_resolve_open` | `""` | Ej. `"20M"` para limitar ancho de banda con DaVinci abierto |
| `min_free_margin_gb` | `10` | Espacio que siempre debe quedar libre |
| `deep_check` | `false` | Decodifica cada video completo (lento; requiere `-WithFfmpeg`) |
