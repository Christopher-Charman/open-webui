#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

BASE="/home/storage/781/4477781/user/webapp"
PKG="$BASE/envs/openwebui/lib/python3.11/site-packages/open_webui"
TARGET_COMMIT="1aee9c5"
TARGET_BACKUP="$PKG/frontend.pre-neural-material-20260923T171905Z"
TARGET_DOC="CUSTOM_SHELL_NEURAL_MATERIAL_DEPLOYMENT_2026-09-23.md"

echo "NEURAL_MATERIAL_AUDIT=BEGIN"
echo "mode=READ_ONLY"
echo "target_commit=$TARGET_COMMIT"
echo "target_backup=$TARGET_BACKUP"

if [ -d "$TARGET_BACKUP" ]; then
  echo "target_backup_exists=YES"
else
  echo "target_backup_exists=NO"
fi

echo "=== EXACT DEPLOYMENT DOC SEARCH ==="
DOC_FOUND=0
for root in \
  "$BASE" \
  "$BASE/runtime-domains" \
  "$BASE/Architecture Control Plane" \
  "$BASE/projects" \
  "$PKG"
do
  [ -e "$root" ] || continue
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    echo "deployment_doc=$p"
    echo "--- deployment doc head ---"
    sed -n '1,220p' "$p"
    echo "--- end deployment doc ---"
    DOC_FOUND=1
  done < <(find "$root" -maxdepth 5 -type f -name "$TARGET_DOC" -print 2>/dev/null)
done
[ "$DOC_FOUND" = "1" ] || echo "deployment_doc=NOT_FOUND"

echo "=== BOUNDED GIT REPOSITORY DISCOVERY ==="
mapfile -t GITS < <(
  {
    [ -d "$BASE/.git" ] && printf '%s\n' "$BASE/.git"
    find "$BASE" -maxdepth 4 -type d -name .git -print 2>/dev/null
  } | awk '!seen[$0]++'
)

echo "git_repo_count=\${#GITS[@]}"
COMMIT_FOUND=0

for gd in "\${GITS[@]}"; do
  repo="\${gd%/.git}"
  printf 'git_repo=%s\n' "$repo"
  if git -C "$repo" cat-file -e "$TARGET_COMMIT^{commit}" 2>/dev/null; then
    COMMIT_FOUND=1
    full="$(git -C "$repo" rev-parse "$TARGET_COMMIT^{commit}")"
    echo "target_commit_repo=$repo"
    echo "target_commit_full=$full"
    echo "--- commit metadata and file list ---"
    git -C "$repo" show \
      --format='commit=%H%nauthor_date=%aI%ncommit_date=%cI%nsubject=%s' \
      --name-status \
      --no-renames \
      "$full"
    echo "--- changed file object identities ---"
    git -C "$repo" diff-tree --no-commit-id --name-only -r "$full" |
    while IFS= read -r path; do
      [ -n "$path" ] || continue
      blob="$(git -C "$repo" rev-parse "$full:$path" 2>/dev/null || true)"
      parent_blob="$(git -C "$repo" rev-parse "$full^:$path" 2>/dev/null || true)"
      printf 'file=%s post_blob=%s pre_blob=%s\n' "$path" "\${blob:-NONE}" "\${parent_blob:-NONE}"
    done
    echo "--- target source excerpts ---"
    for wanted in Placeholder.svelte shellState.ts custom.css loader.js owui-orb-v1.js owui-orb-v1.css; do
      path="$(git -C "$repo" diff-tree --no-commit-id --name-only -r "$full" | grep -E "(^|/)$wanted$" | head -1 || true)"
      [ -n "$path" ] || continue
      echo "BEGIN_TARGET_FILE=$path"
      git -C "$repo" show "$full:$path" | sed -n '1,320p'
      echo "END_TARGET_FILE=$path"
    done
  fi
done

[ "$COMMIT_FOUND" = "1" ] || echo "target_commit_repo=NOT_FOUND"

echo "=== NAMED FRONTEND SNAPSHOT LINEAGE ==="
find "$PKG" -maxdepth 1 -type d \
  \( -name 'frontend.pre-*20260923*' -o -name 'orb-backups-*20260923*' \) \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null |
  sort

echo "=== DESIRED SNAPSHOT HASH INVENTORY ==="
if [ -d "$TARGET_BACKUP" ]; then
  for rel in \
    index.html \
    static/custom.css \
    static/loader.js \
    static/owui-orb-v1.js \
    static/owui-orb-v1.css
  do
    p="$TARGET_BACKUP/$rel"
    if [ -f "$p" ]; then
      printf '%s sha256=%s bytes=%s\n' "$rel" "$(sha256sum "$p" | awk '{print $1}')" "$(wc -c < "$p" | tr -d ' ')"
    else
      printf '%s=MISSING\n' "$rel"
    fi
  done
fi

echo "NEURAL_MATERIAL_AUDIT=END"
echo "RUNTIME_MUTATION=NONE"
