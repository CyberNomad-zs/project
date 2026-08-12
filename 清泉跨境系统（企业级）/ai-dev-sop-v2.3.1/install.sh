#!/usr/bin/env bash
# install.sh — AI 开发 SOP 安装与健康检查
# 用法:
#   ./install.sh                  # 校验 + 用户级多客户端 Skill 链 + 本仓项目链
#   ./install.sh --check          # 仅校验，不写 symlink
#   ./install.sh --no-global      # 不写用户级 ~/.*/skills
#   ./install.sh --no-project     # 不写仓库内 .*/skills
#   ./install.sh --tool all       # 适配目标：all|cursor|claude|grok|agents
#   ./install.sh --into DIR       # 把 SOP 核心同步到业务仓 DIR，并在 DIR 内装项目链
#   ./install.sh --copy           # 用复制代替 symlink（部分环境 symlink 不可用）
#
# 退出码: 0 成功; 1 校验失败; 2 参数错误

set -euo pipefail

TOOL="all"
CHECK_ONLY=0
USE_COPY=0
INSTALL_GLOBAL=1
INSTALL_PROJECT=1
INTO=""

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \?//'
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --copy) USE_COPY=1; shift ;;
    --no-global) INSTALL_GLOBAL=0; shift ;;
    --no-project) INSTALL_PROJECT=0; shift ;;
    --tool) TOOL="${2:-}"; shift 2 ;;
    --into) INTO="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

case "$TOOL" in
  all|cursor|claude|grok|agents) ;;
  *) echo "ERROR: --tool must be all|cursor|claude|grok|agents" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR"

if [[ -n "$INTO" ]]; then
  INTO="$(cd "$INTO" 2>/dev/null && pwd)" || { echo "ERROR: --into path not found: $INTO" >&2; exit 2; }
fi

# --- colors (optional) ---
ok()   { echo "  PASS  $*"; }
fail() { echo "  FAIL  $*"; FAILS=$((FAILS+1)); }
warn() { echo "  WARN  $*"; WARNS=$((WARNS+1)); }
info() { echo "  ·  $*"; }

FAILS=0
WARNS=0

echo "=== AI 开发 SOP install ==="
echo "SOP root: $ROOT"
[[ -n "$INTO" ]] && echo "Target:   $INTO"
echo "Global:   $([[ "$INSTALL_GLOBAL" -eq 1 ]] && echo on || echo off)  (user-level skills)"
echo "Project:  $([[ "$INSTALL_PROJECT" -eq 1 ]] && echo on || echo off)  (repo-level skills)"
echo "Tool:     $TOOL"
echo

# --- required layout relative to ROOT ---
REQUIRED_PATHS=(
  "skills/ai-dev-sop/SKILL.md"
  "skills/ai-dev-sop/references/workflow.md"
  "skills/ai-dev-sop/references/gates.md"
  "skills/ai-dev-sop/references/l1-scan-dimensions.md"
  "skills/ai-dev-sop/references/checklists/gate-a-plan.md"
  "skills/ai-dev-sop/references/checklists/gate-b-findings.md"
  "skills/ai-dev-sop/references/checklists/gate-c-diff.md"
  "skills/ai-dev-sop/scripts/check-dor.sh"
  "skill-pack/01-req-clarify/SKILL.md"
  "skill-pack/02-mvp-cut/SKILL.md"
  "skill-pack/03-arch-design/SKILL.md"
  "skill-pack/04-spec-to-plan/SKILL.md"
  "skill-pack/05-implement-verify/SKILL.md"
  "skill-pack/06-review-ship/SKILL.md"
  "skills/ai-dev-sop/references/checklists/gate-m-mvp.md"
  "skills/ai-dev-sop/references/checklists/gate-d-arch.md"
  "templates/ARCHITECTURE.md"
  "templates/PLAN.md"
  "docs/节点交付物.md"
  "使用说明.md"
  "templates/INTENT-raw.md"
  "templates/INTENT.md"
  "templates/SPEC.md"
  "templates/ACCEPTANCE.md"
  "templates/spec-compliance-checklist.md"
  "AGENTS.md"
  "README.md"
)

