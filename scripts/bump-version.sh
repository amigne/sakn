#!/usr/bin/env bash
# bump-version.sh — Atomically bump the project version across both stacks.
#
# SAKN maintains version strings in two places with incompatible formats:
#   - src/backend/pyproject.toml  → PEP 440  (0.1.1, 0.1.1.dev0)
#   - src/frontend/package.json   → SemVer   (0.1.1, 0.1.1-dev)
#
# FastAPI reads from importlib.metadata, which sources pyproject.toml,
# so main.py no longer contains a separate version literal.
#
# Usage:
#   ./scripts/bump-version.sh 0.1.1          # release
#   ./scripts/bump-version.sh 0.1.1-dev      # SemVer prerelease (auto-converts to PEP 440)
#   ./scripts/bump-version.sh 0.1.1.dev0     # PEP 440 prerelease (auto-converts to SemVer)
#
# After running, verify with:
#   grep version src/backend/pyproject.toml src/frontend/package.json

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYPROJECT="$ROOT/src/backend/pyproject.toml"
PACKAGE_JSON="$ROOT/src/frontend/package.json"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

if [ $# -ne 1 ]; then
    echo "Usage: $0 <version>"
    echo ""
    echo "Examples:"
    echo "  $0 0.1.1          # release"
    echo "  $0 0.1.1-dev      # SemVer prerelease"
    echo "  $0 0.1.1.dev0     # PEP 440 prerelease"
    exit 1
fi

INPUT="$1"

# Derive PEP 440 and SemVer forms from the input.
#   Input:       0.1.1         → pep440: 0.1.1      semver: 0.1.1
#   Input:       0.1.1-dev     → pep440: 0.1.1.dev0  semver: 0.1.1-dev
#   Input:       0.1.1.dev0    → pep440: 0.1.1.dev0  semver: 0.1.1-dev
case "$INPUT" in
    *-dev)
        # SemVer prerelease form: 0.1.1-dev → PEP 440: 0.1.1.dev0
        BASE="${INPUT%-dev}"
        PEP440="${BASE}.dev0"
        SEMVER="$INPUT"
        ;;
    *.dev[0-9]*)
        # PEP 440 prerelease form: 0.1.1.dev0 → SemVer: 0.1.1-dev
        BASE="${INPUT%%.dev*}"
        SEMVER="${BASE}-dev"
        PEP440="$INPUT"
        ;;
    *)
        # Release: no dev suffix
        PEP440="$INPUT"
        SEMVER="$INPUT"
        ;;
esac

# Validate base version is roughly SemVer-shaped
if ! echo "$PEP440" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+'; then
    die "Version '$INPUT' does not look like a valid MAJOR.MINOR.PATCH version."
fi

echo "Bumping version to:"
echo "  pyproject.toml → $PEP440 (PEP 440)"
echo "  package.json   → $SEMVER (SemVer)"

# Update pyproject.toml
if [ -f "$PYPROJECT" ]; then
    sed -i "s/^version = \".*\"/version = \"$PEP440\"/" "$PYPROJECT"
    echo "  ✓ pyproject.toml updated"
else
    die "pyproject.toml not found at $PYPROJECT"
fi

# Update package.json
if [ -f "$PACKAGE_JSON" ]; then
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$SEMVER\"/" "$PACKAGE_JSON"
    echo "  ✓ package.json updated"
else
    die "package.json not found at $PACKAGE_JSON"
fi

echo ""
echo "Done. FastAPI will read version from importlib.metadata (pyproject.toml)."
echo "Verify with:  grep version src/backend/pyproject.toml src/frontend/package.json"
