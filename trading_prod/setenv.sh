#!/bin/bash
# setenv.sh: Configure environment for trading_prod

# Deactivate any existing virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi

# Unset variables to avoid duplicates
unset PYTHONPATH
unset CHTRKR_ROOT

# Activate virtual environment
source /home/egirg/shared/trading_prod/venv/bin/activate

# Set environment variables
export PYTHONPATH="/home/egirg/shared/trading_prod"
export CHTRKR_ROOT="/home/egirg/shared/trading_prod"

echo "Environment set for trading_prod:"
echo "PYTHONPATH=$PYTHONPATH"
echo "CHTRKR_ROOT=$CHTRKR_ROOT"
echo "Virtual environment: $VIRTUAL_ENV"
