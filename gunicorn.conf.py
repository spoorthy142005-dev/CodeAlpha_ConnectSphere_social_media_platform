"""
Gunicorn configuration for ConnectSphere production deployment.
Recommended usage:
    gunicorn -c gunicorn.conf.py config.wsgi:application
"""

import multiprocessing
import os

# Server socket
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
backlog = 2048

# Worker processes (2 * cores + 1 is standard for I/O bound Django apps)
cpu_count = multiprocessing.cpu_count()
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, cpu_count * 2)))
worker_class = "sync"
worker_connections = 1000
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 30))
keepalive = 2

# Process naming
proc_name = "connectsphere_gunicorn"

# Logging: output stdout/stderr to console for container / systemd journal collection
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# Security: drop privileges if started as root (in Docker / production)
# user = "connectsphere"
# group = "connectsphere"

# Clean graceful restart behavior
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 50
