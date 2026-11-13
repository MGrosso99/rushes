; Instalador por usuario (no pide permisos de administrador).
; Compilar con: ISCC.exe /DAppVersion=0.1.0 packaging\installer.iss  (lo hace scripts\build.ps1)

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6B2F7C1E-8E0B-4E36-9A57-3C1D2E4F5A6B}}
AppName=Rushes
AppVersion={#AppVersion}
AppPublisher=Uso personal
DefaultDirName={localappdata}\Programs\Rushes
DefaultGroupName=Rushes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Rushes-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Rushes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; Flags: checkedonce

[Files]
Source: "..\dist\Rushes\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Rushes"; Filename: "{app}\Rushes.exe"
Name: "{userdesktop}\Rushes"; Filename: "{app}\Rushes.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Rushes.exe"; Description: "Abrir Rushes"; Flags: nowait postinstall skipifsilent

; Nota: al desinstalar NO se borra %APPDATA%\Rushes (config + token de Google).
; Para revocar el acceso: borrar esa carpeta y quitar la app en myaccount.google.com/permissions.
