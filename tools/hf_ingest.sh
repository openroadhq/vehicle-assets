#!/bin/zsh
# Read "slug<space>rawUrl" lines, download each, ingest with CORRECT slug.
# Slug comes from the file, never reconstructed from a filename (that / vs _
# ambiguity created 8 malformed top-level files once).
set -e
URLS="$1"; STAGE="$2"; mkdir -p "$STAGE"
ARGS=()
while read slug url; do
  [ -z "$slug" ] && continue
  f="$STAGE/$(echo "$slug" | tr '/' '@').png"     # @ is reversible, never in a slug
  curl -so "$f" "$url"
  ARGS+=("$slug|$f")
done < "$URLS"
tools/ingest.py "${ARGS[@]}" 2>&1 | grep -E "^(ok|FAIL|manifest)"
