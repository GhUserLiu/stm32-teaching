# ASCII-only build helper for F103 training projects (avoids PS5 GBK/UTF-8 issues)
# Usage: powershell -ExecutionPolicy Bypass -File build_f1.ps1 <project-name>
$ErrorActionPreference = 'Stop'
$gcc  = 'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-gcc.exe'
$size = 'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-size.exe'
$root = Join-Path $PSScriptRoot '..'          # repo root (script lives in scripts/)
$proj = $args[0]
$inc  = @("-I$root\src\common-f1\inc", "-I$root\src\projects\$proj")
$cf   = @('-mcpu=cortex-m3','-mthumb','-Wall','-Wextra','-std=c11','-O0','-g3')
$out  = "$root\outputs\build\$proj"
New-Item -ItemType Directory -Force $out | Out-Null
Remove-Item "$out\*.obj" -ErrorAction SilentlyContinue

$files = @(Get-ChildItem "$root\src\projects\$proj\*.c") + @(Get-ChildItem "$root\src\common-f1\src\*.c") + @("$root\src\common-f1\startup\startup_stm32f103.s")
$objs = @()
foreach ($f in $files) {
    $path = if ($f -is [string]) { $f } else { $f.FullName }
    $base = [System.IO.Path]::GetFileNameWithoutExtension($path)
    $o = Join-Path $out ($base + '.obj')
    & $gcc @cf @inc -c $path -o $o
    if ($LASTEXITCODE -ne 0) { throw "compile fail: $path" }
    $objs += $o
}
& $gcc '-mcpu=cortex-m3' '-mthumb' "-T$root\src\common-f1\startup\stm32f103c8.ld" '-Wl,--gc-sections' '--specs=nano.specs' '--specs=nosys.specs' @objs '-lm' -o "$out\$proj.elf"
if ($LASTEXITCODE -ne 0) { throw 'link fail' }
& $size "$out\$proj.elf"
Write-Host "BUILD OK: $out\$proj.elf"
