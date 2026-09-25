; Sage setup wizard and uninstaller (Inno Setup 6).
; Built by builder.py, which passes AppVersion, SourceDir and the output folder.
;
; Install:   copies the compiled app to Program Files, optionally adds it to PATH,
;            then runs "sage install" to create the locked-down data directory.
; Uninstall: offers to revert every applied tweak (last chance: snapshots are
;            deleted next), then removes the app, the data directory
;            (%ProgramData%\Sage: snapshots and logs), the PATH entry and the
;            Apps & Features entry. Nothing Sage created is left behind.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\sage"
#endif

[Setup]
AppId={{944D56DD-5E78-4B88-A20A-7FB484054985}
AppName=Sage
AppVersion={#AppVersion}
AppVerName=Sage {#AppVersion}
AppPublisher=Rodrigo Bechara
DefaultDirName={autopf}\Sage
; Fixed install folder: the uninstaller deletes {app} recursively, so it must never
; point at a folder that holds anything else.
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ChangesEnvironment=yes
OutputDir=..\dist\installer
OutputBaseFilename=sage-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Sage
UninstallDisplayIcon={app}\sage.exe

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
ptbr.AddToPath=Adicionar o Sage ao PATH (permite usar o comando "sage" em qualquer terminal)
en.AddToPath=Add Sage to PATH (lets you run "sage" from any terminal)
ptbr.InstallStepFailed=Os arquivos foram instalados, mas a criação da pasta de dados protegida falhou (código %1).%n%nAbra um terminal como Administrador e execute:%n    sage install
en.InstallStepFailed=Files were installed, but creating the protected data directory failed (code %1).%n%nOpen an Administrator terminal and run:%n    sage install
ptbr.AskRevert=Deseja reverter todas as otimizações que o Sage aplicou neste computador?%n%nRecomendado: os backups usados para reverter serão apagados na desinstalação. Se escolher "Não", as alterações continuarão no Windows e não poderão mais ser desfeitas pelo Sage.
en.AskRevert=Revert every optimization Sage applied to this computer?%n%nRecommended: the backups used to revert are deleted during uninstall. If you choose "No", the changes stay in Windows and Sage can no longer undo them.
ptbr.RevertFailed=Algumas otimizações não puderam ser revertidas.%n%nPara ver os detalhes, cancele e execute "sage revert-all" num terminal como Administrador.%n%nDesinstalar mesmo assim? Os backups serão apagados.
en.RevertFailed=Some optimizations could not be reverted.%n%nTo see details, cancel and run "sage revert-all" from an Administrator terminal.%n%nUninstall anyway? The backups will be deleted.

[Tasks]
Name: "addtopath"; Description: "{cm:AddToPath}"

[InstallDelete]
; On upgrade, drop the previous build's libraries so no stale files linger.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; Everything created at run time, not only what the installer copied.
Type: filesandordirs; Name: "{commonappdata}\Sage"
Type: filesandordirs; Name: "{app}"

[Code]
const
  EnvKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

function SageExe(): String;
begin
  Result := ExpandConstant('{app}\sage.exe');
end;

procedure AddToPath(Dir: String);
var
  Paths: String;
begin
  if not RegQueryStringValue(HKLM, EnvKey, 'Path', Paths) then
    Paths := '';
  if Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') > 0 then
    Exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then
    Paths := Paths + ';';
  RegWriteExpandStringValue(HKLM, EnvKey, 'Path', Paths + Dir);
end;

procedure RemoveFromPath(Dir: String);
var
  Paths: String;
  P: Integer;
begin
  if not RegQueryStringValue(HKLM, EnvKey, 'Path', Paths) then
    Exit;
  Paths := ';' + Paths + ';';
  P := Pos(';' + Uppercase(Dir) + ';', Uppercase(Paths));
  if P = 0 then
    Exit;
  Delete(Paths, P, Length(Dir) + 1);
  RegWriteExpandStringValue(HKLM, EnvKey, 'Path', Copy(Paths, 2, Length(Paths) - 2));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;
  if WizardIsTaskSelected('addtopath') then
    AddToPath(ExpandConstant('{app}'));
  if not Exec(SageExe(), 'install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
     or (ResultCode <> 0) then
    SuppressibleMsgBox(FmtMessage(CustomMessage('InstallStepFailed'), [IntToStr(ResultCode)]),
      mbError, MB_OK, IDOK);
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if not FileExists(SageExe()) then
    Exit;
  if SuppressibleMsgBox(CustomMessage('AskRevert'), mbConfirmation, MB_YESNO, IDYES) <> IDYES then
    Exit;
  if not Exec(SageExe(), 'revert-all', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
     or (ResultCode <> 0) then
    Result := SuppressibleMsgBox(CustomMessage('RevertFailed'), mbError, MB_YESNO, IDNO) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
