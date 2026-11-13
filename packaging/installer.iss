; Instalador por usuario (no pide permisos de administrador).
; Compilar con: ISCC.exe /DAppVersion=0.1.0 packaging\installer.iss  (lo hace scripts\build.ps1)

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6B2F7C1E-8E0B-4E36-9A57-3C1D2E4F5A6B}}
AppName=Traer material
AppVersion={#AppVersion}
AppPublisher=Uso personal
DefaultDirName={localappdata}\Programs\TraerMaterial
DefaultGroupName=Traer material
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=TraerMaterial-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Traer material

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; Flags: checkedonce

[Files]
Source: "..\dist\TraerMaterial\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Traer material"; Filename: "{app}\TraerMaterial.exe"
Name: "{userdesktop}\Traer material"; Filename: "{app}\TraerMaterial.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TraerMaterial.exe"; Description: "Abrir Traer material"; Flags: nowait postinstall skipifsilent

; Nota: al desinstalar NO se borra %APPDATA%\TraerMaterial (config + token de Google).
; Para revocar el acceso: borrar esa carpeta y quitar la app en myaccount.google.com/permissions.
