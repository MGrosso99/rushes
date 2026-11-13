# Seguridad y credenciales

## Qué acceso tiene la app

- Permiso OAuth **`drive.readonly`**: puede listar y leer el Drive de ella. **No puede** crear, modificar,
  borrar ni compartir nada, aunque hubiera un bug.
- En el disco, solo usa `rclone copy` (nunca `sync`/`move`/`delete`): **nunca borra archivos locales**.

## Dónde están los secretos

| Dato | Dónde | Sensibilidad |
|---|---|---|
| Token OAuth (refresh token) | `%APPDATA%\Rushes\rclone.conf` | **Alta**: da lectura del Drive |
| Client ID / secret | `%APPDATA%\Rushes\config.json` | Baja: Google no los trata como secretos en apps de escritorio |
| Logs | `%APPDATA%\Rushes\logs\` | Baja: nombres de archivo y errores, sin tokens |

- `%APPDATA%` solo es accesible para su usuario de Windows (y administradores).
- `.gitignore` excluye `rclone.conf`, `config.json`, `*.token` y `.env`. **Nunca commitear credenciales.**
- El log de comandos omite la ruta del config y rclone no imprime tokens con `--log-level NOTICE`.
- Si querés más protección: rclone admite cifrar el config con contraseña (`rclone config` → *Set configuration
  password*), pero ella tendría que escribirla cada vez. Para una PC personal con cuenta de Windows con
  contraseña, no lo recomiendo: va en contra del "a prueba de todo".

## Revocar acceso (si se pierde/roba la compu o se deja de usar)

1. <https://myaccount.google.com/permissions> → quitar **rushes**. Invalida el token al instante.
2. Borrar `%APPDATA%\Rushes\`.
3. Si se filtró el client secret: Google Cloud → Credenciales → regenerar secret.

## Binarios de terceros

- `rclone.exe` y `ffprobe.exe` no van en el repo. `scripts/fetch_vendor.ps1` los baja de las fuentes
  oficiales (downloads.rclone.org y gyan.dev, la build de Windows que enlaza ffmpeg.org) y:
  1. compara el SHA256 contra el checksum publicado por la fuente, y
  2. contra el hash **fijado** en `vendor/checksums.txt` (commiteado). Si cambia, el build falla.
- Actualizar versiones = correr con `-UpdatePins`, revisar el diff de `checksums.txt` y commitear.
- Licencias: rclone es MIT; las builds de ffmpeg de gyan.dev son GPL. Para uso personal no hay problema;
  si algún día se distribuye, incluir los avisos de licencia.

## Entradas no confiables

- El link se valida con regex estricta (`[A-Za-z0-9_-]{10,}`) antes de pasarlo a rclone.
- Todos los subprocesos usan lista de argumentos, **nunca `shell=True`**.
- El nombre de proyecto se sanea (sin `<>:"/\|?*`, sin `..`, máx. 80 caracteres).
- Los archivos descargados solo se leen con ffprobe; no se ejecuta nada de lo que baja.

## Instalador

- Sin firma de código → SmartScreen avisa la primera vez. Firmarlo requiere un certificado pago
  (o Azure Trusted Signing). Para uso personal, alcanza con verificar que el `.exe` es el que generaste vos.
- Se instala por usuario, sin permisos de administrador.

## Actualizaciones automáticas

- La app consulta `api.github.com/repos/<UPDATE_REPO>/releases/latest` al abrir (sin credenciales).
- Solo acepta un instalador `Rushes-Setup-x.y.z.exe` cuya URL sea de las Releases de ESE repo, y solo si la
  Release publica también su `.sha256`. Verifica el hash antes de ejecutar; si no coincide, no instala.
- Ignora drafts y prereleases. Sin internet, no muestra nada.
- Riesgo principal: quien controle tu cuenta de GitHub puede publicar una versión. **Activá 2FA** y protegé
  los tags (Settings → Rules → tag rulesets) para que solo vos puedas crear `v*`.
- El workflow de release no usa Actions de terceros (publica con `gh`, que viene en el runner) y tiene
  solo permiso `contents: write`. `actions/checkout` y `actions/setup-python` son de GitHub; para fijarlas a un
  hash: `gh api repos/actions/checkout/commits/v4 --jq .sha` y usar `actions/checkout@<sha> # v4`.
- Antes del primer push, los commits deben salir con tu mail noreply de GitHub, no con uno personal.
