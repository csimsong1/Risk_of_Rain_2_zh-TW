# Record the language strings a mod registers by executing its token methods.
# Rec.cs rewrites a copy of the mod DLL with Mono.Cecil: calls whose callee FullName matches -Record
# (static, 2 or 3 string args) go to Rec.R.Add/Add3, calls matching -Stub (regex on Type::Method)
# pop their arguments and push a default value. Then the -Pre and -Call methods are invoked
# (null/default arguments; instance methods on an uninitialized object) and the log is saved as
# JSON rows [token, text] or [token, text, language].
#
# Usage (one fresh powershell process per DLL; mods that touch BepInEx config need the 32-bit
# one, because BepInEx.dll is x86-only):
#   & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File tools\rec.ps1 `
#     -Dll <mod.dll> -Record <regex> [-Stub <regex>] -Call <Type::Method,...> [-Pre <Type::Method,...>] `
#     [-Out <json>] [-ProfileName <r2modman profile>]
#   -Out defaults to work\rec\<dll name>.json. -ProfileName (or $env:ROR2_PROFILE) is the profile
#   whose BepInEx core and plugins are used to resolve the mod's references.
#   PS 5.1 drops empty-string arguments to native exes, so leave -Stub out instead of passing "".
param([string]$Dll, [string]$Record, [string]$Stub = 'NEVER_MATCH_ANYTHING', [string]$Call, [string]$Out, [string]$Pre = '', [string]$ProfileName)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

if (-not $Dll -or -not $Record -or -not $Call) { throw 'Need -Dll, -Record and -Call' }
$Dll = Get-FullPath $Dll
if (-not $Out) { $Out = Join-Path (Get-ToolsWork 'rec') ([IO.Path]::GetFileNameWithoutExtension($Dll) + '.json') }
$Out = Get-FullPath $Out
$bep = Join-Path (Resolve-Ror2Profile $ProfileName) 'BepInEx'
$managed = Join-Path (Find-Ror2Game) 'Risk of Rain 2_Data\Managed'
$cecil = Join-Path $bep 'core\Mono.Cecil.dll'
$source = Join-Path $PSScriptRoot 'Rec.cs'

# Rec_4.dll / Rec_8.dll: the recorder compiled for the current bitness, rebuilt when Rec.cs changes.
$recDll = Join-Path (Get-ToolsWork 'bin') ('Rec_' + [IntPtr]::Size + '.dll')
if (-not (Test-Path -LiteralPath $recDll) -or (Get-Item -LiteralPath $recDll).LastWriteTime -lt (Get-Item -LiteralPath $source).LastWriteTime) {
  Add-Type -Path $cecil
  Add-Type -Path $source -ReferencedAssemblies $cecil, 'System.Core', 'System.Runtime.Serialization' -OutputAssembly $recDll -OutputType Library
}
[void][Reflection.Assembly]::LoadFrom($cecil)
$recAsm = [Reflection.Assembly]::LoadFrom($recDll)
$dirs = [string[]]@($managed, (Join-Path $bep 'core'), (Join-Path $bep 'plugins'))
[Rec.Resolver]::Install($dirs)

$sub = Get-ToolsWork ('rewritten\' + [IO.Path]::GetFileNameWithoutExtension($Out))
$rewritten = Join-Path $sub ([IO.Path]::GetFileName($Dll))
$n = [Rec.Rewriter]::Rewrite($Dll, $rewritten, $Record, $Stub, $recDll, $dirs)
"rewrote $n calls"
$asm = [Reflection.Assembly]::LoadFrom($rewritten)
foreach ($spec in @($Pre -split ',' | Where-Object { $_ }) + @($Call -split ',' | Where-Object { $_ })) {
  $spec + ' -> ' + [Rec.Runner]::Invoke($asm, $spec)
}
[Rec.R]::Save($Out)
'saved ' + [Rec.R]::Log.Count + ' entries to ' + $Out
