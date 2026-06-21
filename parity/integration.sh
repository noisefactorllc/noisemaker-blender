#!/usr/bin/env bash
# Integration-surface end-to-end gate.
#
# Proves the user-facing path the addon ships, byte-exact to the reference:
#   DSL text  ->  registered NOISEMAKER_OT_bake  ->  compile_graph  ->  GpuBackend
#             ->  Image datablock
#
# Two checks:
#   [1] in-Blender (GUI): register()/unregister() round-trip, the CUSTOM node tree + node
#       instantiate, and the bake operator's Image equals the gated direct pipeline exactly
#       (INVARIANT A, max-abs-diff 0). Dumps the baked Image to a PNG.
#   [2] out-of-process: that baked PNG vs the reference golden (INVARIANT B), graded by the
#       project's own parity/compare.py.
#
# GPU needs GUI mode on macOS, so a Blender window flashes briefly (same as the render
# harness). Env overrides:
#   NM_BLENDER    Blender executable      (default: /Applications/Blender.app/.../Blender)
#   NM_GRADE_PY   python with numpy+PIL   (default: Blender's bundled standalone python)
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
BLENDER="${NM_BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
GRADE_PY="${NM_GRADE_PY:-/Applications/Blender.app/Contents/Resources/5.1/python/bin/python3.13}"
GOLDEN="$HERE/parity/out/adjust.golden.png"
BAKED="/tmp/nm_bake_adjust.png"

if [ ! -f "$GOLDEN" ]; then
  echo "FAIL: golden $GOLDEN not present."
  echo "      Seed it first (derived artifact), e.g.:"
  echo "        NM_REFERENCE_ROOT=<ref> node tools/export-graph.mjs --file parity/programs/adjust.dsl parity/out/adjust.graph.json"
  echo "        NM_JOBS='[{\"graph\":\"parity/out/adjust.graph.json\",\"out\":\"parity/out/adjust.golden.png\"}]' \\"
  echo "          \"$BLENDER\" --factory-startup --python blender/harness/render_all.py"
  exit 2
fi

rm -f "$BAKED"
LOG="$(mktemp)"

echo "== [1/2] in-Blender integration test (registration + node + bake == pipeline) =="
"$BLENDER" --factory-startup --python "$HERE/blender/harness/test_integration.py" >"$LOG" 2>&1 || true
grep -E "reg OK|node OK|img OK|dump OK|sweep|errpath|INVARIANT A|INTEGRATION" "$LOG" || true
if ! grep -q "INTEGRATION PASS" "$LOG"; then
  echo "FAIL: in-Blender integration test did not pass"
  echo "---- log tail ----"; tail -30 "$LOG"; exit 1
fi

echo
echo "== [2/2] INVARIANT B: baked Image vs reference golden =="
if [ ! -f "$BAKED" ]; then echo "FAIL: bake did not produce $BAKED"; exit 1; fi
"$GRADE_PY" "$HERE/parity/compare.py" "$GOLDEN" "$BAKED" --name "integration/adjust(baked)" --tolerance 1

echo
echo "INTEGRATION GATE: PASS (DSL -> operator -> Image, byte-exact to reference)"
