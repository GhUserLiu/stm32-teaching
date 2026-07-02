@echo off
REM 局部化环境变量（PYTHONPATH 等），脚本结束自动还原，不污染用户 shell
setlocal
REM ============================================================
REM 教学管理系统启动器（教师端）
REM Teaching Management System Launcher (teacher side)
REM
REM 双击即可运行：自动定位仓库根目录、激活 conda 环境 stm32_teaching、
REM 启动 PyQt6 GUI。整仓库迁移后仍可直接运行（以本 bat 所在目录为根）。
REM
REM 依赖：conda 环境 stm32_teaching（Python 3.11 + PyQt6）。
REM   注意：PyQt6 为 GUI 依赖，未含于 requirements.txt（后者仅覆盖文档/数据/批阅等
REM   依赖），需在环境内单独安装：pip install PyQt6
REM
REM 编码约定：本文件以 GBK（CP936）+ CRLF 保存，匹配中文 Windows 控制台默认代码页。
REM   切勿存为 UTF-8 后在脚本里 chcp 65001 —— 会触发 cmd 批处理字节偏移 bug，
REM   导致行碎片被执行（'ui'/'M'/'src\"' 等报“不是命令”）且中文乱码。
REM ============================================================

REM 以本 bat 所在目录（仓库根）为工作目录
cd /d "%~dp0"

REM 与仓库统一约定：tools => src/tools，便于模块内 `from tools.xxx` 导入
set "PYTHONPATH=%~dp0src"

title 教学管理系统

REM [1/4] 检查 conda 是否可用
where conda >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 conda。请先安装 Miniconda/Anaconda 并将其加入 PATH，
  echo        或直接从「Anaconda Prompt」中运行本脚本。
  goto :end
)

REM [2/4] 检查 conda 环境 stm32_teaching 是否存在
conda env list | findstr /B /C:"stm32_teaching " >nul
if errorlevel 1 (
  echo [错误] 未找到 conda 环境 stm32_teaching。请先创建：
  echo            conda create -n stm32_teaching python=3.11
  echo            conda activate stm32_teaching
  echo            pip install -r requirements.txt
  echo            pip install PyQt6     （GUI 依赖，未含于 requirements.txt）
  goto :end
)

REM [3/4] 激活环境
call conda activate stm32_teaching
if errorlevel 1 (
  echo [错误] 激活 stm32_teaching 失败。若未对 cmd 初始化，请先执行：
  echo            conda init cmd.exe
  echo        然后关闭并重新打开命令行窗口，再运行本脚本。
  goto :end
)

REM [4/4] 启动 GUI
REM 版本横幅：需与 src/tools/teaching_management_gui/__init__.py 的 __version__ 保持一致
echo 教学管理系统 v2.5
echo 正在启动教学管理系统 ...
python src\tools\teaching_management_gui\main.py
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (
  echo.
  echo [错误] 程序异常退出（退出码 %RC%），请查看上方日志排查。
)

:end
echo.
pause
