#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# A.T.H.E.N.A. — Termux 24/7 Setup Script
#
# One-click setup to make the Python backend run 24/7 on Android via Termux.
# Run this once: bash scripts/setup_termux_24_7.sh
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  A.T.H.E.N.A. — Termux 24/7 Backend Setup${NC}"
echo -e "${CYAN}  Adaptive Thinking Hands-free Engine for Neural Assistance${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ──────────────────────────────────────────────────────────────────────────
# Step 1: Acquire Termux Wake Lock
# ──────────────────────────────────────────────────────────────────────────
echo -e "${YELLOW}[1/5] Acquiring Termux wake lock...${NC}"
if command -v termux-wake-lock &>/dev/null; then
    termux-wake-lock
    echo -e "${GREEN}  ✅ Wake lock acquired — Termux will not be killed by Android${NC}"
else
    echo -e "${RED}  ⚠️  termux-wake-lock not found — install Termux:API${NC}"
fi

# ──────────────────────────────────────────────────────────────────────────
# Step 2: Install required Termux packages
# ──────────────────────────────────────────────────────────────────────────
echo -e "${YELLOW}[2/5] Installing required Termux packages...${NC}"
pkg update -y 2>/dev/null || true

PACKAGES="python termux-api"
for pkg_name in $PACKAGES; do
    if ! dpkg -l "$pkg_name" &>/dev/null; then
        echo -e "  Installing $pkg_name..."
        pkg install -y "$pkg_name" 2>/dev/null || true
    else
        echo -e "  ${GREEN}✅ $pkg_name already installed${NC}"
    fi
done

# ──────────────────────────────────────────────────────────────────────────
# Step 3: Setup Python virtual environment & dependencies
# ──────────────────────────────────────────────────────────────────────────
echo -e "${YELLOW}[3/5] Setting up Python environment...${NC}"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "  Installing Python dependencies..."
pip install -q -r requirements.txt 2>/dev/null || {
    echo -e "${RED}  ⚠️  Some dependencies may have failed — check requirements.txt${NC}"
}
echo -e "${GREEN}  ✅ Python environment ready${NC}"

# ──────────────────────────────────────────────────────────────────────────
# Step 4: Create Termux:Boot auto-start script
# ──────────────────────────────────────────────────────────────────────────
echo -e "${YELLOW}[4/5] Setting up Termux:Boot auto-start...${NC}"

BOOT_DIR="$HOME/.termux/boot"
BOOT_SCRIPT="$BOOT_DIR/start-athena.sh"

mkdir -p "$BOOT_DIR"

cat > "$BOOT_SCRIPT" << BOOTEOF
#!/data/data/com.termux/files/usr/bin/bash
# ═══ A.T.H.E.N.A. Auto-Start Script (Termux:Boot) ═══
# This script runs automatically when the phone boots.

# Acquire wake lock so Android doesn't kill Termux
termux-wake-lock

# Small delay to let the system settle after boot
sleep 10

# Navigate to project and start the AI backend with watchdog
cd "$PROJECT_DIR"

# Start with the watchdog wrapper for crash recovery
exec bash scripts/daemon_watchdog.sh
BOOTEOF

chmod +x "$BOOT_SCRIPT"
echo -e "${GREEN}  ✅ Boot script created at: $BOOT_SCRIPT${NC}"
echo -e "  ${CYAN}(Requires Termux:Boot app from F-Droid)${NC}"

# ──────────────────────────────────────────────────────────────────────────
# Step 5: Create .env if not exists
# ──────────────────────────────────────────────────────────────────────────
echo -e "${YELLOW}[5/5] Checking configuration...${NC}"

if [ -f "$PROJECT_DIR/.env" ]; then
    echo -e "${GREEN}  ✅ .env file exists${NC}"
else
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo -e "${YELLOW}  ⚠️  Created .env from .env.example — edit with your API keys!${NC}"
    else
        echo -e "${RED}  ❌ No .env or .env.example found${NC}"
    fi
fi

# ──────────────────────────────────────────────────────────────────────────
# Done
# ──────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ A.T.H.E.N.A. Termux 24/7 setup complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}To start the backend now:${NC}"
echo -e "    bash scripts/daemon_watchdog.sh"
echo ""
echo -e "  ${CYAN}Or simply reboot your phone — Termux:Boot will auto-start.${NC}"
echo ""
echo -e "  ${CYAN}Then open the ATHENA Android app and tap 'Start ATHENA'.${NC}"
echo ""
