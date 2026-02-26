"""Production entrypoint for Smart Attendance API using Waitress."""

import os
import sys

from waitress import serve

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.config as config
from app import app


if __name__ == "__main__":
    serve(app, host=config.FLASK_HOST, port=config.FLASK_PORT)
