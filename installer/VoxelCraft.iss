; Voxel Craft Desktop Application - Inno Setup Script
; ================================================
; Antigravity Style Modern Installer
; Requires Inno Setup 6.x

#define AppName "Voxel Craft"
#define AppVersion "1.0.0"
#define AppPublisher "Voxel Craft"
#define AppURL "https://voxelcraft.onrender.com"
#define AppExeName "VoxelCraft.exe"
#define AppGUID "{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}"

[Setup]
AppId={#AppGUID}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/support
AppUpdatesURL={#AppURL}/updates
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=setup_assets\LICENSE.txt
OutputDir=output
OutputBaseFilename=VoxelCraft_Setup_v{#AppVersion}
SetupIconFile=setup_assets\logo.ico

; Antigravity Style - Large modern installer window
WizardImageFile=setup_assets\logo_large.bmp
WizardSmallImageFile=setup_assets\logo_small.bmp

; Compression settings - Maximum compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=8

; Antigravity modern style
WizardStyle=modern
WizardSizePercent=120
WizardResizable=yes
WindowShowCaption=yes
WindowVisible=yes
WindowStartMaximized=no

; Privileges and architecture
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Disable unused pages for cleaner experience
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=no
DisableReadyPage=no
DisableFinishedPage=no

; Uninstall Settings
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
CreateUninstallRegKey=yes

; Version Info
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Desktop Application Installer
VersionInfoCopyright=Copyright (c) 2024 {#AppPublisher}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

; Additional setup options
ShowLanguageDialog=no
AlwaysShowComponentsList=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main executable (all dependencies bundled via PyInstaller)
Source: "..\dist\VoxelCraft.exe"; DestDir: "{app}"; Flags: ignoreversion

; Assets directory (icons, logos, etc.)
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; Documentation (optional)
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\logo\logo.ico"
Name: "{group}\{cm:ProgramOnTheWeb,{#AppName}}"; Filename: "{#AppURL}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\logo\logo.ico"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon; IconFilename: "{app}\assets\logo\logo.ico"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Add to installed programs with proper uninstall info
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}"; ValueType: string; ValueName: "DisplayName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#AppVersion}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}"; ValueType: string; ValueName: "Publisher"; ValueData: "{#AppPublisher}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{#AppURL}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}"; ValueType: string; ValueName: "InstallLocation"; ValueData: "{app}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}"; ValueType: string; ValueName: "UninstallString"; ValueData: "{uninstallexe}"
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}"; ValueType: string; ValueName: "DisplayIcon"; ValueData: "{app}\assets\logo\logo.ico"

[Dirs]
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\output"; Permissions: users-modify

[Messages]
; Custom messages for better user experience
WelcomeLabel1=Welcome to the [name] Setup Wizard
WelcomeLabel2=This will install [name] [ver] on your computer.%n%nIt is recommended that you close all other applications before continuing.
SelectDirDesc=Where should [name] be installed?
SelectDirLabel3=Setup will install [name] into the following folder.
SelectDirBrowseLabel=To continue, click Next. If you would like to select a different folder, click Browse.
ReadyLabel1=Setup is now ready to begin installing [name] on your computer.
FinishedHeadingLabel=Completing the [name] Setup Wizard
FinishedLabel=Setup has finished installing [name] on your computer. The application may be launched by selecting the installed shortcuts.
ClickFinish=Click Finish to exit Setup.

[Code]
procedure CreateEnvFile;
var
  EnvFilePath: string;
begin
  EnvFilePath := ExpandConstant('{app}\.env');
  
  // Only create .env if it doesn't exist
  if not FileExists(EnvFilePath) then
  begin
    // Copy from .env.example
    FileCopy(ExpandConstant('{app}\.env.example'), EnvFilePath, False);
  end;
end;

// Check if app is already running
function InitializeSetup: Boolean;
var
  OldVersion: String;
  UninstallPath: String;
  ErrorCode: Integer;
begin
  // Check for previous version
  if RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppName}_is1',
    'UninstallString', UninstallPath) then
  begin
    UninstallPath := RemoveQuotes(UninstallPath);
    if MsgBox('An older version of {#AppName} is installed. Do you want to uninstall it first?', 
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      UninstallPath := RemoveQuotes(UninstallPath);
      Exec(UninstallPath, '/SILENT /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
    end;
  end;
  
  Result := True;
end;

// Clean up on uninstall
function InitializeUninstall: Boolean;
begin
  if MsgBox('Are you sure you want to uninstall {#AppName}?', mbConfirmation, MB_YESNO) = IDYES then
    Result := True
  else
    Result := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Ask to remove user data
    if MsgBox('Do you want to remove all application data including logs and output files?', 
      mbConfirmation, MB_YESNO) = IDYES then
    begin
      // Remove data directories
      DelTree(ExpandConstant('{app}\logs'), True, True, True);
      DelTree(ExpandConstant('{app}\output'), True, True, True);
      DelTree(ExpandConstant('{app}\assets'), True, True, True);
    end;
  end;
end;