echo "[1] Layout check (SOP package)"
for rel in "${REQUIRED_PATHS[@]}"; do
  if [[ -f "$ROOT/$rel" ]] || [[ -d "$ROOT/$rel" ]]; then
    ok "$rel"
  else
    fail "missing $rel"
  fi
done

# check-dor executable + smoke
echo
echo "[2] check-dor.sh"
DOR="$ROOT/skills/ai-dev-sop/scripts/check-dor.sh"
if [[ -f "$DOR" ]]; then
  chmod +x "$DOR" 2>/dev/null || true
  if [[ -x "$DOR" ]]; then
    ok "executable"
  else
    warn "not executable (chmod may have failed)"
  fi
  if [[ -f "$ROOT/docs/specs/SPEC-smoke.md" && -f "$ROOT/docs/specs/ACCEPTANCE-smoke.md" ]]; then
    if "$DOR" "$ROOT/docs/specs/SPEC-smoke.md" "$ROOT/docs/specs/ACCEPTANCE-smoke.md" >/dev/null 2>&1; then
      ok "smoke SPEC+ACCEPTANCE → PASS"
    else
      fail "smoke check-dor failed"
    fi
  else
    warn "smoke fixtures missing; skip dor smoke"
  fi
else
  fail "check-dor.sh missing"
fi

# --- sync into product repo ---
sync_into() {
  local dest="$1"
  echo
  echo "[3] Sync core dirs → $dest"
  local dirs=(skills/ai-dev-sop skill-pack templates)
  local files=(AGENTS.md)
  # human-facing SOP docs (not full research history)
  local doc_files=(
    docs/节点交付物.md
    docs/00-总览与流程图.md
    docs/L0-心智与禁区.md
    docs/L1-需求澄清.md
    docs/L2-开发执行.md
    docs/L3-评审发布.md
    docs/试跑剧本.md
    docs/试跑记录.md
    docs/试点投产检查单.md
  )
  for d in "${dirs[@]}"; do
    mkdir -p "$dest/$(dirname "$d")"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --delete "$ROOT/$d/" "$dest/$d/"
    else
      rm -rf "$dest/$d"
      mkdir -p "$dest/$d"
      cp -R "$ROOT/$d/." "$dest/$d/"
    fi
    ok "synced $d/"
  done
  for f in "${files[@]}"; do
    if [[ -f "$dest/$f" ]]; then
      # merge note: do not clobber existing AGENTS without backup
      if ! grep -q 'ai-dev-sop' "$dest/$f" 2>/dev/null; then
        cp "$dest/$f" "$dest/${f}.bak-sop-$(date +%Y%m%d%H%M%S)"
        {
          echo ""
          echo "# --- appended by AI 开发 SOP install.sh ---"
          cat "$ROOT/$f"
        } >> "$dest/$f"
        warn "appended SOP AGENTS.md block into existing $f (backup created)"
      else
        ok "$f already mentions ai-dev-sop (left unchanged)"
      fi
    else
      cp "$ROOT/$f" "$dest/$f"
      ok "copied $f"
    fi
  done
  mkdir -p "$dest/docs/specs"
  for df in "${doc_files[@]}"; do
    if [[ -f "$ROOT/$df" ]]; then
      mkdir -p "$dest/$(dirname "$df")"
      cp "$ROOT/$df" "$dest/$df"
      ok "synced $df"
    else
      warn "missing $df (skip)"
    fi
  done
  ok "ensured docs/specs/"
}

# Project-local skill link (relative symlink inside a repo)
link_skill() {
  local base="$1"   # product or sop root where skills/ai-dev-sop lives
  local tool_dir="$2"
  local label="$3"

  mkdir -p "$tool_dir"
  local target_link="$tool_dir/ai-dev-sop"
  local src="$base/skills/ai-dev-sop"

  if [[ ! -d "$src" ]]; then
    fail "source skill missing: $src"
    return
  fi

  local rel
  rel="$(python3 - "$tool_dir" "$src" <<'PY'
import os, sys
tool, src = sys.argv[1], sys.argv[2]
print(os.path.relpath(src, start=tool))
PY
)"

  if [[ "$USE_COPY" -eq 1 ]]; then
    rm -rf "$target_link"
    cp -R "$src" "$target_link"
    ok "$label: copied → $target_link"
  else
    ln -sfn "$rel" "$target_link"
    ok "$label: symlink $target_link → $rel"
  fi
}

