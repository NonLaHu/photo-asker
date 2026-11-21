#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "${BIN_DIR}"
ln -sf "${SCRIPT_DIR}/bin/photo-asker" "${BIN_DIR}/photo-asker"

echo "[✓] Successfully installed photo-asker to ${BIN_DIR}/photo-asker"
echo ""
echo "Ensure ${BIN_DIR} is in your \$PATH."
echo "You can now run 'photo-asker' from anywhere!"
