#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# A.T.H.E.N.A. — Daemon Watchdog
#
# Keeps main.py alive indefinitely. If the Python process crashes or exits
# for any reason, this script waits a few seconds and restarts it.
#
# Usage: bash scripts/daemon_watchdog.sh
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

LOG_FILE="${PROJECT_DIR}/athena_watchdog.log"
MAX_RAPID_RESTARTS=5
RAPID_RESTART_WINDOW=60  # seconds
COOLDOWN_SECONDS=30

cd "$PROJECT_DIR"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo -e "${CYAN}═══ A.T.H.E.N.A. Watchdog starting ═══${NC}"
echo "$(date '+%Y-%m-%d %H:%M:%S') — Watchdog started" >> "$LOG_FILE"

restart_count=0
window_start=$(date +%s)

while true; do
    echo -e "${GREEN}[watchdog] Starting main.py...${NC}"
    echo "$(date '+%Y-%m-%d %H:%M:%S') — Starting main.py (restart #$restart_count)" >> "$LOG_FILE"

    # Run the assistant
    python main.py 2>&1 | tee -a "$LOG_FILE"
    exit_code=$?

    echo -e "${YELLOW}[watchdog] main.py exited with code $exit_code${NC}"
    echo "$(date '+%Y-%m-%d %H:%M:%S') — main.py exited (code=$exit_code)" >> "$LOG_FILE"

    # Check for rapid restart loop (crash loop protection)
    now=$(date +%s)
    elapsed=$((now - window_start))

    if [ $elapsed -lt $RAPID_RESTART_WINDOW ]; then
        restart_count=$((restart_count + 1))
        if [ $restart_count -ge $MAX_RAPID_RESTARTS ]; then
            echo -e "${RED}[watchdog] Too many rapid restarts ($restart_count in ${elapsed}s) — cooling down ${COOLDOWN_SECONDS}s${NC}"
            echo "$(date '+%Y-%m-%d %H:%M:%S') — Crash loop detected, cooling down ${COOLDOWN_SECONDS}s" >> "$LOG_FILE"
            sleep $COOLDOWN_SECONDS
            restart_count=0
            window_start=$(date +%s)
        fi
    else
        # Reset the window
        restart_count=1
        window_start=$now
    fi

    # Brief pause before restart
    echo -e "${YELLOW}[watchdog] Restarting in 3 seconds...${NC}"
    sleep 3
done
