#!/bin/bash
# Convenient wrapper script to run the CMS tracker with proper environment

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}CMS Star Rating Tracker${NC}"
echo "================================"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not found${NC}"
    echo "Creating virtual environment..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate venv
echo "Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to activate virtual environment${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import pandas, requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt --quiet
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install dependencies${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies OK${NC}"
fi

echo ""
echo "================================"
echo -e "${GREEN}Running tracker...${NC}"
echo "================================"
echo ""

# Run the tracker with all arguments passed to this script
python track_cms_star_rating_change.py "$@"

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ Tracker completed successfully${NC}"
else
    echo -e "${RED}✗ Tracker failed with exit code $exit_code${NC}"
    echo "Check cms_tracker.log for details"
fi

exit $exit_code
