; Inno Setup script for SayIt (Windows installer)
; Produces SayIt-Setup-x64.exe with Start Menu / optional Desktop shortcuts and
; an uninstaller. The product presents to users as "SayIt". Internal technical
; identifiers (the executable name, package, and the %LOCALAPPDATA%\SayIt
; data directory) are "SayIt".

#define MyAppName "SayIt"
#ifndef MyAppVersion
  #define MyAppVersion "0.1.2"
#endif
#define MyAppPublisher "SayIt"
#define MyAppURL "https://github.com/VptrCipher/SayIt"
; The Briefcase-built executable is named SayIt.exe (technical identifier).
#define MyAppExeName "SayIt.exe"
#define MyAppIcon "icons\sayit.ico"

[Setup]
; Unique application identifier - NEVER change this after first release.
AppId={{13AD1DC3-955C-4618-86E0-36B01ABF13EF}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; Output settings - the installer is created in installer-output/.
OutputDir=installer-output
OutputBaseFilename=SayIt-Setup-x64
; Compression settings
Compression=lzma2
SolidCompression=yes
; Windows version requirements
MinVersion=10.0
; Installer appearance
SetupIconFile={#MyAppIcon}
WizardStyle=modern
; Privilege requirements - install for current user by default (no UAC prompt).
; App installs to: C:\Users\<User>\AppData\Local\Programs\SayIt
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; 64-bit architecture settings
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start SayIt when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Install all files from the Briefcase build folder. Briefcase places the app
; (executable + bundled Python runtime + resources) under app\src.
Source: "build\sayit\windows\app\src\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; NOTE: User data (settings, downloaded models, vocabulary, logs, history) lives
; in %LOCALAPPDATA%\SayIt and is intentionally NOT removed automatically on
; uninstall, so reinstalling preserves the user's setup and ~100MB-1GB models.
; The user is offered an explicit choice at uninstall time (see [Code]). SayIt
; also provides an in-app "Clear Data" action for users who want a full wipe.

[Code]
// Kill the running process before uninstalling to release file locks.
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM {#MyAppExeName} /T', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
  Result := True;
end;

// On uninstall, ASK before deleting user data (settings + downloaded models).
// Default is to KEEP it, so an accidental uninstall never destroys a user's
// multi-hundred-MB model cache or their configuration.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\SayIt');
    if DirExists(DataDir) then
    begin
      if MsgBox('Also delete SayIt user data (settings and downloaded speech models) in'
                + #13#10 + DataDir + '?' + #13#10 + #13#10
                + 'Choose No to keep your settings and models for a future reinstall.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;

