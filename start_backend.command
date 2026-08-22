#!/bin/bash

# Resolve the absolute directory where this command script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Workspace root resolved to: $DIR"

VENV_PYTHON="$DIR/venv/bin/python3"

# Verify virtual environment exists
if [ -f "$VENV_PYTHON" ]; then
    echo "Activating virtual environment python at: $VENV_PYTHON"
    export PATH="$DIR/venv/bin:$PATH"
    source venv/bin/activate 2>/dev/null || true
else
    echo "❌ Error: Virtual environment (venv) not found at workspace root ($VENV_PYTHON)!"
    read -p "Press Enter to exit..."
    exit 1
fi

# Navigate to the backend directory so main.py runs with its local context
cd backend

# Start the server with --reload for instant Hot-Reloading on code edits
echo "Starting Miracle Auto-Entry Backend Server on port 8000 (Hot-Reload Enabled)..."
"$VENV_PYTHON" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
