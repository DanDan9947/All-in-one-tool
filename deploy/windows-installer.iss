#define AppName "蛋蛋小工具"
#define AppVersion "1.0.0"
#define AppExecutable "蛋蛋小工具.exe"
#ifndef PortableSource
#define PortableSource "..\dist\蛋蛋小工具"
#endif
#ifndef InstallerOutputDir
#define InstallerOutputDir "..\dist"
#endif

[Setup]
AppId={{06A8EFC0-FA26-4F83-900D-F7D10D58F19A}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#InstallerOutputDir}
OutputBaseFilename=DandanTools-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\dandan-logo.ico
WizardSmallImageFile=assets\dandan-wizard-small.bmp
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExecutable}
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Windows 安装程序

[Languages]
Name: "chinesesimplified"; MessagesFile: "assets\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Files]
Source: "{#PortableSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExecutable}"; WorkingDir: "{app}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExecutable}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExecutable}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Temp\wechat-image-tools\recordings"
Type: filesandordirs; Name: "{localappdata}\Temp\wechat-pdf-conversions"
