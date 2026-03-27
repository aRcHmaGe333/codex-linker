#!/usr/bin/env bash
set -euo pipefail

# IPClaim — stamp.sh
# Applies APC licensing, timestamping workflow, and verification to any git repo.
# Usage: stamp.sh <target-repo> [author-name] [apc|apc-vf]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-}"

if [ -z "$TARGET" ]; then
  echo "Usage: stamp.sh <target-repo-path> [author-name] [apc|apc-vf]"
  exit 1
fi

TARGET="$(cd "$TARGET" && pwd)"

# --- Validate target ---
if [ ! -d "$TARGET/.git" ]; then
  echo "Error: $TARGET is not a git repository."
  exit 1
fi

COMMIT_COUNT=$(git -C "$TARGET" rev-list --count HEAD 2>/dev/null || echo 0)
if [ "$COMMIT_COUNT" -eq 0 ]; then
  echo "Error: $TARGET has no commits. Make at least one commit first."
  exit 1
fi

REMOTE=$(git -C "$TARGET" remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE" ]; then
  echo "Warning: No remote 'origin' configured. Push will not work automatically."
fi

# --- Author name ---
AUTHOR="${2:-}"
if [ -z "$AUTHOR" ]; then
  read -rp "Author name: " AUTHOR
  if [ -z "$AUTHOR" ]; then
    echo "Error: Author name is required."
    exit 1
  fi
fi

# --- License type ---
LICENSE_TYPE="${3:-}"
if [ -z "$LICENSE_TYPE" ]; then
  echo "License options:"
  echo "  apc    — All rights reserved (LICENSE-APC.md)"
  echo "  apc-vf — All rights reserved + ValueFlow profit sharing (LICENSE-APC-VF.md)"
  read -rp "License type [apc/apc-vf]: " LICENSE_TYPE
fi

case "$LICENSE_TYPE" in
  apc)    LICENSE_FILE="LICENSE-APC.md" ;;
  apc-vf) LICENSE_FILE="LICENSE-APC-VF.md" ;;
  *)      echo "Error: Invalid license type '$LICENSE_TYPE'. Use 'apc' or 'apc-vf'."; exit 1 ;;
esac

LICENSE_SRC="$SCRIPT_DIR/$LICENSE_FILE"

if [ ! -f "$LICENSE_SRC" ]; then
  echo "Error: License template not found at $LICENSE_SRC"
  exit 1
fi

# --- Gather data ---
TREE_HASH=$(git -C "$TARGET" rev-parse HEAD^{tree})
DATE_UTC=$(date -u +%Y-%m-%d)
YEAR=$(date -u +%Y)

echo ""
echo "=== IPClaim Stamp ==="
echo "Target:    $TARGET"
echo "Author:    $AUTHOR"
echo "License:   $LICENSE_FILE"
echo "Tree hash: $TREE_HASH"
echo "Date:      $DATE_UTC UTC"
echo "====================="
echo ""

# --- Check for existing files ---
for CHECK_FILE in "$TARGET/$LICENSE_FILE" "$TARGET/.github/workflows/timestamp.yml" "$TARGET/VERIFY.md"; do
  if [ -f "$CHECK_FILE" ]; then
    read -rp "$(basename "$CHECK_FILE") already exists in target. Overwrite? [y/N]: " OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
      echo "Aborted."
      exit 0
    fi
  fi
done

# --- Copy files ---
mkdir -p "$TARGET/.github/workflows"
cp "$SCRIPT_DIR/.github/workflows/timestamp.yml" "$TARGET/.github/workflows/timestamp.yml"
cp "$SCRIPT_DIR/VERIFY.md" "$TARGET/VERIFY.md"
cp "$LICENSE_SRC" "$TARGET/$LICENSE_FILE"

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'
}

AUTHOR_ESCAPED="$(escape_sed_replacement "$AUTHOR")"
TREE_HASH_ESCAPED="$(escape_sed_replacement "$TREE_HASH")"
DATE_ESCAPED="$(escape_sed_replacement "$DATE_UTC UTC")"
YEAR_ESCAPED="$(escape_sed_replacement "$YEAR")"

# --- Fill placeholders in license ---
sed -i.bak \
  -e "s|\[AUTHOR NAME OR ENTITY\]|$AUTHOR_ESCAPED|g" \
  -e "s|\[AUTHOR NAME\]|$AUTHOR_ESCAPED|g" \
  -e "s|\[INSERT ROOT HASH\]|$TREE_HASH_ESCAPED|g" \
  -e "s|\[INSERT TREE HASH\]|$TREE_HASH_ESCAPED|g" \
  -e "s|\[INSERT HASH\]|$TREE_HASH_ESCAPED|g" \
  -e "s|\[HASH\]|$TREE_HASH_ESCAPED|g" \
  -e "s|\[INSERT DATE AND TIME UTC\]|$DATE_ESCAPED|g" \
  -e "s|\[INSERT DATE UTC\]|$DATE_ESCAPED|g" \
  -e "s|\[YEAR\]|$YEAR_ESCAPED|g" \
  "$TARGET/$LICENSE_FILE"
rm -f "$TARGET/$LICENSE_FILE.bak"

echo "Files copied and placeholders filled."

# --- Commit ---
git -C "$TARGET" add "$LICENSE_FILE" VERIFY.md .github/workflows/timestamp.yml
git -C "$TARGET" commit -m "[APC] IPClaim stamp applied — $LICENSE_FILE"

echo "Committed."

# --- Push ---
if [ -n "$REMOTE" ]; then
  read -rp "Push to origin? This triggers the timestamp workflow. [Y/n]: " PUSH
  if [[ ! "$PUSH" =~ ^[Nn]$ ]]; then
    git -C "$TARGET" push
    echo ""
    echo "Pushed. The timestamp workflow will run on GitHub Actions."
    echo "Check: $(echo "$REMOTE" | sed 's/\.git$//')/actions"
  else
    echo "Not pushed. Run 'git push' manually when ready."
  fi
else
  echo "No remote configured. Push manually when ready."
fi

echo ""
echo "Done. Tree hash $TREE_HASH stamped for $AUTHOR."
