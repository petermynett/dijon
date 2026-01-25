#!/bin/bash
# One-time script to resample existing WAV files in raw audio directory to 22050 Hz.
#
# This script resamples all WAV files in data/datasets/raw/audio/ to 22050 Hz
# and updates the manifest.csv accordingly.
#
# Usage:
#   ./scripts/resample_raw_audio.sh [--dry-run] [--no-backup]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/resample_raw_audio.py"

cd "$PROJECT_ROOT"

# Check if Python script exists
if [[ ! -f "$PYTHON_SCRIPT" ]]; then
    echo "Error: Python script not found: $PYTHON_SCRIPT" >&2
    exit 1
fi

# Check if ffmpeg is available
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is required but not found in PATH" >&2
    exit 1
fi

# Check if ffprobe is available
if ! command -v ffprobe &> /dev/null; then
    echo "Error: ffprobe is required but not found in PATH" >&2
    exit 1
fi

# Pass all arguments to Python script
exec python3 "$PYTHON_SCRIPT" "$@"
