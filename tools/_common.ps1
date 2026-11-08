# Shared path helpers for the .ps1 tools. Dot-source it:  . (Join-Path $PSScriptRoot '_common.ps1')
# Keep this file ASCII-only: Windows PowerShell 5.1 reads BOM-less scripts as the ANSI code page.
# Only functions here (no script-level variables), because PowerShell variable names are
# case-insensitive and a dot-sourced variable would silently clobber a caller's parameter.
#
# Environment variables (all optional):
#   ROR2_PROFILE     r2modman profile name or folder (needed by rec.ps1)
#   ROR2_GAME        game folder (the one that contains "Risk of Rain 2_Data")
#   ROR2_TOOLS_WORK  output folder for dumps, rewritten DLLs and recordings (default tools\work)

function Get-R2mmDir {
  Join-Path $env:APPDATA 'r2modmanPlus-local\RiskOfRain2'
}

function Get-FullPath([string]$PathText) {
  # .NET calls resolve relative paths against the process directory, not the PowerShell location.
  $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PathText)
}

function Get-ToolsWork([string]$Sub) {
  $base = $env:ROR2_TOOLS_WORK
  if (-not $base) { $base = Join-Path $PSScriptRoot 'work' }
  $dir = $base
  if ($Sub) { $dir = Join-Path $base $Sub }
  New-Item -ItemType Directory -Force $dir | Out-Null
  Get-FullPath $dir
}

function Resolve-Ror2Profile([string]$Name) {
  if (-not $Name) { $Name = $env:ROR2_PROFILE }
  $root = Join-Path (Get-R2mmDir) 'profiles'
  if (-not $Name) {
    $names = @(Get-ChildItem -Directory $root | Where-Object { Test-Path (Join-Path $_.FullName 'BepInEx') } | ForEach-Object { $_.Name })
    throw ('Specify -ProfileName or set $env:ROR2_PROFILE. Profiles: ' + ($names -join ', '))
  }
  foreach ($candidate in @($Name, (Join-Path $root $Name))) {
    if (Test-Path -LiteralPath (Join-Path $candidate 'BepInEx\plugins')) { return (Get-FullPath $candidate) }
  }
  throw "r2modman profile not found: $Name"
}

function Find-Cecil([string]$Name) {
  # Mono.Cecil.dll ships in every BepInEx core folder; any profile will do unless one is named.
  if ($Name -or $env:ROR2_PROFILE) {
    $dll = Join-Path (Resolve-Ror2Profile $Name) 'BepInEx\core\Mono.Cecil.dll'
    if (Test-Path -LiteralPath $dll) { return $dll }
    throw "Mono.Cecil.dll not found: $dll"
  }
  $hit = Get-ChildItem (Join-Path (Get-R2mmDir) 'profiles\*\BepInEx\core\Mono.Cecil.dll') -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $hit) { throw 'Mono.Cecil.dll not found in any r2modman profile' }
  $hit.FullName
}

function Find-Ror2Game {
  # Same search order as ror2_s2t.find_game_dir: Steam libraries, then Epic.
  if ($env:ROR2_GAME) { return $env:ROR2_GAME }
  $candidates = @()
  try {
    $steam = (Get-ItemProperty -Path 'HKCU:\Software\Valve\Steam' -Name SteamPath -ErrorAction Stop).SteamPath
    $libraries = @($steam)
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
      foreach ($hit in [regex]::Matches((Get-Content -Raw -LiteralPath $vdf), '"path"\s+"([^"]+)"')) {
        $libraries += $hit.Groups[1].Value.Replace('\\', '\')
      }
    }
    foreach ($library in $libraries) { $candidates += Join-Path $library 'steamapps\common\Risk of Rain 2' }
  } catch {}
  $epic = Join-Path $env:ProgramData 'Epic\UnrealEngineLauncher\LauncherInstalled.dat'
  if (Test-Path -LiteralPath $epic) {
    try {
      foreach ($install in (Get-Content -Raw -LiteralPath $epic | ConvertFrom-Json).InstallationList) { $candidates += $install.InstallLocation }
    } catch {}
  }
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath (Join-Path $candidate 'Risk of Rain 2_Data\Managed')) { return $candidate }
  }
  throw 'Game folder not found; set $env:ROR2_GAME'
}

function Sort-Versions([string[]]$Versions) {
  # Numeric-aware sort for version folder names such as 2.3.9 / 2.3.10.
  $Versions | Sort-Object { ($_ -split '[.-]' | ForEach-Object { if ($_ -match '^\d+$') { '{0:D10}' -f [long]$_ } else { $_ } }) -join '.' }
}
