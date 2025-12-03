#!/bin/bash
###############################################################################
# Apex Digital Bot - Deployment Verification Script
# 
# This script verifies that the bot environment is correctly set up and ready
# for deployment. Run this before starting the bot in production.
###############################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Apex Digital Bot - Deployment Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

ERRORS=0
WARNINGS=0

check_pass() {
    echo -e "${GREEN}✓ $1${NC}"
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((ERRORS++))
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((WARNINGS++))
}

# 1. Check Python version
echo -e "${BLUE}[1/12] Checking Python version...${NC}"
if python3 --version >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 9 ]; then
        check_pass "Python $PYTHON_VERSION (>= 3.9 required)"
    else
        check_fail "Python $PYTHON_VERSION found, but 3.9+ required"
    fi
else
    check_fail "Python 3 not found"
fi
echo ""

# 2. Check virtual environment
echo -e "${BLUE}[2/12] Checking virtual environment...${NC}"
if [ -d ".venv" ]; then
    check_pass "Virtual environment directory exists (.venv)"
    if [ "$VIRTUAL_ENV" = "" ]; then
        check_warn "Virtual environment not activated. Run: source .venv/bin/activate"
    else
        check_pass "Virtual environment active: $VIRTUAL_ENV"
    fi
else
    check_fail "Virtual environment not found. Run: python3 -m venv .venv"
fi
echo ""

# 3. Check dependencies
echo -e "${BLUE}[3/12] Checking core dependencies...${NC}"
DEPS=("discord" "aiosqlite" "pytest")
for dep in "${DEPS[@]}"; do
    if python3 -c "import $dep" 2>/dev/null; then
        VERSION=$(python3 -c "import $dep; print($dep.__version__)" 2>/dev/null || echo "installed")
        check_pass "$dep: $VERSION"
    else
        check_fail "$dep not installed"
    fi
done
echo ""

# 4. Check optional dependencies
echo -e "${BLUE}[4/12] Checking optional dependencies...${NC}"
if python3 -c "import chat_exporter" 2>/dev/null; then
    check_pass "chat-exporter installed (enhanced transcripts)"
else
    check_warn "chat-exporter not installed (will use basic transcripts)"
fi

if python3 -c "import boto3" 2>/dev/null; then
    check_pass "boto3 installed (S3 storage available)"
else
    check_warn "boto3 not installed (will use local storage)"
fi
echo ""

# 5. Check configuration files
echo -e "${BLUE}[5/12] Checking configuration files...${NC}"
if [ -f "config.json" ]; then
    check_pass "config.json exists"
    
    # Check if it's still the example file
    if grep -q "YOUR_DISCORD_BOT_TOKEN_HERE" config.json 2>/dev/null; then
        check_fail "config.json still contains placeholder token. Update with real bot token."
    else
        check_pass "config.json appears to be configured"
    fi
    
    # Validate JSON syntax
    if python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
        check_pass "config.json has valid JSON syntax"
    else
        check_fail "config.json has invalid JSON syntax"
    fi
else
    check_fail "config.json not found. Copy from config.example.json"
fi

if [ -f "config/payments.json" ]; then
    check_pass "config/payments.json exists"
else
    check_warn "config/payments.json not found (will use fallback)"
fi
echo ""

# 6. Check required directories
echo -e "${BLUE}[6/12] Checking directory structure...${NC}"
DIRS=("apex_core" "cogs" "config" "templates" "tests")
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        check_pass "$dir/ directory exists"
    else
        check_fail "$dir/ directory missing"
    fi
done

# Check for logs directory (will be created automatically but good to note)
if [ -d "logs" ]; then
    check_pass "logs/ directory exists"
else
    check_warn "logs/ directory will be created on first run"
fi
echo ""

# 7. Check main files
echo -e "${BLUE}[7/12] Checking main bot files...${NC}"
FILES=("bot.py" "config.example.json" "requirements.txt")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        check_pass "$file exists"
    else
        check_fail "$file missing"
    fi
done
echo ""

# 8. Check cog files
echo -e "${BLUE}[8/12] Checking cog modules...${NC}"
COGS=(
    "storefront.py"
    "wallet.py"
    "orders.py"
    "manual_orders.py"
    "product_import.py"
    "notifications.py"
    "ticket_management.py"
    "refund_management.py"
    "referrals.py"
    "setup.py"
)
COG_COUNT=0
for cog in "${COGS[@]}"; do
    if [ -f "cogs/$cog" ]; then
        ((COG_COUNT++))
    fi
