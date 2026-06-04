#!/bin/bash

# Start LogSentry AI Flask Application
# For Linux/Mac

echo "========================================="
echo "  LogSentry AI - Starting Server"
echo "========================================="
echo ""

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo "✓ Found virtual environment"
    source venv/bin/activate
else
    echo "⚠ Virtual environment not found"
    echo "  Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate

    echo "  Installing dependencies..."
    pip install -r requirements_flask.txt
fi

# Check if data directory exists
if [ ! -d "data" ]; then
    echo "  Creating data directory..."
    mkdir -p data/models data/processed data/raw
fi

# Start Flask application
echo ""
echo "🚀 Starting Flask server on http://localhost:5000"
echo ""
echo "   Default credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "   Press Ctrl+C to stop"
echo ""
echo "-----------------------------------------"
echo ""

python run.py
