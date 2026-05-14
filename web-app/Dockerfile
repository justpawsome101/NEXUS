FROM debian:bullseye-slim

RUN apt-get update && \
    apt-get install -y git python3 python3-pip && \
    pip3 install flask==3.0.3 gunicorn==20.0.4 paho-mqtt==1.6.1 requests==2.31.0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN mkdir -p /var/www/html/static && \
    cp -r /app/static /var/www/html/static && \
    mkdir -p /tmp/gitbuild && cd /tmp/gitbuild && \
    git init && \
    git config user.email "dev@nexusfacilities.io" && \
    git config user.name "Nexus Dev" && \
    printf 'FLASK_ENV=production\nFLASK_DEBUG=1\nINTERNAL_TOKEN=eff92ab3d1f4c8e7b2a09d3f6e1c5b8a\nMQTT_BROKER=mqtt-broker\n' > .env && \
    printf '# Nexus Platform\n## Internal admin\nDevice manager endpoint: /nx-internal/devicemanager/runtime-cfg\nRequires X-Internal-Token header (see .env)\nNOTE: Change custom proxy\n' > README.md && \
    printf '# Legacy entry\n# Internal device manager: /nx-internal/devicemanager/\n# Token: see .env INTERNAL_TOKEN\n' > app_v1.py && \
    git add -A && git commit -q -m "initial commit - platform setup" && \
    printf '## v2.4.0\n- Added device listing\n- Updated internal token\n' > CHANGELOG.md && \
    git add -A && git commit -q -m "add changelog and v2.4.0 features" && \
    git rm -q .env app_v1.py && \
    printf '.env\n__pycache__/\n*.pyc\n' > .gitignore && \
    git add -A && git commit -q -m "cleanup: remove .env and dead code, add .gitignore" && \
    echo "# Nexus Platform v2.4.1" >> README.md && \
    git add -A && git commit -q -m "v2.4.1 release" && \
    cp -r /tmp/gitbuild/.git /app/static/.git && \
    git --git-dir=/app/static/.git update-server-info && \
    rm -rf /tmp/gitbuild

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
CMD ["/entrypoint.sh"]