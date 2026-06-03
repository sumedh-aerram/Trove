#!/usr/bin/env bash
# Smoke tests for Build Radar API (requires API on :8000 and seeded DB).
set -euo pipefail

API="${API_BASE_URL:-http://localhost:8000}"

echo "== health =="
curl -s "$API/health" | head -c 200
echo

search() {
  local q="$1"
  echo ""
  echo "== search: $q =="
  curl -sG "$API/search" --data-urlencode "q=$q" --data-urlencode "limit=5" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('total', d.get('total'), 'top', [r.get('title') for r in d.get('results',[])[:3]])"
}

search "AI lecture summarizer"
search "RAG Chrome extension"
search "MCP server for coding agents"
search "computer vision posture app"

echo ""
echo "Smoke tests finished."
