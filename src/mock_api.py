"""
Mock JSON API server for testing the OPC UA server.

Generates realistic HACCP quality check form data (CCP1/CCP3) over HTTP
so you can run the full pipeline without an external data source.

Includes a web frontend for submitting custom form data and monitoring
whether the OPC UA server has picked it up.

Usage:
    source .venv/bin/activate
    python -m src.mock_api              # defaults: port 8080
    python -m src.mock_api --port 9090  # custom port

Endpoints:
    GET  /            - Web frontend for form entry and monitoring
    GET  /api/forms   - CCP1 and CCP3 quality check form data
    POST /api/forms   - Submit custom form data (replaces auto-generated)
    GET  /api/status  - Submission log with OPC poll status
    GET  /health      - Health check
"""

import argparse
import json
import random
import time
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ── Simulated chilling process state ──────────────────────────────
# Temperatures cool down over time to simulate a real chilling cycle.
_start_time = None


def _minutes_elapsed():
    global _start_time
    if _start_time is None:
        _start_time = time.time()
    return (time.time() - _start_time) / 60


def _fmt_time(offset_minutes: float = 0) -> str:
    dt = datetime.now() - timedelta(minutes=offset_minutes)
    return dt.strftime("%b-%d-%Y %I:%M %p")


def _fmt_now() -> str:
    return datetime.now().strftime("%b-%d-%Y %I:%M:%S %p")


# ── Shared submission state (thread-safe) ─────────────────────────
_lock = threading.Lock()
_custom_forms: dict[str, dict] = {}          # form_type -> latest submitted data
_submission_log: list[dict] = []             # ordered list of submissions
_submission_counter = 0
_last_opc_poll_at: str | None = None         # timestamp of last GET /api/forms


