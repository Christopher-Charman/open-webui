#!/usr/bin/env bash
# Only report a version transition proven against the exact event.before commit.
set -euo pipefail
previous_sha="${1:-}"
if [[ ! "$previous_sha" =~ ^[0-9a-f]{40}$ || "$previous_sha" =~ ^0{40}$ ]]; then
  echo "::error::Missing valid event.before SHA; refusing publication or build suppression decision" >&2
  exit 2
fi
if ! git cat-file -e "${previous_sha}^{commit}" 2>/dev/null; then
  echo "::error::event.before commit unavailable in checkout" >&2
  exit 3
fi
if ! previous_json=$(git show "${previous_sha}:package.json"); then
  echo "::error::Cannot retrieve previous package.json" >&2
  exit 4
fi
if ! previous_version=$(jq -er '.version | select(type == "string" and length > 0)' <<< "$previous_json"); then
  echo "::error::Previous package version is invalid" >&2
  exit 5
fi
if ! current_version=$(jq -er '.version | select(type == "string" and length > 0)' package.json); then
  echo "::error::Current package version is invalid" >&2
  exit 6
fi
if [[ "$previous_version" == "$current_version" ]]; then
  echo changed=false
else
  echo changed=true
fi
