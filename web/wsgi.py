"""Production entrypoint for Smart Attendance API using Waitress or Gunicorn."""

import os

import sys

import logging







sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



import src.config as config

from app import app, startup_cleanup



logger = logging.getLogger(__name__)





os.makedirs(config.DATASET_PATH, exist_ok=True)

os.makedirs(config.ENCODINGS_PATH, exist_ok=True)

os.makedirs(config.DATABASE_PATH, exist_ok=True)

os.makedirs(config.LOGS_PATH, exist_ok=True)

os.makedirs(config.REPORTS_PATH, exist_ok=True)





logger.info("Running startup cleanup...")

startup_cleanup()

logger.info("Startup cleanup complete")











if __name__ == "__main__":



    from waitress import serve





    serve(

        app,

        host=config.FLASK_HOST,

        port=config.FLASK_PORT,

        channel_timeout=180,

        asyncore_loop_timeout=1,

        outbuf_overflow=1048576,

        inbuf_overflow=524288,

        connection_limit=100,

        cleanup_interval=10,

        recv_bytes=8192,

        send_bytes=8192,

        threads=4

    )

