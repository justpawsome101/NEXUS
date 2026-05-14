# Nexus Facilities Group — IoT Misconfiguration Challenge
A Docker-based attack simulation.

## Setup
```bash
git clone https://gitlab.com/bananasoveroranges/rndp
cd nexus
chmod +x setup.sh
./setup.sh
```

Portal: http://<host-ip>:80

## Reset
```bash
docker compose down && docker compose up -d
```