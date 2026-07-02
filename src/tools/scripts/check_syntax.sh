#!/bin/bash
# check_syntax.sh - Check C code syntax using clang
# Usage: ./check_syntax.sh [project-name]

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PROJECT_NAME=${1:-01-turn-signal}
PROJECT_DIR="${PROJECT_ROOT}/projects/${PROJECT_NAME}"
COMMON_DIR="${PROJECT_ROOT}/common"

# Check if clang is available
if ! command -v clang &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} clang not found. Please install clang."
    echo "  Windows: winget install LLVM.LLVM"
    echo "  Linux: sudo apt install clang"
    echo "  macOS: brew install llvm"
    exit 1
fi

echo -e "${GREEN}[INFO]${NC} Checking syntax for project: $PROJECT_NAME"
echo ""

# Find all C source files
SOURCES=$(find "$PROJECT_DIR" -name "*.c" 2>/dev/null)
SOURCES+=" $(find "$COMMON_DIR" -name "*.c" 2>/dev/null)"

# Check each file
ERRORS=0
for file in $SOURCES; do
    echo "Checking: $file"
    if ! clang -fsyntax-only -target arm-none-eabi \
        -I"$PROJECT_DIR" \
        -I"$COMMON_DIR/inc" \
        -I"$COMMON_DIR/hal" \
        -DSTM32F407xx \
        "$file" 2>&1; then
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}[SUCCESS]${NC} No syntax errors found!"
else
    echo -e "${RED}[ERROR]${NC} Found $ERRORS file(s) with syntax errors"
    exit 1
fi