class MockAPIHandler(BaseHTTPRequestHandler):
    """Serves synthetic HACCP quality form data and the web frontend."""

    def do_GET(self):
        if self.path == "/":
            self._serve_frontend()
        elif self.path == "/api/forms":
            self._serve_forms()
        elif self.path == "/api/status":
            self._serve_status()
        elif self.path == "/health":
            self._respond_json(200, {"status": "ok"})
        else:
            self._respond_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/forms":
            self._handle_form_submission()
        else:
            self._respond_json(404, {"error": "not found"})

    # ── Frontend ──────────────────────────────────────────────────

    def _serve_frontend(self):
        html_path = Path(__file__).parent / "static" / "index.html"
        try:
            content = html_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._respond_json(500, {"error": "index.html not found"})

    # ── GET /api/forms ────────────────────────────────────────────

    def _serve_forms(self):
        global _last_opc_poll_at

        with _lock:
            # Record poll timestamp and mark pending submissions as received
            now = _fmt_now()
            _last_opc_poll_at = now
            for entry in _submission_log:
                if not entry["received"]:
                    entry["received"] = True
                    entry["received_at"] = now

        # Build response: use custom data when available, auto-generated otherwise
        forms = self._generate_forms()
        with _lock:
            for form_type, form_data in _custom_forms.items():
                forms[form_type] = form_data

        self._respond_json(200, forms)

    # ── POST /api/forms ───────────────────────────────────────────

    def _handle_form_submission(self):
        global _submission_counter

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._respond_json(400, {"error": "empty body"})
            return

        try:
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError) as e:
            self._respond_json(400, {"error": f"invalid JSON: {e}"})
            return

        if not isinstance(data, dict) or not data:
            self._respond_json(400, {"error": "expected a JSON object with form type keys"})
            return

        with _lock:
            for form_type, form_data in data.items():
                if not isinstance(form_data, dict):
                    continue
                _custom_forms[form_type] = form_data
                _submission_counter += 1
                _submission_log.append({
                    "id": _submission_counter,
                    "form_type": form_type,
                    "submitted_at": _fmt_now(),
                    "data": {form_type: form_data},
                    "received": False,
                    "received_at": None,
                })

        self._respond_json(200, {
            "status": "accepted",
            "message": f"Form data stored for: {', '.join(data.keys())}. "
                       f"OPC server will pick it up on next poll.",
        })

    # ── GET /api/status ───────────────────────────────────────────

    def _serve_status(self):
        with _lock:
            response = {
                "last_opc_poll_at": _last_opc_poll_at,
                "total_submissions": len(_submission_log),
                "submissions": list(_submission_log),
            }
        self._respond_json(200, response)

    # ── Auto-generated form data ──────────────────────────────────

    def _generate_forms(self):
        elapsed = _minutes_elapsed()

        # Simulate cooling: start at 158 F, drop toward 38 F over ~120 min
        start_temp = 158.0
        chill1_temp = max(38.0, start_temp - elapsed * 1.2 + random.gauss(0, 0.5))
        chill2_temp = max(35.0, chill1_temp - 15 - elapsed * 0.3 + random.gauss(0, 0.3))

        baking_start_temp = 138.0
        baking_c1_temp = max(26.0, baking_start_temp - elapsed * 1.5 + random.gauss(0, 0.5))

        return {
            "ccp1": {
                "header": {
                    "quality_check_id": "QC-213091",
                    "form_name": "Empanada (USDA/FDA) HACCP Record (CCP 2B) FSQ-2.4.3.12-CCP-2B",
                    "authenticated_by": "Alejandro Anzoategui (aanzo)",
                    "auth_time": _fmt_time(0),
                    "triggered_by": "CCP1B Pass = CCP2B",
                    "trigger_time": _fmt_time(120),
                    "assigned_to": "Chilling CCP1&2 Cooking, Alejandro Anzoategui",
                    "signed_off_by": "Sandra Echeverry (secheverry)",
                    "sign_off_time": _fmt_time(0),
                    "location": "Kettle 1",
                    "product": "Ground Beef Empanadas RTE 24/3oz",
                    "sku": "120001-C",
                    "run_id": "25174-001 USDA",
                    "custom_reference": "1",
                    "run_start_date": _fmt_time(180),
                    "run_end_date": _fmt_time(120),
                    "run_sign_off_time": _fmt_time(0),
                    "run_sign_off_by": "Sandra Echeverry (secheverry)",
                },
                "critical_limits_text": (
                    "All meat or poultry fillings must be chilled to reduce internal "
                    "temperature from 130 to <= 80 F in <= 1.5 hours (CHILLING 1) and "
                    "from 80 to <= 40 F in <= 5 hours (CHILLING 2)."
                ),
                "start_chilling": {
                    "batch_number": 1,
                    "temperature": round(start_temp + random.gauss(0, 1), 1),
                    "time": _fmt_time(120),
                    "passed": True,
                },
                "chilling_process_1": {
                    "batch_number": 1,
                    "temperature": round(chill1_temp, 1),
                    "time": _fmt_time(30),
                    "passed": chill1_temp <= 80.0,
                },
                "chilling_process_2": {
                    "batch_number": 1,
                    "temperature": round(chill2_temp, 1),
                    "time": _fmt_time(0),
                    "passed": chill2_temp <= 40.0,
                },
                "direct_observation": {
                    "verified_by": "Sandra Echeverry",
                    "time": _fmt_time(0),
                    "results": "Acceptable Monitoring Procedures",
                },
            },
            "ccp3": {
                "header": {
                    "quality_check_id": "QC-213092",
                    "form_name": "Empanada (USDA/FDA) HACCP Record (CCP 4B) FSQ-2.4.3.12-CCP-4B",
                    "authenticated_by": "Camilo Triana (ctriana)",
                    "auth_time": _fmt_time(0),
                    "triggered_by": "CCP3B Pass = CCP4B",
                    "trigger_time": _fmt_time(90),
                    "assigned_to": "Chilling CCP3&4 Baking, Camilo Triana",
                    "signed_off_by": "Fernanda Benavides (fbenavides)",
                    "sign_off_time": _fmt_time(0),
                    "location": "Baking Line",
                    "product": "Italian Sausage Empanadas RTE 24/3oz",
                    "sku": "122003-B",
                    "run_id": "25167-002 (1-1)",
                    "custom_reference": "1-1",
                    "run_start_date": _fmt_time(100),
                    "run_end_date": _fmt_time(90),
                    "run_sign_off_time": _fmt_time(0),
                    "run_sign_off_by": "Fernanda Benavides (fbenavides)",
                },
                "critical_limits_text": (
                    "All meat or poultry fillings must be chilled to reduce internal "
                    "temperature from 130 F to <= 80 F in <= 1.5 hours (CHILLING 1) "
                    "and from 80 F to <= 40 F in <= 5 hours (CHILLING 2)."
                ),
                "baking_start_chilling": {
                    "batch_number": 1,
                    "rack_number": 1,
                    "temperature": round(baking_start_temp + random.gauss(0, 1), 1),
                    "date_time": _fmt_time(90),
                    "passed": True,
                },
                "baking_chilling_1": {
                    "temperature": round(baking_c1_temp, 1),
                    "usl": 80.0,
                    "date_time": _fmt_time(5),
                    "passed": baking_c1_temp <= 80.0,
                },
                "baking_chilling_2": {
                    "temperature": 0.0,
                    "date_time": "",
                    "passed": False,
                },
                "direct_observation": {
                    "verified_by": "Sandra Echeverry",
                    "time": _fmt_time(0),
                    "results": "Acceptable Monitoring Procedures",
                    "comments": "",
                },
                "linked_items": [
                    "Quality Check - Empanada (USDA/FDA) HACCP Record (CCP 3B) FSQ-2.4.3.12-CCP-3B - Pass",
                    "Action Review - Baking Line Empanada (USDA/FDA) HACCP Record (CCP 3B) Review",
                    "Action Review - Empanada (USDA/FDA) HACCP Record (CCP 4B) Pre-Shipment Review",
                    "Action Review - Baking Line Empanada (USDA/FDA) HACCP Record (CCP 4B) Review",
                ],
            },
        }

    # ── Helpers ───────────────────────────────────────────────────

    def _respond_json(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[MockAPI] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Mock JSON API for HACCP data")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), MockAPIHandler)
    print(f"Mock API serving at http://0.0.0.0:{args.port}")
    print(f"  GET  /            - Web frontend")
    print(f"  GET  /api/forms   - CCP1 & CCP3 quality check forms")
    print(f"  POST /api/forms   - Submit custom form data")
    print(f"  GET  /api/status  - Submission log + OPC poll status")
    print(f"  GET  /health      - Health check")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock API")
        server.server_close()


if __name__ == "__main__":
    main()
