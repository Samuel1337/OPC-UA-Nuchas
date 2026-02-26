"""
Mock JSON API server for testing the OPC UA SPC server.

Generates random measurement data and serves it over HTTP so you can
run the full pipeline without an external data source.

Usage:
    source .venv/bin/activate
    python -m src.mock_api              # defaults: port 8080
    python -m src.mock_api --port 9090  # custom port
"""

import argparse
import json
import math
import random
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


class MockAPIHandler(BaseHTTPRequestHandler):
    """Serves synthetic measurement data at GET /api/data."""

    # Simulated process: target=10.0, natural variation ~0.5
    TARGET = 10.0
    NOISE = 0.5

    def do_GET(self):
        if self.path == "/api/data":
            self._serve_data()
        elif self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def _serve_data(self):
        # Generate 5 measurements (one subgroup) with slight drift over time
        drift = 0.3 * math.sin(time.time() / 30)
        values = [
            round(self.TARGET + drift + random.gauss(0, self.NOISE), 4)
            for _ in range(5)
        ]
        self._respond(200, {"values": values})

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[MockAPI] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Mock JSON API for SPC data")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), MockAPIHandler)
    print(f"Mock API serving at http://0.0.0.0:{args.port}/api/data")
    print(f"Generating subgroups of 5 measurements around target={MockAPIHandler.TARGET}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock API")
        server.server_close()


if __name__ == "__main__":
    main()
