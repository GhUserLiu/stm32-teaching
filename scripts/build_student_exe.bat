@echo off
REM ============================================================
REM 学生端作业自检与自评系统 — 打包脚本（Windows，单一通用产物）
REM Student Self-Check & Self-Grade GUI — universal build (conda)
REM
REM 用法：在仓库根目录执行  scripts\build_student_exe.bat
REM 产物：dist\StudentSelfCheck.exe（单文件，无控制台，覆盖 Win7/8.1/10/11）
REM
REM 为什么用 conda + Python 3.8 + PyQt5：
REM   历史上学生端用 Python 3.13 + PyQt6 打包，在 Windows 7 上启动即崩——
REM   Python 3.9+ 依赖 api-ms-win-core-path-l1-1-0.dll（Win7 无此 API Set），
REM   且 Qt6 运行时最低要求 Windows 10 1809+。改用 Python 3.8（最后一个支持
REM   Win7 的 CPython）+ PyQt5==5.15.2（Qt 5.15.2 = 最后一个官方支持 Win7 的 Qt）
REM   后，单一 exe 即可覆盖 Win7/8.1/10/11，不再需要分发两个 exe。
REM
REM   学生端 GUI 代码通过 qt_compat.py 双绑定 shim 同时支持 PyQt5（本构建）
REM   与 PyQt6（开发机/教师端主线），故本脚本是学生端唯一需要的构建。
REM
REM 关键点：
REM   - 独立 conda 环境 stm32f407-win7（不污染 base/其它环境）。
REM   - 固定 numpy<2（避免 numpy 2.x 与 PyInstaller 的 CPU dispatcher 冲突）。
REM   - py7zr==0.22.0：Py3.8 兼容的最高版（1.x 需 Py3.9+），用于解压 .7z 期末
REM     项目源码包；API 与教师端 1.1.3 兼容。
REM   - 学生端运行时只需 numpy/PIL/docx/openpyxl/defusedxml/py7zr/PyQt5，
REM     不含 torch/pandas/sklearn 等重型依赖（spec 中显式排除）。
REM ============================================================
setlocal enabledelayedexpansion

set ENV=stm32f407-win7
set PY=3.8
set REPO=%~dp0..

where conda >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 conda。请先安装 Miniconda/Anaconda 并确保 conda 在 PATH。
  exit /b 1
)

REM [1/4] 创建 conda 环境（若不存在）
conda env list | findstr /B /C:"%ENV% " >nul
if errorlevel 1 (
  echo [1/4] 创建 conda 环境 %ENV% ^(python=%PY%^) ...
  call conda create -n %ENV% python=%PY% -y
  if errorlevel 1 ( echo [错误] 创建 conda 环境失败。& exit /b 1 )
) else (
  echo [1/4] 复用已有 conda 环境：%ENV%
)

REM [2/4] 激活
call conda activate %ENV%
if errorlevel 1 (
  echo [错误] 激活失败。若未对 cmd 初始化，请先执行：  conda init cmd.exe
  exit /b 1
)

REM [3/4] 安装依赖（Windows 7 兼容版本锁定）
echo [3/4] 安装依赖（Py3.8 / PyQt5==5.15.2 / py7zr==0.22.0 / numpy^<2）...
python -m pip install --upgrade pip
python -m pip install ^
  "PyQt5==5.15.2" ^
  "numpy==1.24.4" "Pillow==10.4.0" ^
  "python-docx==1.1.2" "openpyxl==3.1.5" ^
  "defusedxml==0.7.1" "PyYAML==6.0.2" ^
  "py7zr==0.22.0" ^
  "pyinstaller==6.21.0"
if errorlevel 1 ( echo [错误] 依赖安装失败。& exit /b 1 )

REM [4/4] 打包
pushd "%REPO%"
echo [4/4] 清理旧产物并打包 ...
if exist build\StudentSelfCheck rmdir /s /q build\StudentSelfCheck
if exist dist\StudentSelfCheck.exe del /q dist\StudentSelfCheck.exe
python -m PyInstaller --noconfirm build_student.spec
set RC=%ERRORLEVEL%
popd

call conda deactivate

echo.
if exist "%REPO%\dist\StudentSelfCheck.exe" (
  echo === 完成 ===
  echo   产物：%REPO%\dist\StudentSelfCheck.exe
  echo   覆盖系统：Windows 7 / 8.1 / 10 / 11（单一通用版，无需区分）
  echo   运行后报告输出到：%%USERPROFILE%%\STM32学生自检\outputs\student_self_check\
) else (
  echo === 打包失败（退出码 !RC!），请检查上方日志 ===
  exit /b 1
)
endlocal
