#!/bin/bash
# new_project.sh - Create a new STM32F407 project
# Usage: ./new_project.sh <project-number> <project-name>

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <project-number> <project-name>"
    echo ""
    echo "Example: $0 02 led-blink"
    exit 1
fi

PROJECT_NUM=$1
PROJECT_NAME=$2
PROJECT_DIR="${PROJECT_ROOT}/projects/${PROJECT_NUM}-${PROJECT_NAME}"

# Validate project number
if [[ ! "$PROJECT_NUM" =~ ^[0-9]+$ ]]; then
    print_error "Project number must be numeric"
    exit 1
fi

# Check if project already exists
if [ -d "$PROJECT_DIR" ]; then
    print_error "Project directory already exists: $PROJECT_DIR"
    exit 1
fi

# Create project directory
print_info "Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"

# Copy template files
print_info "Copying template files..."
if [ -d "${PROJECT_ROOT}/projects/_template" ]; then
    cp -r "${PROJECT_ROOT}/projects/_template/"* "$PROJECT_DIR/"
else
    print_warning "Template directory not found, creating basic structure..."
fi

# Create project docs
mkdir -p "$PROJECT_DIR/docs"

# Create README
cat > "$PROJECT_DIR/README.md" << EOF
# Project ${PROJECT_NUM}: ${PROJECT_NAME}

## Description

TODO: Add project description

## Hardware Requirements

TODO: List required hardware connections

## Building

\`\`\`bash
make PROJECT=${PROJECT_NUM}-${PROJECT_NAME}
\`\`\`

## Features

- TODO: Feature 1
- TODO: Feature 2

## Configuration

See \`config.h\` for project-specific configuration.

## Documentation

- See \`docs/\` directory for additional documentation
EOF

print_info "Project created successfully!"
echo ""
echo "Project location: $PROJECT_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit projects/${PROJECT_NUM}-${PROJECT_NAME}/config.h for your configuration"
echo "  2. Edit projects/${PROJECT_NUM}-${PROJECT_NAME}/main.c for your code"
echo "  3. Build: make PROJECT=${PROJECT_NUM}-${PROJECT_NAME}"
echo ""
