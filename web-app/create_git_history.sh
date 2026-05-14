#!/bin/bash
# fake git history

set -e

mkdir -p /app/.git_exposed
cd /app/.git_exposed

git init
git config user.email "dev@nexusfacilities.io"
git config user.name "Nexus Dev"

#  initial app with .env containing secrets
mkdir -p templates static/css

cat > .env << 'EOF'
FLASK_ENV=production
FLASK_DEBUG=1
INTERNAL_TOKEN=eff92ab3d1f4c8e7b2a09d3f6e1c5b8a
MQTT_BROKER=mqtt-broker
MQTT_PORT=1883
MQTT_USER=iotadmin
MQTT_PASS=Str0ngP@ss!
INTERNAL_API_HOST=api-service
INTERNAL_API_PORT=80
EOF

cat > README.md << 'EOF'
# Nexus Facilities Platform

Internal deployment repo.

## Services
- Web app: Flask + gunicorn behind nginx
- API: FastAPI internal service
- MQTT: Mosquitto broker
- Devices: thermostat-01, pump-ctrl-01

## Admin
Internal config endpoint: v2/admin/config
Requires X-Internal-Token header — see .env
EOF

cat > app_old.py << 'EOF'
# Old app entry — kept for reference
# Internal API base: /v2/admin/
# Token: see .env INTERNAL_TOKEN
import os
from flask import Flask
app = Flask(__name__)
EOF

git add .
git commit -m "initial commit — platform setup"

cat > CHANGELOG.md << 'EOF'
## v2.4.0
- Added device listing endpoint
- Improved dashboard rendering
- Internal API token updated in .env
EOF

git add .
git commit -m "add changelog and feature updates"

git rm .env
git rm app_old.py

cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
*.pyo
.DS_Store
EOF

git add .
git commit -m "cleanup: remove .env and dead code, add .gitignore"

echo "# Nexus Platform v2.4.1" >> README.md
git add .
git commit -m "v2.4.1 release"

echo "Git history created successfully"
git log --oneline