# Absolute symlink/copy into a user-level skills directory
link_global_skill() {
  local dest_dir="$1"
  local label="$2"
  local src="$ROOT/skills/ai-dev-sop"
  local dest="${dest_dir}/ai-dev-sop"

  if [[ ! -d "$src" ]]; then
    fail "source skill missing: $src"
    return
  fi
  mkdir -p "$dest_dir"
  if [[ "$USE_COPY" -eq 1 ]]; then
    rm -rf "$dest"
    cp -R "$src" "$dest"
    ok "$label: copied → $dest"
  else
    ln -sfn "$src" "$dest"
    ok "$label: symlink $dest → $src"
  fi
}

# User-level skills for supported clients
install_global_skills() {
  echo
  echo "[4a] User-level Skill links"
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    info "--check: skip global links"
    return
  fi
  if [[ "$INSTALL_GLOBAL" -ne 1 ]]; then
    info "--no-global: skip"
    return
  fi

  case "$TOOL" in
    all)
      link_global_skill "${HOME}/.cursor/skills" "user ~/.cursor/skills"
      link_global_skill "${HOME}/.claude/skills" "user ~/.claude/skills"
      link_global_skill "${HOME}/.grok/skills" "user ~/.grok/skills"
      link_global_skill "${HOME}/.agents/skills" "user ~/.agents/skills"
      ;;
    cursor) link_global_skill "${HOME}/.cursor/skills" "user ~/.cursor/skills" ;;
    claude) link_global_skill "${HOME}/.claude/skills" "user ~/.claude/skills" ;;
    grok)   link_global_skill "${HOME}/.grok/skills" "user ~/.grok/skills" ;;
    agents) link_global_skill "${HOME}/.agents/skills" "user ~/.agents/skills" ;;
  esac
}

install_project_tools() {
  local base="$1"
  echo
  echo "[4b] Project Skill links (base=$base)"
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    info "--check: skip project links"
    return
  fi
  if [[ "$INSTALL_PROJECT" -ne 1 ]]; then
    info "--no-project: skip"
    return
  fi
  case "$TOOL" in
    all)
      link_skill "$base" "$base/.cursor/skills" "project .cursor/skills"
      link_skill "$base" "$base/.claude/skills" "project .claude/skills"
      link_skill "$base" "$base/.grok/skills" "project .grok/skills"
      link_skill "$base" "$base/.agents/skills" "project .agents/skills"
      ;;
    cursor) link_skill "$base" "$base/.cursor/skills" "project .cursor/skills" ;;
    claude) link_skill "$base" "$base/.claude/skills" "project .claude/skills" ;;
    grok)   link_skill "$base" "$base/.grok/skills" "project .grok/skills" ;;
    agents) link_skill "$base" "$base/.agents/skills" "project .agents/skills" ;;
  esac
}

# --- run install steps ---
if [[ -n "$INTO" ]]; then
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    info "--check with --into: only validating SOP package, not syncing"
  else
    sync_into "$INTO"
  fi
else
  echo
  echo "[3] Sync: skipped (no --into)"
fi

install_global_skills

if [[ -n "$INTO" ]]; then
  install_project_tools "$INTO"
else
  install_project_tools "$ROOT"
fi

echo
echo "[5] Next steps"
cat <<EOF
  1. 在已适配的 Agent 客户端中确认可调用: /ai-dev-sop
  2. 读 skill-pack / templates：按 SOP_ROOT（本包真实路径），不必 --into
  3. 写制品：当前业务仓 docs/specs/
  4. 甲方 INTENT-raw → 产品 INTENT → /ai-dev-sop
  5. 说明见 使用说明.md ；试跑见 docs/试跑剧本.md

  仅用户级（推荐个人）:
    ./install.sh --no-project
  只装某一客户端:
    ./install.sh --tool cursor|claude|grok|agents
  团队同步进业务仓:
    ./install.sh --into /path/to/your-product-repo
  SOP_ROOT 本机:
    $ROOT
EOF

echo
echo "=== summary ==="
if [[ "$FAILS" -eq 0 ]]; then
  echo "RESULT: OK ($WARNS warning(s))"
  exit 0
else
  echo "RESULT: FAILED ($FAILS failure(s), $WARNS warning(s))"
  exit 1
fi
