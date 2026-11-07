# TrisDashboard

Local dashboard for iPad mini (1st generation, iOS 9 Safari), iPhone, and desktop. The MacBook is the server, and clients connect over trusted home Wi-Fi.

## Setup (Python 3.11+)
```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8080
```

Open http://127.0.0.1:8080 on the Mac. On an iPad/iPhone connected to the same Wi-Fi, open `http://<macbook-local-ip>:8080` (find the local IP in macOS Wi-Fi settings). Permit incoming Python connections in macOS Firewall if prompted. The Mac must remain awake to serve clients.

**Security:** This initial service has no login and is intended only for a trusted home LAN. Never expose port 8080 to the public internet, and do not store secrets in the frontend. iOS 9 client support requires testing on the actual iPad mini.

## Tests
```sh
pip install -r requirements-dev.txt
python -m pytest -q
```

## Endpoints
- `/` dashboard
- `/healthz` lightweight health probe

## Design
- Dark dashboard, two-column landscape layout, single-column mobile layout.
- Conservative CSS and ES5 JavaScript for legacy Safari.
- Live clock; connection indicator checks the health endpoint and recovers after outages.
- Portfolio, development, weather, and fitness are placeholders until data integrations are implemented.

## Next
Real-device iOS 9 verification; optional macOS launchd auto-start; integrations with server-managed credentials.
