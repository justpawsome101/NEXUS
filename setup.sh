#!/bin/bash
set -e

echo "[*] Setting up Nexus Facilities Group challenge..."

# Check dependencies
if ! command -v docker &> /dev/null; then
  echo "[!] Docker not found — please install Docker first"
  exit 1
fi

# Support both docker-compose v1 and v2
if docker compose version &> /dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose &> /dev/null; then
  DC="docker-compose"
else
  echo "[!] docker-compose not found"
  exit 1
fi

echo "[*] Building and starting all containers..."
$DC up --build -d

echo ""
echo "[+] Nexus challenge is running"
echo ""
echo "    Web portal:  http://$(hostname -I | awk '{print $1}'):80"
echo "    (or)         http://localhost:80"
echo ""
echo "    Port scan will show: port 80 only"
echo "    All other services are internal to Docker networks"
echo ""
echo "[*] Useful commands:"
echo "    $DC logs -f                          # all logs"
echo "    $DC logs -f thermostat-01 pump-ctrl-01  # IoT device logs only"
echo "    $DC down                             # stop everything"
echo "    $DC down -v                          # stop and remove volumes"
