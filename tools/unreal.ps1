param(
    [ValidateSet('help', 'build', 'package', 'run')]
    [string]$Action = 'help',
    [string[]]$GameArgs = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($Action -eq 'help') {
    Write-Output 'Usage: tools/unreal.ps1 build|package|run [-GameArgs "-windowed"]'
    exit 0
}
if ($env:OS -ne 'Windows_NT') {
    throw 'This script requires Windows. Use tools/unreal.sh on Linux or macOS.'
}
$repoRoot = Split-Path -Parent $PSScriptRoot
$engineRoot = $env:UE_ROOT
if (-not $engineRoot) {
    $engineRoot = Join-Path $env:ProgramFiles 'Epic Games\UE_5.8'
}
$project = Join-Path $repoRoot 'FormulaForge.uproject'
$localRoot = Join-Path $repoRoot 'build\unreal'
if ($Action -ne 'run') {
    $versionFile = Join-Path $engineRoot 'Engine\Build\Build.version'
    if (-not (Test-Path -LiteralPath $versionFile)) {
        throw 'Set UE_ROOT to the Unreal installation containing Engine\Build\Build.version.'
    }
    $version = Get-Content -LiteralPath $versionFile -Raw | ConvertFrom-Json
    if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8 -or $version.PatchVersion -lt 3) {
        throw 'Unreal 5.8.3 or a newer 5.8 patch is required.'
    }
}
foreach ($directory in @('home', 'logs', 'tmp', 'ddc', 'shaders', 'dotnet', 'nuget')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $localRoot $directory) | Out-Null
}
$operationLock = $null
try {
    $operationLock = [System.IO.File]::Open((Join-Path $localRoot 'operation.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $env:TEMP = Join-Path $localRoot 'tmp'
    $env:TMP = $env:TEMP
    $env:DOTNET_CLI_HOME = Join-Path $localRoot 'dotnet'
    $env:NUGET_PACKAGES = Join-Path $localRoot 'nuget'
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
    $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
    $env:DOTNET_PROCESSOR_COUNT = '2'
    $env:UE_ENGINE_ROOT = $engineRoot
    $env:FF_REPO_ROOT = $repoRoot
    $env:uebp_LogFolder = Join-Path $localRoot 'logs\uat'
    $env:uebp_FinalLogFolder = $env:uebp_LogFolder
    $logRoot = Join-Path $localRoot 'logs'
    $packageLog = Join-Path $logRoot 'package.log'
    switch ($Action) {
        'build' {
            & (Join-Path $engineRoot 'Engine\Build\BatchFiles\Build.bat') FormulaForgeEditor Win64 Development $project -WaitMutex -MaxParallelActions=1 -NoUBA "-Log=$logRoot\build.log"
        }
        'package' {
            [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath', (Join-Path $localRoot 'ddc'), 'Process')
            $cookOptions = '-partialgc -notraceserver -NoCrashDialog -NoAnalytics -DDC=InstalledNoZenLocalFallback -NoSharedDDC'
            $uatArgs = @('BuildCookRun', "-project=$project", '-noP4', '-platform=Win64',
                '-clientconfig=Development', '-build', '-cook', '-stage', '-pak', '-iostore',
                '-compressed', '-unattended', '-utf8output', '-nocompileuat', '-nodebuginfo',
                "-stagingdirectory=$localRoot\package", '-ubtargs=-MaxParallelActions=1 -NoUBA',
                "-AdditionalCookerOptions=$cookOptions")
            Set-Content -LiteralPath $packageLog -Value ''
            & (Join-Path $engineRoot 'Engine\Build\BatchFiles\RunUAT.bat') @uatArgs | Tee-Object -FilePath $packageLog
        }
        'run' {
            $game = Join-Path $localRoot 'package\Windows\FormulaForge\Binaries\Win64\FormulaForge.exe'
            if (-not (Test-Path -LiteralPath $game)) {
                throw 'Run tools/unreal.ps1 package first.'
            }
            & $game "-UserDir=$localRoot\home/" -SaveToUserDir -NoSplash -NoSound -NoAnalytics -notraceserver "-abslog=$logRoot\game.log" @GameArgs
        }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Unreal $Action failed with exit code $LASTEXITCODE. See $logRoot."
    }
    if ($Action -eq 'package' -and (Select-String -LiteralPath $packageLog -Quiet -Pattern 'Failed to compile Material|ShaderCompileWorker.*crash|Fatal error:')) {
        throw 'Cook has shader errors.'
    }
}
finally {
    if ($null -ne $operationLock) {
        $operationLock.Dispose()
    }
}
