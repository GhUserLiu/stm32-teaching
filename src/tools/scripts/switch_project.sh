#!/bin/bash
# switch_project.sh - Switch the current active project for EIDE
# Usage: ./switch_project.sh <project-name>

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EIDE_CONFIG="${PROJECT_ROOT}/.eide/eide.yml"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <project-name>"
    echo ""
    echo "Available projects:"
    ls -1 "${PROJECT_ROOT}/projects" | grep -E "^[0-9]" | sed 's/^/  /'
    exit 1
fi

PROJECT_NAME=$1

# Validate project exists
if [ ! -d "${PROJECT_ROOT}/projects/${PROJECT_NAME}" ]; then
    echo -e "${RED}[ERROR]${NC} Project not found: $PROJECT_NAME"
    exit 1
fi

# Backup current config
if [ -f "$EIDE_CONFIG" ]; then
    cp "$EIDE_CONFIG" "${EIDE_CONFIG}.bak"
    echo -e "${GREEN}[INFO]${NC} Backed up current eide.yml"
fi

# Update eide.yml
echo "Updating EIDE configuration for project: $PROJECT_NAME"

# Check if this is a CubeMX project
if [ -f "${PROJECT_ROOT}/projects/${PROJECT_NAME}/cubemx/Core/Src/main.c" ]; then
    echo "Detected CubeMX project structure"
    # For CubeMX projects, we need different handling
    echo -e "${GREEN}[INFO]${NC} CubeMX projects should be opened directly in their directory"
    echo "Project path: ${PROJECT_ROOT}/projects/${PROJECT_NAME}/cubemx"
else
    # Update simple eide.yml
    cat > "$EIDE_CONFIG" << EOF
version: "4.1"
name: stm32-teaching
type: ARM
deviceName: STM32F407ZGTx
packDir: .pack/Keil/STM32F4xx_DFP.3.1.1
srcDirs:
  - projects/${PROJECT_NAME}
  - common/core
  - common/bsp
  - common/inc
virtualFolder:
  name: <virtual_root>
  files: []
  folders: []
dependenceList: []
outDir: build\\${PROJECT_NAME}
miscInfo:
  uid: fd4b1674541bdd2a4cfe463c6ba02d6a
targets:
  Debug:
    cppPreprocessAttrs:
      defineList:
        - STM32F407xx
      incList:
        - .
        - projects/${PROJECT_NAME}
        - common/inc
        - common/core
        - common/bsp
      libList: []
    excludeList:
      - projects/_template
      - projects/Test6
    settings:
      debugger: cortex-debug
    toolchain: GCC
    toolchainConfigMap:
      GCC:
        archExtensions: ""
        cpuType: Cortex-M4
        floatingPointHardware: single
        options:
          version: 5
          afterBuildTasks: []
          asm-compiler:
            ASM_FLAGS: ""
          beforeBuildTasks: []
          c/cpp-compiler:
            CXX_FLAGS: ""
            C_FLAGS: ""
            language-c: c11
            language-cpp: c++11
            one-elf-section-per-data: true
            one-elf-section-per-function: true
            optimization: level-debug
            warnings: all-warnings
          global:
            \$float-abi-type: hard
            misc-control: ""
            not-use-syscalls: true
            output-debug-info: enable
            use-newlib-nano: true
          linker:
            \$outputTaskExcludes: []
            LD_FLAGS: ""
            LIB_FLAGS: -lm
            output-format: elf
            remove-unused-input-sections: true
        scatterFilePath: STM32F407XX_FLASH.ld
        storageLayout:
          RAM: []
          ROM: []
        useCustomScatterFile: true
    uploadConfigMap:
      JLink:
        baseAddr: ""
        bin: ""
        cpuInfo:
          cpuName: "null"
          vendor: "null"
        otherCmds: ""
        proType: 1
        speed: 8000
      OpenOCD:
        baseAddr: "0x08000000"
        bin: ""
        interface: stlink
        target: stm32f4x
    uploader: OpenOCD
EOF
fi

echo -e "${GREEN}[SUCCESS]${NC} Project switched to: $PROJECT_NAME"
echo ""
echo "Reload your VSCode window to apply changes."
