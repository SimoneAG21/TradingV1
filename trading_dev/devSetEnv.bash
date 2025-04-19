#!/bin/bash
# setenv.sh: Configure environment for trading_dev

# Deactivate any existing virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi
# Unset variables to avoid duplicates
unset PYTHONPATH
unset CHTRKR_ROOT

# Activate virtual environment
source /home/egirg/shared/trading_dev/venv/bin/activate

# Set environment variables
export PYTHONPATH="/home/egirg/shared/trading_dev"
export CHTRKR_ROOT="/home/egirg/shared/trading_dev"

echo "Environment set for trading_dev:"
echo "PYTHONPATH=$PYTHONPATH"
echo "CHTRKR_ROOT=$CHTRKR_ROOT"
echo "Virtual environment: $VIRTUAL_ENV"
alias npp='notepad++.exe'
alias cmp='/mnt/c/porta/PortableApps/WinMergePortable/WinMergePortable.exe'