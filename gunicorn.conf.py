"""Gunicorn configuration for Smart Attendance System - Production deployment with concurrent request handling."""



import multiprocessing

import os





bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

backlog = 2048







workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))

worker_class = "sync"

worker_connections = 1000

max_requests = 1000

max_requests_jitter = 50

timeout = 120

keepalive = 5





accesslog = "-"

errorlog = "-"

loglevel = os.getenv("LOG_LEVEL", "info").lower()

access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'





proc_name = "smart-attendance"





daemon = False

pidfile = None

umask = 0

user = None

group = None

tmp_upload_dir = None





preload_app = True

reload = False





def on_starting(server):

    """Called just before the master process is initialized."""

    print(f"🚀 Starting Gunicorn with {workers} workers for concurrent request handling")



def when_ready(server):

    """Called just after the server is started."""

    print(f"✅ Server ready to handle concurrent student entries/exits")



def on_reload(server):

    """Called to recycle workers."""

    print("♻️  Reloading workers...")









