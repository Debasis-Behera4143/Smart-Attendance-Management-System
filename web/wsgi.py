"""Production entrypoint for Smart Attendance API using Waitress or Gunicorn."""
import os
import sys
import logging 



sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.config as config
from app import app, startup_cleanup

logger = logging.getLogger(__name__)

# Ensure directories exist
os.makedirs(config.DATASET_PATH, exist_ok=True)
os.makedirs(config.ENCODINGS_PATH, exist_ok=True)
os.makedirs(config.DATABASE_PATH, exist_ok=True)
os.makedirs(config.LOGS_PATH, exist_ok=True)
os.makedirs(config.REPORTS_PATH, exist_ok=True)

# Run startup cleanup when module is loaded (for gunicorn/waitress)
logger.info("Running startup cleanup...")
startup_cleanup()
logger.info("Startup cleanup complete")

# Export app for WSGI servers (gunicorn, waitress, etc.)
# Usage: gunicorn web.wsgi:app
# This ensures startup_cleanup runs before serving requests

if __name__ == "__main__":
    # For local development with waitress
    from waitress import serve
    
    # Increased timeouts for long-running image processing operations
    serve(
        app, 
        host=config.FLASK_HOST, 
        port=config.FLASK_PORT,
        channel_timeout=180,  # 3 minutes for channel timeout
        asyncore_loop_timeout=1,  # Poll interval
        outbuf_overflow=1048576,  # 1MB outbound buffer
        inbuf_overflow=524288,  # 512KB inbound buffer
        connection_limit=100,  # Max simultaneous connections
        cleanup_interval=10,  # Cleanup idle connections every 10s
        recv_bytes=8192,  # Receive buffer size
        send_bytes=8192,  # Send buffer size
        threads=4  # Worker threads
    )
