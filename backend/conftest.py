"""Ensure test env is set in-process BEFORE any test module imports.

The test modules read REACT_APP_BACKEND_URL / MONGO_URL / DB_NAME at import time
(module top-level). Shell env vars can be lost by xdist workers, so set them here
at the earliest possible point in pytest startup.
"""
import os

os.environ.setdefault("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001")
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "appnsaas_test")