done
if [ $COG_COUNT -eq 10 ]; then
    check_pass "All 10 cogs present"
else
    check_warn "Found $COG_COUNT/10 cogs"
fi
echo ""

# 9. Check .gitignore
echo -e "${BLUE}[9/12] Checking security (.gitignore)...${NC}"
if [ -f ".gitignore" ]; then
    check_pass ".gitignore exists"
    
    PATTERNS=("config.json" "*.db" "__pycache__" ".env")
    for pattern in "${PATTERNS[@]}"; do
        if grep -q "$pattern" .gitignore; then
            check_pass ".gitignore includes: $pattern"
        else
            check_warn ".gitignore missing pattern: $pattern"
        fi
    done
else
    check_fail ".gitignore not found"
fi
echo ""

# 10. Check database (if exists)
echo -e "${BLUE}[10/12] Checking database...${NC}"
if [ -f "bot.db" ]; then
    check_pass "bot.db exists"
    
    # Check if it's accessible
    if sqlite3 bot.db "SELECT name FROM sqlite_master WHERE type='table';" >/dev/null 2>&1; then
        TABLE_COUNT=$(sqlite3 bot.db "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
        if [ "$TABLE_COUNT" -ge 12 ]; then
            check_pass "Database has $TABLE_COUNT tables (expected 12)"
        else
            check_warn "Database has $TABLE_COUNT tables (expected 12)"
        fi
    else
        check_warn "Cannot access bot.db (may need repair)"
    fi
else
    check_warn "bot.db not found (will be created on first run)"
fi
echo ""

# 11. Check documentation
echo -e "${BLUE}[11/12] Checking documentation...${NC}"
DOCS=(
    "README.md"
    "QUICK_START_UBUNTU.md"
    "DEPLOYMENT_SUMMARY.md"
    "TESTING_CHECKLIST.md"
    "UBUNTU_E2E_TEST_REPORT.md"
)
DOC_COUNT=0
for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        ((DOC_COUNT++))
    fi
done
check_pass "Found $DOC_COUNT/5 documentation files"
echo ""

# 12. Run quick syntax check
echo -e "${BLUE}[12/12] Running Python syntax check...${NC}"
if python3 -m py_compile bot.py 2>/dev/null; then
    check_pass "bot.py syntax valid"
else
    check_fail "bot.py has syntax errors"
fi

# Check a few core modules
CORE_MODULES=("apex_core/config.py" "apex_core/database.py")
SYNTAX_OK=0
for module in "${CORE_MODULES[@]}"; do
    if python3 -m py_compile "$module" 2>/dev/null; then
        ((SYNTAX_OK++))
    fi
done
if [ $SYNTAX_OK -eq 2 ]; then
    check_pass "Core module syntax valid"
else
    check_warn "Some core modules have syntax issues"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ Perfect! All checks passed.${NC}"
    echo -e "${GREEN}✓ Your bot is ready for deployment.${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Activate virtual environment: source .venv/bin/activate"
    echo "  2. Start the bot: python bot.py"
    echo "  3. In Discord, run: !setup_store and !setup_tickets"
    echo ""
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Warnings: $WARNINGS${NC}"
    echo -e "${GREEN}✓ No critical errors found.${NC}"
    echo -e "${YELLOW}Review warnings above and proceed with caution.${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Review warnings above"
    echo "  2. Install optional dependencies (recommended): pip install -r requirements-optional.txt"
    echo "  3. Activate virtual environment: source .venv/bin/activate"
    echo "  4. Start the bot: python bot.py"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Errors: $ERRORS${NC}"
    echo -e "${YELLOW}⚠ Warnings: $WARNINGS${NC}"
    echo ""
    echo -e "${RED}Please fix the errors above before deploying.${NC}"
    echo ""
    echo -e "${BLUE}Common fixes:${NC}"
    echo "  • Missing dependencies: pip install -r requirements.txt"
    echo "  • Missing config.json: cp config.example.json config.json"
    echo "  • Update config.json with your bot token and Discord IDs"
    echo "  • Create virtual environment: python3 -m venv .venv"
    echo ""
    exit 1
fi
