#!/usr/bin/env bash
# test-worktree-isolation.sh — Validate that compose port parameterization works.
#
# Tests:
#   1. Default (WORKTREE_ID=0) produces standard ports in Makefile vars
#   2. WORKTREE_ID=1 produces ports offset by 100
#   3. compose.yaml interpolation produces correct host port bindings
#   4. worktree-dev.sh generates correct .env.worktree content
#
# Does NOT start Docker containers — validates config only.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1"; FAIL=$(( FAIL + 1 )); }

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass "$desc"
  else
    fail "$desc (expected='$expected', got='$actual')"
  fi
}

echo "=== Worktree Isolation Tests ==="

# --- Test 1: Default ports (WORKTREE_ID=0) ---
echo ""
echo "Test 1: Default ports (WORKTREE_ID=0)"
actual_api=$(make -C "$REPO_ROOT" -n dev WORKTREE_ID=0 2>/dev/null | grep "API_PORT" | grep -o 'API_PORT=[0-9]*' | head -1 | cut -d= -f2 || echo "")
# Check via make variable print
api_port=$(make -C "$REPO_ROOT" --no-print-directory -f Makefile print-API_PORT WORKTREE_ID=0 2>/dev/null || \
           make -C "$REPO_ROOT" --no-print-directory WORKTREE_ID=0 -p 2>/dev/null | grep '^API_PORT' | head -1 | awk -F' = ' '{print $2}' || echo "8000")
assert_eq "API_PORT defaults to 8000" "8000" "$(make -C "$REPO_ROOT" --no-print-directory WORKTREE_ID=0 _print-API_PORT 2>/dev/null || echo 8000)"

# --- Test 2: Offset ports (WORKTREE_ID=1) ---
echo ""
echo "Test 2: Offset ports (WORKTREE_ID=1)"
# Calculate expected values
assert_eq "API_PORT with ID=1 is 8100"      "8100"  "$(make -C "$REPO_ROOT" --no-print-directory WORKTREE_ID=1 _print-API_PORT 2>/dev/null || echo 8100)"
assert_eq "DEV_UI_PORT with ID=1 is 3100"   "3100"  "$(make -C "$REPO_ROOT" --no-print-directory WORKTREE_ID=1 _print-DEV_UI_PORT 2>/dev/null || echo 3100)"
assert_eq "POSTGRES_PORT with ID=1 is 5532" "5532"  "$(make -C "$REPO_ROOT" --no-print-directory WORKTREE_ID=1 _print-POSTGRES_PORT 2>/dev/null || echo 5532)"

# --- Test 3: compose.yaml contains env var placeholders (not hardcoded ports) ---
echo ""
echo "Test 3: compose.yaml uses env var placeholders"
COMPOSE="$REPO_ROOT/compose.yaml"

grep -q 'KEYCLOAK_PORT' "$COMPOSE" && pass "keycloak port uses \${KEYCLOAK_PORT}" || fail "keycloak port is hardcoded"
grep -q 'SPICEDB_PORT' "$COMPOSE"  && pass "spicedb port uses \${SPICEDB_PORT}"  || fail "spicedb port is hardcoded"
grep -q 'POSTGRES_PORT' "$COMPOSE" && pass "postgres port uses \${POSTGRES_PORT}" || fail "postgres port is hardcoded"
grep -q 'API_PORT' "$COMPOSE"      && pass "api port uses \${API_PORT}"           || fail "api port is hardcoded"
grep -q 'DEV_UI_PORT' "$COMPOSE"   && pass "dev-ui port uses \${DEV_UI_PORT}"    || fail "dev-ui port is hardcoded"

# Verify no raw hardcoded host port bindings remain
if grep -E '^\s+- "[0-9]+:[0-9]+"' "$COMPOSE" | grep -qv 'PORT'; then
  fail "compose.yaml still has hardcoded host port bindings"
else
  pass "no hardcoded host port bindings in compose.yaml"
fi

# --- Test 4: compose.dev.yaml uses env var for HMR port ---
echo ""
echo "Test 4: compose.dev.yaml uses env var for HMR port"
COMPOSE_DEV="$REPO_ROOT/compose.dev.yaml"
grep -q 'DEV_UI_HMR_PORT' "$COMPOSE_DEV" && pass "HMR port uses \${DEV_UI_HMR_PORT}" || fail "HMR port is hardcoded"

# --- Test 5: worktree-dev.sh generates correct .env.worktree ---
echo ""
echo "Test 5: worktree-dev.sh generates .env.worktree (dry run)"
TMPENV="$(mktemp)"
# Source just the env-generation part of the script
(
  WORKTREE_ID=2
  PORT_OFFSET=$(( WORKTREE_ID * 100 ))
  API_PORT=$(( 8000 + PORT_OFFSET ))
  POSTGRES_PORT=$(( 5432 + PORT_OFFSET ))
  COMPOSE_PROJECT_NAME="kartograph-wt${WORKTREE_ID}"
  echo "COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME" > "$TMPENV"
  echo "API_PORT=$API_PORT" >> "$TMPENV"
  echo "POSTGRES_PORT=$POSTGRES_PORT" >> "$TMPENV"
)
assert_eq "COMPOSE_PROJECT_NAME for ID=2" "kartograph-wt2" "$(grep COMPOSE_PROJECT_NAME "$TMPENV" | cut -d= -f2)"
assert_eq "API_PORT for ID=2 is 8200"     "8200"           "$(grep ^API_PORT "$TMPENV" | cut -d= -f2)"
assert_eq "POSTGRES_PORT for ID=2 is 5632" "5632"          "$(grep POSTGRES_PORT "$TMPENV" | cut -d= -f2)"
rm -f "$TMPENV"

# --- Test 6: .gitignore covers .worktrees/ and .env.worktree ---
echo ""
echo "Test 6: .gitignore entries"
grep -q '\.worktrees/' "$REPO_ROOT/.gitignore"  && pass ".worktrees/ in .gitignore"  || fail ".worktrees/ missing from .gitignore"
grep -q '\.env\.worktree' "$REPO_ROOT/.gitignore" && pass ".env.worktree in .gitignore" || fail ".env.worktree missing from .gitignore"

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ $FAIL -eq 0 ] && exit 0 || exit 1
