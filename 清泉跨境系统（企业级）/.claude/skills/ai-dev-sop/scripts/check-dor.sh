#!/usr/bin/env bash
# check-dor.sh — L1 Definition of Ready 机械检查（P1 harness）
# 用法:
#   ./skills/ai-dev-sop/scripts/check-dor.sh <SPEC.md> [ACCEPTANCE.md]
#   MIN_OUT=3 MIN_EDGE=3 MAX_OPEN=2 ./.../check-dor.sh SPEC.md ACCEPTANCE.md
#
# 退出码: 0 通过; 1 未通过; 2 用法/文件错误
# 说明: 只做可机械判定项；「用户批准」仍须人工。

set -euo pipefail

MIN_OUT="${MIN_OUT:-3}"
MIN_EDGE="${MIN_EDGE:-3}"
MAX_OPEN="${MAX_OPEN:-2}"

usage() {
  cat <<'EOF'
Usage: check-dor.sh <SPEC.md> [ACCEPTANCE.md]

Checks (mechanical):
  - Out of Scope items >= MIN_OUT (default 3)
  - Open Questions with status open <= MAX_OPEN (default 2)
  - Edge cases >= MIN_EDGE (default 3) from SPEC and/or ACCEPTANCE
  - Weasel / unmeasurable words in SPEC (+ ACCEPTANCE if given)
  - Placeholder leftovers (<简短标题>, <粘贴>, etc.)

Does NOT check: human approval signature (always manual).

Env:
  MIN_OUT  MIN_EDGE  MAX_OPEN  WEASEL_EXTRA (space-separated extra patterns)
EOF
  exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage
SPEC="$1"
ACC="${2:-}"

if [[ ! -f "$SPEC" ]]; then
  echo "ERROR: SPEC not found: $SPEC" >&2
  exit 2
fi
if [[ -n "$ACC" && ! -f "$ACC" ]]; then
  echo "ERROR: ACCEPTANCE not found: $ACC" >&2
  exit 2
fi

FAIL=0
WARN=0
pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN  $1"; WARN=$((WARN + 1)); }

echo "=== check-dor ==="
echo "SPEC: $SPEC"
[[ -n "$ACC" ]] && echo "ACCEPTANCE: $ACC"
echo "Thresholds: Out>=$MIN_OUT OpenQ<=$MAX_OPEN Edge>=$MIN_EDGE"
echo

# --- helpers ---
# Count numbered list items under a section header until next ##
count_section_numbered() {
  local file="$1"
  local header_pat="$2"
  awk -v pat="$header_pat" '
    BEGIN { insec=0; n=0 }
    $0 ~ pat { insec=1; next }
    insec && /^## / { exit }
    insec && /^[0-9]+\.[[:space:]]+/ {
      line=$0
      sub(/^[0-9]+\.[[:space:]]+/, "", line)
      gsub(/[[:space:]]/, "", line)
      if (line != "" && line != "-" && line !~ /^</) n++
    }
    END { print n+0 }
  ' "$file"
}

# Count table data rows under header (lines starting with | that are not separator/header-ish empty)
count_table_rows_after() {
  local file="$1"
  local header_pat="$2"
  awk -v pat="$header_pat" '
    BEGIN { insec=0; n=0 }
    $0 ~ pat { insec=1; next }
    insec && /^## / { exit }
    insec && /^\|[-: ]+\|/ { next }
    insec && /^\|/ {
      # skip header row if first cell looks like # or ID
      split($0, a, "|")
      cell=a[2]
      gsub(/[[:space:]]/, "", cell)
      if (cell == "#" || cell == "ID" || cell == "实体/数据" || cell == "依赖" || cell == "项" || cell == "角色") next
      if (cell == "") next
      # skip empty template rows (only pipes and spaces)
      body=$0
      gsub(/[|[:space:]]/, "", body)
      if (body == "") next
      n++
    }
    END { print n+0 }
  ' "$file"
}

# --- 1. Out of Scope ---
echo "[1] Out of Scope"
OUT_N=$(count_section_numbered "$SPEC" "Out of Scope")
# also count bullet lines under Out of Scope
OUT_BULLETS=$(awk '
  /Out of Scope/ { insec=1; next }
  insec && /^## / { exit }
  insec && /^-[[:space:]]+/ {
    line=$0
    sub(/^-[[:space:]]+/, "", line)
    gsub(/[[:space:]]/, "", line)
    if (line != "" && line !~ /^</) n++
  }
  END { print n+0 }
' "$SPEC")
if [[ "$OUT_BULLETS" -gt "$OUT_N" ]]; then OUT_N=$OUT_BULLETS; fi
if [[ "$OUT_N" -ge "$MIN_OUT" ]]; then
  pass "Out of Scope count=$OUT_N (need >= $MIN_OUT)"
else
  fail "Out of Scope count=$OUT_N (need >= $MIN_OUT)"
fi

# --- 2. Open Questions ---
echo "[2] Open Questions (open status)"
OPEN_N=$(awk '
  /OPEN QUESTIONS|Open Questions/ { insec=1; next }
  insec && /^## / { exit }
  insec && /^\|/ {
    low=tolower($0)
    if (low ~ /\|\s*#\s*\|/ || low ~ /\|\s*id\s*\|/) next
    if ($0 ~ /^\|[-: ]+\|/) next
    # count rows that look open: open, 待, 未关闭, Y with open-ish
    if (low ~ /open/ && low !~ /closed/) { n++; next }
    if ($0 ~ /待确认|未关闭|待定/) { n++; next }
  }
  END { print n+0 }
' "$SPEC")
# Q-lines like | Q1 | ... | open |
if [[ "$OPEN_N" -le "$MAX_OPEN" ]]; then
  pass "Open (unclosed) count=$OPEN_N (need <= $MAX_OPEN)"
else
  fail "Open (unclosed) count=$OPEN_N (need <= $MAX_OPEN)"
fi

# --- 3. Edge ---
echo "[3] Edge cases"
EDGE_SPEC=$(count_section_numbered "$SPEC" "异常与边界|Edge")
EDGE_SPEC_TBL=$(count_table_rows_after "$SPEC" "异常与边界|Edge 清单|Edge /")
EDGE_ACC=0
if [[ -n "$ACC" ]]; then
  EDGE_ACC=$(count_table_rows_after "$ACC" "Edge 清单")
  # count Scenario error lines
  EDGE_SC=$(grep -cE 'Scenario:.*E[0-9]|### Error|Error / 边界' "$ACC" 2>/dev/null || true)
  EDGE_SC=${EDGE_SC:-0}
  if [[ "$EDGE_SC" -gt "$EDGE_ACC" ]]; then EDGE_ACC=$EDGE_SC; fi
fi
EDGE_N=$EDGE_SPEC
[[ "$EDGE_SPEC_TBL" -gt "$EDGE_N" ]] && EDGE_N=$EDGE_SPEC_TBL
[[ "$EDGE_ACC" -gt "$EDGE_N" ]] && EDGE_N=$EDGE_ACC

if [[ "$EDGE_N" -ge "$MIN_EDGE" ]]; then
  pass "Edge count=$EDGE_N (need >= $MIN_EDGE)"
else
  fail "Edge count=$EDGE_N (need >= $MIN_EDGE) — fill SPEC §3.2 or ACCEPTANCE Edge table"
fi

# --- 4. Weasel words ---
echo "[4] Weasel / unmeasurable words"
# Chinese + English common set; avoid matching inside code fences roughly by full-file scan (ok for P1)
WEASEL_PAT='可能|大概|适当|优化一下|尽快|更智能|更好用|或许|尽量|差不多|视情况|tbd|TODO|FIXME|\bmaybe\b|\bprobably\b|\bsomehow\b|\betc\b'
if [[ -n "${WEASEL_EXTRA:-}" ]]; then
  WEASEL_PAT="${WEASEL_PAT}|${WEASEL_EXTRA// /|}"
fi
WEASEL_HITS=$(grep -nEi "$WEASEL_PAT" "$SPEC" 2>/dev/null | grep -vE '禁止|不可测|改写|示例|检查|weasel|阈值|No |无「' || true)
if [[ -n "$ACC" ]]; then
  ACC_HITS=$(grep -nEi "$WEASEL_PAT" "$ACC" 2>/dev/null | grep -vE '禁止|不可测|改写|示例|约定' || true)
  WEASEL_HITS=$(printf '%s\n%s' "$WEASEL_HITS" "$ACC_HITS" | sed '/^$/d')
fi
if [[ -z "${WEASEL_HITS// }" ]]; then
  pass "No weasel-word hits (heuristic)"
else
  fail "Weasel-word hits found:"
  echo "$WEASEL_HITS" | head -20 | sed 's/^/         /'
fi

# --- 5. Placeholders ---
echo "[5] Template placeholders left behind"
PH_PAT='<简短标题>|<粘贴>|<一句话|<路径|<姓名|SPEC-YYYYMMDD|<与 SPEC 相同'
PH_HITS=$(grep -nE "$PH_PAT" "$SPEC" 2>/dev/null || true)
if [[ -n "$ACC" ]]; then
  PH_ACC=$(grep -nE "$PH_PAT|功能 F1: <|Scenario: F1-" "$ACC" 2>/dev/null || true)
  # F1 template left as-is is a smell
  PH_HITS=$(printf '%s\n%s' "$PH_HITS" "$PH_ACC" | sed '/^$/d')
fi
if [[ -z "${PH_HITS// }" ]]; then
  pass "No obvious empty template placeholders"
else
  warn "Possible unfilled placeholders:"
  echo "$PH_HITS" | head -15 | sed 's/^/         /'
fi

# --- 6. Approval (informational) ---
echo "[6] Human approval (manual — not enforced)"
if grep -qE '可以按此 Spec 开发|批准人:[[:space:]]*[^[:space:]]' "$SPEC"; then
  if grep -qE '批准人:[[:space:]]*$|批准人:[[:space:]]*\|' "$SPEC"; then
    warn "Approval section present but 批准人 may be empty — confirm manually"
  else
    pass "Approval-related text found (still verify in person)"
  fi
else
  warn "No explicit approval phrase found — human must approve Spec before PHASE 2 (MVP)"
fi

# --- 7. Compliance / release boundary (dim 8) ---
echo "[7] Compliance & release boundary (dim 8)"
if grep -qE '合规|发布边界|8\.1|目标区域|维 8' "$SPEC"; then
  pass "Dim-8 / compliance section markers found"
else
  warn "No dim-8 markers — fill section 7 or mark N/A with reason"
fi

echo
echo "=== summary ==="
if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULT: PASS ($WARN warning(s))"
  echo "Note: User verbal/written approval is still required before coding."
  exit 0
else
  echo "RESULT: FAIL ($FAIL failure(s), $WARN warning(s))"
  echo "Fix SPEC/ACCEPTANCE and re-run. See skills/ai-dev-sop/references/gates.md"
  exit 1
fi
