# Dump every method body of an assembly as text, one instruction per line (Mono.Cecil, ~0.3 s per DLL).
# Format: "## <method full name>" then "<opcode> <operand>" lines; branch targets are "@<index>",
# strings are C#-escaped and quoted, floats use round-trip formatting.
#
# Usage:
#   ildump.ps1 -Dll <path> [-Out <path>]
#       One DLL; -Out defaults to work\il\<dll name>.il
#   ildump.ps1 -Mod <Author-Name> [-Old <version>] [-New <version>]
#       Every DLL of two versions in the r2modman cache (cache\<mod>\<version>\), written to
#       work\il\<mod>@<version>@<dll>.il for ildiff.py. Earlier dumps of that mod are removed first.
#       -New defaults to the newest cached version; -Old to the version in mods\<mod>.json when it
#       differs from -New, otherwise the second newest.
#   -ProfileName picks the profile whose BepInEx\core\Mono.Cecil.dll is used (default: any profile).
param([string]$Dll, [string]$Out, [string]$Mod, [string]$Old, [string]$New, [string]$ProfileName)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')

$cecil = Find-Cecil $ProfileName
Add-Type -Path $cecil
if (-not ('IlDump' -as [type])) {
Add-Type -ReferencedAssemblies $cecil -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using Mono.Cecil;
using Mono.Cecil.Cil;

public static class IlDump {
    static string Esc(string s) {
        var b = new StringBuilder("\"");
        foreach (char c in s) {
            if (c == '\\') b.Append("\\\\");
            else if (c == '"') b.Append("\\\"");
            else if (c == '\n') b.Append("\\n");
            else if (c == '\r') b.Append("\\r");
            else if (c == '\t') b.Append("\\t");
            else b.Append(c);
        }
        return b.Append('"').ToString();
    }
    public static void Run(string dll, string output) {
        var asm = AssemblyDefinition.ReadAssembly(dll);
        using (var w = new StreamWriter(output, false, new UTF8Encoding(false))) {
            foreach (var mod in asm.Modules) {
                foreach (var t in mod.GetTypes()) {
                    foreach (var m in t.Methods) {
                        if (!m.HasBody) continue;
                        w.WriteLine("## " + m.FullName);
                        var idx = new Dictionary<Instruction, int>();
                        int i = 0;
                        foreach (var ins in m.Body.Instructions) idx[ins] = i++;
                        foreach (var ins in m.Body.Instructions) {
                            object op = ins.Operand;
                            string s;
                            if (op == null) s = "";
                            else if (op is string) s = Esc((string)op);
                            else if (op is Instruction) s = "@" + idx[(Instruction)op];
                            else if (op is Instruction[]) {
                                var parts = new List<string>();
                                foreach (var x in (Instruction[])op) parts.Add("@" + idx[x]);
                                s = string.Join(",", parts.ToArray());
                            }
                            else if (op is float) s = ((float)op).ToString("R");
                            else if (op is double) s = ((double)op).ToString("R");
                            else s = op.ToString();
                            w.WriteLine(ins.OpCode.Name + " " + s);
                        }
                    }
                }
            }
        }
    }
}
'@
}

if ($Dll) {
  $Dll = Get-FullPath $Dll
  if (-not $Out) { $Out = Join-Path (Get-ToolsWork 'il') ([IO.Path]::GetFileName($Dll) + '.il') }
  $Out = Get-FullPath $Out
  [IlDump]::Run($Dll, $Out)
  "wrote $Out"
  return
}
if (-not $Mod) { throw 'Give -Dll <path> or -Mod <Author-Name>' }

$cacheDir = Join-Path (Get-R2mmDir) ('cache\' + $Mod)
if (-not (Test-Path -LiteralPath $cacheDir)) { throw "Not in the r2modman cache: $cacheDir" }
$versions = @(Sort-Versions @(Get-ChildItem -Directory -LiteralPath $cacheDir | ForEach-Object { $_.Name }))
if (-not $New) { $New = $versions[-1] }
if (-not $Old) {
  $modsFile = Join-Path (Split-Path -Parent $PSScriptRoot) ('mods\' + $Mod + '.json')
  if (Test-Path -LiteralPath $modsFile) {
    # Regex instead of ConvertFrom-Json: PS 5.1 rejects keys that differ only in case.
    $hit = [regex]::Match([IO.File]::ReadAllText($modsFile), '"version"\s*:\s*"([^"]+)"')
    if ($hit.Success -and $hit.Groups[1].Value -ne $New -and $versions -contains $hit.Groups[1].Value) { $Old = $hit.Groups[1].Value }
  }
  if (-not $Old) {
    $older = @($versions | Where-Object { $_ -ne $New })
    if ($older.Count -eq 0) { throw "Only one cached version of $Mod ($New)" }
    $Old = $older[-1]
  }
}
"$Mod : $Old -> $New  (cached: $($versions -join ', '))"

$ilDir = Get-ToolsWork 'il'
Remove-Item (Join-Path $ilDir ($Mod + '@*.il')) -ErrorAction SilentlyContinue
foreach ($version in @($Old, $New)) {
  $verDir = Join-Path $cacheDir $version
  if (-not (Test-Path -LiteralPath $verDir)) { throw "Version not cached: $verDir" }
  $seen = @{}
  foreach ($file in Get-ChildItem -LiteralPath $verDir -Recurse -Filter '*.dll') {
    if ($seen.ContainsKey($file.Name)) { Write-Warning "Skipping second $($file.Name): $($file.FullName)"; continue }
    $seen[$file.Name] = $true
    $target = Join-Path $ilDir ($Mod + '@' + $version + '@' + $file.Name + '.il')
    try {
      [IlDump]::Run($file.FullName, $target)
      "  $version $($file.Name)"
    } catch {
      Write-Warning "Not a .NET assembly or unreadable: $($file.FullName): $($_.Exception.Message)"
      Remove-Item -LiteralPath $target -ErrorAction SilentlyContinue
    }
  }
}
"dumps in $ilDir"
