"""
Quick Start Script for Smart Attendance System with Concurrent Processing

This script starts the application with concurrent request handling enabled,
allowing multiple students to mark entry/exit at the same time.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🎓 Smart Attendance System - Concurrent Mode")
print("=" * 70)
print()
print("✅ Concurrent request handling enabled")
print("✅ Multiple students can mark entry/exit simultaneously")
print("✅ Optimized database with WAL mode and busy timeout")
print()
print("-" * 70)

# Check if running in production or development
is_production = os.getenv("SMART_ATTENDANCE_ENV", "development") != "development"

if is_production:
    print("🚀 Starting in PRODUCTION mode with Gunicorn...")
    print("-" * 70)
    
    # Use gunicorn for production
    from gunicorn.app.wsgiapp import run
    sys.argv = [
        "gunicorn",
        "--config", "gunicorn.conf.py",
        "web.wsgi:app"
    ]
    sys.exit(run())
else:
    print("🛠️  Starting in DEVELOPMENT mode with Flask...")
    print("⚠️  For production, set SMART_ATTENDANCE_ENV=production")
    print("-" * 70)
    print()
    
    # Use Flask development server with threading
    from web.app import app
    import src.config as config
    
    app.run(
        debug=config.FLASK_DEBUG,
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        threaded=True,  # Enable concurrent request handling
        use_reloader=False
    )
