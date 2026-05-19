#!/usr/bin/env bash
# Rebuild all generated constellation assets from canonical inputs.
#
# Inputs (never written): data/constellations/<slug>/current.svg
#                         data/constellations/<slug>/metadata.json
# Run this after editing any current.svg or metadata.json to refresh the
# derived lifecycle, wireframes, web bundle, and per-cluster pages.
set -euo pipefail

cd "$(dirname "$0")/.."

PY=".venv/bin/python"
if [ ! -x "${PY}" ]; then
    PY="python3"
fi

"${PY}" scripts/derive_constellation_lifecycle.py
"${PY}" scripts/build_constellation_wireframes.py
"${PY}" scripts/build_visualization_facts.py
"${PY}" scripts/scaffold_constellation_pages.py
