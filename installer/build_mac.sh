#!/usr/bin/env bash
# =============================================================================
# Manimator — macOS Installer Builder
#
# Creates:
#   dist/Manimator-<version>.dmg
#
# Requirements (install once):
#   brew install create-dmg
#
# Usage:
#   cd installer && ./build_mac.sh [--version 1.0.0]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME="Manimator"
VERSION="1.0.0"

# Parse --version flag
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) VERSION="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

APP_BUNDLE="$SCRIPT_DIR/dist/$APP_NAME.app"
DMG_OUT="$SCRIPT_DIR/dist/${APP_NAME}-${VERSION}.dmg"
ICON="$SCRIPT_DIR/assets/Manimator.icns"

echo "============================================================"
echo "  Building Manimator $VERSION for macOS"
echo "============================================================"

# ── Step 1: Clean previous build ─────────────────────────────────────────────
echo ""
echo "[1/6] Cleaning previous build…"
rm -rf "$SCRIPT_DIR/dist"
mkdir -p "$SCRIPT_DIR/dist"

# ── Step 2: Create .app bundle structure ─────────────────────────────────────
echo "[2/6] Creating .app bundle structure…"

APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_SOURCE="$APP_RESOURCES/app_source"

mkdir -p "$APP_MACOS"
mkdir -p "$APP_RESOURCES"
mkdir -p "$APP_SOURCE"

# ── Step 3: Copy app source code ─────────────────────────────────────────────
echo "[3/6] Copying app source…"

# Copy the Python source (excluding venv, build artifacts, test files)
rsync -a \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git/' \
    --exclude='.DS_Store' \
    --exclude='installer/' \
    --exclude='videos/' \
    --exclude='*.mp4' \
    --exclude='*.gif' \
    --exclude='*.log' \
    --exclude='test_*.py' \
    "$PROJECT_ROOT/" "$APP_SOURCE/"

# Update Info.plist version
sed "s/1\.0\.0/$VERSION/g" "$SCRIPT_DIR/Info.plist" > "$APP_CONTENTS/Info.plist"

# Copy icon
cp "$ICON" "$APP_RESOURCES/Manimator.icns"

# ── Step 4: Install launcher script ──────────────────────────────────────────
echo "[4/6] Installing launcher…"

# Copy and patch the launcher with the actual version
sed "s/APP_VERSION=\"1.0.0\"/APP_VERSION=\"$VERSION\"/" "$SCRIPT_DIR/Manimator.sh" \
    > "$APP_MACOS/$APP_NAME"
chmod +x "$APP_MACOS/$APP_NAME"

# ── Step 5: Code sign (ad-hoc if no Developer ID available) ──────────────────
echo "[5/6] Signing bundle…"

# Check for a Developer ID certificate
SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:-}"

if [[ -n "$SIGN_IDENTITY" ]]; then
    echo "  Signing with: $SIGN_IDENTITY"
    codesign --deep --force --sign "$SIGN_IDENTITY" \
        --entitlements "$SCRIPT_DIR/assets/entitlements.plist" \
        "$APP_BUNDLE"
else
    echo "  No MACOS_SIGN_IDENTITY set — using ad-hoc signature"
    echo "  (Users will need to right-click → Open to bypass Gatekeeper)"
    codesign --deep --force --sign "-" "$APP_BUNDLE"
fi

# ── Step 6: Create DMG ───────────────────────────────────────────────────────
echo "[6/6] Creating DMG…"

# Background image dimensions: 540×380
# App icon at (170, 190), Applications symlink at (370, 190)

create-dmg \
    --volname "$APP_NAME $VERSION" \
    --volicon "$ICON" \
    --window-pos 200 120 \
    --window-size 540 380 \
    --icon-size 100 \
    --icon "$APP_NAME.app" 170 190 \
    --hide-extension "$APP_NAME.app" \
    --app-drop-link 370 190 \
    --no-internet-enable \
    "$DMG_OUT" \
    "$SCRIPT_DIR/dist/$APP_NAME.app" \
    || {
        echo ""
        echo "create-dmg failed (possibly due to missing Xcode tools)."
        echo "Falling back to hdiutil…"
        hdiutil create \
            -volname "$APP_NAME $VERSION" \
            -srcfolder "$SCRIPT_DIR/dist/$APP_NAME.app" \
            -ov -format UDZO \
            "$DMG_OUT"
    }

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Build complete!"
echo ""
echo "  Output: $DMG_OUT"
SIZE=$(du -sh "$DMG_OUT" 2>/dev/null | cut -f1 || echo "?")
echo "  Size:   $SIZE"
echo ""
echo "  To distribute:"
echo "  1. Share the .dmg file"
echo "  2. Users drag Manimator.app to /Applications"
echo "  3. On first launch, right-click → Open (bypasses Gatekeeper)"
echo "     (or: spctl --add /Applications/Manimator.app)"
echo "============================================================"
