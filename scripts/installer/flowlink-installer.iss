; FlowLink Proxy — Inno Setup Installer
; Version 0.3.0
; Requires: Inno Setup 6+

#define MyAppName "FlowLink Proxy"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "FlowLink"
#define MyAppURL "https://github.com/anomalyco/flowlink-proxy"
#define MyAppExeName "FlowLink Proxy.exe"

[Setup]
AppId={{A3F5B2C1-7E4D-4A9B-8F6E-2D1C3B5A7E9F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile=..\..\EULA.rtf
OutputDir=..\Output
OutputBaseFilename=FlowLink-Proxy-v{#MyAppVersion}-Setup
SetupIconFile=..\icons\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
ForceCloseApplications=yes
WizardStyle=modern
DisableProgramGroupPage=yes
DisableReadyPage=no
ShowLanguageDialog=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: checkedonce
Name: "autostart"; Description: "Запускать FlowLink Proxy при входе в Windows"; GroupDescription: "Автозапуск:"; Flags: checkedonce

[Files]
Source: "..\..\releases\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\releases\flowlink-proxy.crx"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\EULA.rtf"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить FlowLink Proxy сейчас"; Flags: nowait postinstall skipifsilent

[Registry]
; Автозапуск с системой (только при выборе задачи autostart)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppName}"; \
    ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: autostart

[Code]
// Завершение работающего процесса перед обновлении
procedure CurStepChanged(CurStep: TSetupStep);
var
    ResultCode: Integer;
begin
    if CurStep = ssInstall then
    begin
        Exec('taskkill', '/f /im {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
end;

// Удаление автозапуска при деинсталляции
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
    ResultCode: Integer;
begin
    if CurUninstallStep = usUninstall then
    begin
        Exec('taskkill', '/f /im {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#MyAppName}');
    end;
end;
