# Política de privacidad de Rushes

_Última actualización: 13 de noviembre de 2026_

Rushes es una aplicación de escritorio para Windows que descarga carpetas de Google Drive a un disco
local y verifica que los archivos lleguen completos. Es un proyecto personal, sin fines comerciales.

## Qué datos usa

- **Acceso a Google Drive (solo lectura, permiso `drive.readonly`).** Rushes lista y descarga
  únicamente las carpetas cuyo link pega la persona usuaria. No puede crear, modificar, borrar ni
  compartir archivos de su Drive.
- **Token de acceso de Google.** Se guarda solo en la computadora de la persona usuaria
  (`%APPDATA%\Rushes\rclone.conf`). Nunca se envía a otro lugar.
- **Archivos descargados.** Se guardan solo en el disco que elige la persona usuaria.
- **Registros técnicos (logs).** Se guardan solo en esa computadora (`%APPDATA%\Rushes\logs`) y
  no contienen tokens ni contraseñas.

## Qué NO hace

- No envía datos de Google Drive ni de la persona usuaria al desarrollador ni a terceros.
- No tiene servidores propios, analítica, publicidad ni rastreo.
- No vende ni comparte datos con nadie.

La única conexión además de Google Drive es una consulta anónima a GitHub para saber si hay una
versión nueva de la app.

## Uso de datos de Google

El uso que hace Rushes de la información recibida de las APIs de Google cumple con la
[Política de datos de usuario de los servicios de API de Google](https://developers.google.com/terms/api-services-user-data-policy),
incluidos los requisitos de uso limitado.

## Cómo revocar el acceso

En cualquier momento, desde <https://myaccount.google.com/permissions> → Rushes → Quitar acceso.
Para borrar todo rastro local: desinstalar Rushes y borrar la carpeta `%APPDATA%\Rushes`.

## Contacto

Consultas a través del repositorio: <https://github.com/MGrosso99/rushes/issues>.
