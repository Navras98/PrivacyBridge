; PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
; Script Inno Setup per l'installer Windows.
; Da compilare con Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;
; Prerequisiti (una volta), dalla radice del progetto:
;   1. Su una macchina Windows, con Python 3.11+ e Inno Setup installati:
;      py -m venv venv && venv\Scripts\activate
;      pip install -r requirements.txt pyinstaller
;      pyinstaller --clean --noconfirm --workpath build\pyinstaller ^
;          --distpath dist build\PrivacyBridge.spec
;   2. Copia il modello dentro il bundle. Su Windows PyInstaller non
;      produce un .app ma la cartella dist\PrivacyBridge\, quindi il
;      modello va accanto all'exe e non in Contents\Resources:
;      xcopy /E /I "<sorgente-modello>" "dist\PrivacyBridge\modello"
;      (vedi docs\BLOCCHI.md § 11: questo passo non è mai stato
;       eseguito su una macchina Windows reale)
;   3. Compila questo .iss con Inno Setup Compiler → produce
;      Output\PrivacyBridge-Setup.exe

#define AppName "PrivacyBridge"
#define AppVersion "1.0.0"
#define AppPublisher "Andrea Sforna"
#define AppExeName "PrivacyBridge.exe"

[Setup]
AppId={{7A5B3C9E-1D2F-4A6B-8C1D-3E4F5A6B7C8D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename=PrivacyBridge-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\LICENSE

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea icona sul desktop"; \
    GroupDescription: "Aggiuntive:"; Flags: unchecked

[Files]
; Bundle costruito da PyInstaller: `dist\PrivacyBridge\` contiene
; PrivacyBridge.exe + tutte le dipendenze + il modello copiato dopo
; il build. La cartella `_internal\` di PyInstaller resta com'è.
Source: "..\dist\PrivacyBridge\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Disinstalla {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Avvia {#AppName}"; \
    Flags: nowait postinstall skipifsilent
