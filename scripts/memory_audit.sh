#!/bin/bash
# Pre-deploy memory audit for MLB Win Forecaster
# Run on VPS BEFORE deploying: bash scripts/memory_audit.sh
# This is the INFRA-01 hard gate -- deploy is blocked if headroom < 1GB

set -e

echo "=== VPS Memory Audit ==="
echo ""

echo "System RAM:"
free -h | head -2
echo ""

echo "Current Docker container memory usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null || echo "(no running containers)"
echo ""

echo "Projected MLB stack additions:"
echo "  api:    512MB"
echo "  worker: 1024MB"
echo "  db:     512MB"
echo "  Total:  2048MB (2GB)"
echo ""

USED_MB=$(free -m | awk '/Mem:/ {print $3}')
TOTAL_MB=$(free -m | awk '/Mem:/ {print $2}')
AVAILABLE_MB=$((TOTAL_MB - USED_MB))
NEEDED_MB=2048
REMAINING_MB=$((AVAILABLE_MB - NEEDED_MB))

echo "Currently used:    ${USED_MB}MB"
echo "Total RAM:         ${TOTAL_MB}MB"
echo "Available:         ${AVAILABLE_MB}MB"
echo "MLB stack needs:   ${NEEDED_MB}MB"
echo "Remaining after:   ${REMAINING_MB}MB"
echo ""

if [ "$REMAINING_MB" -lt 1000 ]; then
    echo "DEPLOY GATE: FAIL -- Less than 1GB headroom remaining after deploy."
    echo "Action required: Free memory or reduce container limits before deploying."
    exit 1
else
    echo "DEPLOY GATE: PASS -- Sufficient memory headroom (${REMAINING_MB}MB remaining)."
    exit 0
fi
