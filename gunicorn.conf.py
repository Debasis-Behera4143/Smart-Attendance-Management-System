"""Gunicorn configuration for Smart Attendance System - Production deployment with concurrent request handling."""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes - enables concurrent request handling
# Multiple students can mark entry/exit simultaneously
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"  # Use "gevent" for even better concurrency if installed
worker_connections = 1000
max_requests = 1000  # Restart workers after 1000 requests to prevent memory leaks
max_requests_jitter = 50  # Add randomness to prevent all workers restarting at once
timeout = 120  # 2 minutes timeout for long-running operations (like face encoding)
keepalive = 5

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "smart-attendance"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Performance tuning
preload_app = True  # Load app before forking workers (saves memory)
reload = False  # Don't reload on code changes in production

# Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"🚀 Starting Gunicorn with {workers} workers for concurrent request handling")

def when_ready(server):
    """Called just after the server is started."""
    print(f"✅ Server ready to handle concurrent student entries/exits")

def on_reload(server):
    """Called to recycle workers."""
    print("♻️  Reloading workers...")

# SSL (if needed)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"
