#!/bin/bash
set -e

# Start gunicorn on localhost — not exposed externally
gunicorn \
  --bind 127.0.0.1:8000 \
  --workers 1 \
  --timeout 60 \
  --access-logfile - \
  --access-logformat '%(h)s "%(r)s" %(s)s' \
  app:app &

sleep 2

# Start the vulnerable proxy on port 80
exec python3 /app/proxy.py
