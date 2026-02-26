# Nuchas OPC UA SPC Server

An OPC UA server that ingests JSON data from an HTTP API, computes Statistical Process Control (SPC) statistics, serves HACCP quality check forms (CCP1/CCP3), and exposes everything as OPC UA variables for client connections. Includes a web frontend for manual form submission and real-time delivery monitoring.

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Setup and Installation](#setup-and-installation)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [OPC UA Server](#opc-ua-server)
- [Data Flow: End-to-End](#data-flow-end-to-end)
- [Configuration Reference](#configuration-reference)
- [Supported JSON Formats](#supported-json-formats)
- [Running Tests](#running-tests)
- [Deploying to AWS](#deploying-to-aws)
- [Project Structure](#project-structure)

## Features

- **Web frontend** — Browser-based form entry for CCP1/CCP3 quality checks with real-time OPC delivery monitoring.
- **JSON API ingestion** — Polls a configurable HTTP endpoint for measurement data. Supports multiple JSON formats (flat arrays, keyed objects, arrays of records).
- **SPC calculations** — X-bar/R control charts, control limits (UCL/LCL), process standard deviation, and process capability indices (Cp, Cpk).
- **HACCP quality forms** — CCP1 (cooking/kettle chilling) and CCP3 (baking/line chilling) stabilization monitoring forms with full field support (String, Int, Double, Boolean).
- **OPC UA endpoint** — Publishes all metrics and form data as browsable OPC UA variables that any OPC UA client can connect to.
- **Out-of-control detection** — Flags subgroups that exceed control limits.
- **Configurable** — YAML config file with environment variable overrides.

## Architecture Overview

The system has three components that communicate over HTTP and OPC UA:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Mock API Server (:8080)                         │
│                                                                         │
│  ┌──────────────┐    POST /api/forms     ┌───────────────────────────┐  │
│  │ Web Frontend │ ─────────────────────▶  │ Form Data Store           │  │
│  │ (Browser)    │                         │  _custom_forms (dict)     │  │
│  │  GET /       │ ◀───────────────────── │  _submission_log (list)   │  │
│  └──────────────┘    GET /api/status      └───────────┬───────────────┘  │
│                                                       │                  │
└───────────────────────────────────────────────────────┼──────────────────┘
                                                        │
                                              GET /api/forms (every 5s)
                                                        │
                                                        ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       OPC UA Server (:4840)                              │
│                                                                         │
│  ┌──────────────┐    ┌────────────────┐    ┌─────────────────────────┐  │
│  │  API Client  │───▶│ SPC Calculator │───▶│  OPC UA Address Space   │  │
│  │  (aiohttp)   │    │  (X̄, R, Cp…)  │    │  Variable Nodes         │  │
│  └──────────────┘    └────────────────┘    └─────────────────────────┘  │
│                                                        │                 │
└────────────────────────────────────────────────────────┼─────────────────┘
                                                         │
                                              opc.tcp:// connections
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │  OPC UA Clients      │
                                              │  (UaExpert, SCADA…)  │
                                              └──────────────────────┘
```

## Setup and Installation

### Prerequisites

- Python 3.11 or newer
- pip (Python package manager)
- Git

### Step 1 — Clone the repository

```bash
git clone https://github.com/Samuel1337/OPC-UA-Nuchas.git
cd OPC-UA-Nuchas
```

### Step 2 — Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---------|---------|
| `asyncua>=1.0.6` | OPC UA server library |
| `aiohttp>=3.9.0` | Async HTTP client for API polling |
| `pyyaml>=6.0` | YAML configuration parsing |
| `numpy>=1.24.0` | Numerical support |
| `pytest>=7.0` | Test framework |
| `pytest-asyncio>=0.21.0` | Async test support |

### Step 4 — Configure (optional)

The default `config.yaml` works out of the box with the mock API. Edit it only if you need to change ports, polling intervals, or point at a real data source.

## Running the Application

You need two terminals (or background processes): one for the mock API, one for the OPC UA server.

### Terminal 1 — Start the Mock API

```bash
source .venv/bin/activate
python -m src.mock_api
```

Output:

```
Mock API serving at http://0.0.0.0:8080
  GET  /            - Web frontend
  GET  /api/forms   - CCP1 & CCP3 quality check forms
  POST /api/forms   - Submit custom form data
  GET  /api/status  - Submission log + OPC poll status
  GET  /health      - Health check
```

To use a custom port:

```bash
python -m src.mock_api --port 9090
```

### Terminal 2 — Start the OPC UA Server

```bash
source .venv/bin/activate
python -m src.server
```

To use a custom config file:

```bash
python -m src.server /path/to/custom-config.yaml
```

### Open the Web Frontend

Navigate to `http://localhost:8080` in your browser to access the form submission and monitoring interface.

### Connect an OPC UA Client

Use any OPC UA client (UaExpert, Prosys OPC UA Browser, etc.) and connect to:

```
opc.tcp://localhost:4840/nuchas/server
```

Browse to `Objects > SPC` for SPC data or `Objects > QualityForms > CCP1/CCP3` for quality check forms.

## API Endpoints

The mock API server exposes the following HTTP endpoints:

### `GET /` — Web Frontend

Serves the HTML/CSS/JS single-page application for form entry and monitoring.

### `GET /api/forms` — Quality Check Form Data

Returns the current CCP1 and CCP3 quality check form data as JSON. This is the endpoint the OPC UA server polls every 5 seconds.

**Behavior:**
- If the user has submitted custom data via `POST /api/forms`, it returns that data for the submitted form types.
- For form types without custom submissions, it returns auto-generated simulated data with realistic temperature cooling curves.
- Every time this endpoint is called, it records a poll timestamp and marks all pending submissions as "received".

**Response (200):**

```json
{
  "ccp1": {
    "header": {
      "quality_check_id": "QC-213091",
      "form_name": "Empanada (USDA/FDA) HACCP Record ...",
      "authenticated_by": "Alejandro Anzoategui (aanzo)",
      "auth_time": "Feb-26-2026 03:15 PM",
      "triggered_by": "CCP1B Pass = CCP2B",
      "trigger_time": "Feb-26-2026 01:15 PM",
      "assigned_to": "Chilling CCP1&2 Cooking, Alejandro Anzoategui",
      "signed_off_by": "Sandra Echeverry (secheverry)",
      "sign_off_time": "Feb-26-2026 03:15 PM",
      "location": "Kettle 1",
      "product": "Ground Beef Empanadas RTE 24/3oz",
      "sku": "120001-C",
      "run_id": "25174-001 USDA",
      "custom_reference": "1",
      "run_start_date": "Feb-26-2026 12:15 PM",
      "run_end_date": "Feb-26-2026 01:15 PM",
      "run_sign_off_time": "Feb-26-2026 03:15 PM",
      "run_sign_off_by": "Sandra Echeverry (secheverry)"
    },
    "critical_limits_text": "All meat or poultry fillings must be chilled ...",
    "start_chilling": {
      "batch_number": 1,
      "temperature": 158.3,
      "time": "Feb-26-2026 01:15 PM",
      "passed": true
    },
    "chilling_process_1": {
      "batch_number": 1,
      "temperature": 72.4,
      "time": "Feb-26-2026 02:45 PM",
      "passed": true
    },
    "chilling_process_2": {
      "batch_number": 1,
      "temperature": 38.1,
      "time": "Feb-26-2026 03:15 PM",
      "passed": true
    },
    "direct_observation": {
      "verified_by": "Sandra Echeverry",
      "time": "Feb-26-2026 03:15 PM",
      "results": "Acceptable Monitoring Procedures"
    }
  },
  "ccp3": {
    "header": { "..." : "..." },
    "critical_limits_text": "...",
    "baking_start_chilling": {
      "batch_number": 1,
      "rack_number": 1,
      "temperature": 138.2,
      "date_time": "Feb-26-2026 01:45 PM",
      "passed": true
    },
    "baking_chilling_1": {
      "temperature": 65.3,
      "usl": 80.0,
      "date_time": "Feb-26-2026 03:10 PM",
      "passed": true
    },
    "baking_chilling_2": {
      "temperature": 0.0,
      "date_time": "",
      "passed": false
    },
    "direct_observation": {
      "verified_by": "Sandra Echeverry",
      "time": "Feb-26-2026 03:15 PM",
      "results": "Acceptable Monitoring Procedures",
      "comments": ""
    },
    "linked_items": [
      "Quality Check - Empanada (USDA/FDA) HACCP Record (CCP 3B) ...",
      "Action Review - Baking Line Empanada ..."
    ]
  }
}
```

### `POST /api/forms` — Submit Custom Form Data

Accepts a JSON body containing one or more form types. The submitted data replaces the auto-generated data for those form types on subsequent `GET /api/forms` calls.

**Request body:**

```json
{
  "ccp1": {
    "header": { "product": "Custom Empanadas", "sku": "999-X", "..." : "..." },
    "start_chilling": { "batch_number": 5, "temperature": 162.0, "time": "...", "passed": true },
    "..."
  }
}
```

**Response (200):**

```json
{
  "status": "accepted",
  "message": "Form data stored for: ccp1. OPC server will pick it up on next poll."
}
```

**Error responses:**

| Status | Body | Cause |
|--------|------|-------|
| 400 | `{"error": "empty body"}` | No request body |
| 400 | `{"error": "invalid JSON: ..."}` | Malformed JSON |
| 400 | `{"error": "expected a JSON object with form type keys"}` | Body is not a dict or is empty |

### `GET /api/status` — Submission Monitor

Returns the full submission log with delivery status for each entry. The web frontend polls this every 2 seconds.

**Response (200):**

```json
{
  "last_opc_poll_at": "Feb-26-2026 03:15:42 PM",
  "total_submissions": 3,
  "submissions": [
    {
      "id": 1,
      "form_type": "ccp1",
      "submitted_at": "Feb-26-2026 03:14:30 PM",
      "data": { "ccp1": { "..." : "..." } },
      "received": true,
      "received_at": "Feb-26-2026 03:14:35 PM"
    },
    {
      "id": 2,
      "form_type": "ccp3",
      "submitted_at": "Feb-26-2026 03:15:00 PM",
      "data": { "ccp3": { "..." : "..." } },
      "received": true,
      "received_at": "Feb-26-2026 03:15:05 PM"
    },
    {
      "id": 3,
      "form_type": "ccp1",
      "submitted_at": "Feb-26-2026 03:15:40 PM",
      "data": { "ccp1": { "..." : "..." } },
      "received": false,
      "received_at": null
    }
  ]
}
```

### `GET /health` — Health Check

**Response (200):**

```json
{ "status": "ok" }
```

## OPC UA Server

### Server Configuration

| Parameter | Default | Env Override |
|-----------|---------|-------------|
| Endpoint | `opc.tcp://0.0.0.0:4840/nuchas/server` | `NUCHAS_OPC_ENDPOINT` |
| Server name | `Nuchas OPC UA SPC Server` | — |
| Namespace URI | `http://nuchas.opcua.spc.server` | — |
| API data URL | `http://localhost:8080/api/data` | `NUCHAS_API_URL` |
| API forms URL | `http://localhost:8080/api/forms` | `NUCHAS_FORMS_URL` |
| Poll interval | 5 seconds | `NUCHAS_POLL_INTERVAL` |
| Request timeout | 10 seconds | — |

### OPC UA Address Space

All data is published as individually-addressable OPC UA variable nodes organized in folders:

```
Objects/
├── SPC/
│   ├── XBarChart/
│   │   ├── GrandMean       (Double)   — X̄ grand mean
│   │   ├── UCL             (Double)   — Upper Control Limit
│   │   └── LCL             (Double)   — Lower Control Limit
│   ├── RChart/
│   │   ├── AverageRange    (Double)   — R̄ average range
│   │   ├── UCL             (Double)
│   │   └── LCL             (Double)
│   ├── ProcessStats/
│   │   ├── StdDev          (Double)   — Estimated sigma (σ)
│   │   ├── SampleCount     (Int64)    — Total measurements
│   │   └── SubgroupCount   (Int64)    — Complete subgroups
│   ├── Capability/
│   │   ├── Cp              (Double)   — Process capability
│   │   ├── Cpk             (Double)   — Adjusted capability
│   │   ├── Cpu             (Double)   — Upper capability
│   │   └── Cpl             (Double)   — Lower capability
│   ├── OutOfControl/
│   │   ├── XBarOOCCount    (Int64)    — X̄ out-of-control count
│   │   └── ROOCCount       (Int64)    — R out-of-control count
│   └── Configuration/
│       ├── SubgroupSize    (Int64)
│       ├── MaxSubgroups    (Int64)
│       ├── SigmaMultiplier (Double)
│       ├── APISourceURL    (String)
│       └── PollIntervalSec (Double)
└── QualityForms/
    ├── CCP1/                              — Cooking/Kettle chilling
    │   ├── Header/
    │   │   ├── QualityCheckID    (String)
    │   │   ├── FormName          (String)
    │   │   ├── AuthenticatedBy   (String)
    │   │   ├── AuthTime          (String)
    │   │   ├── TriggeredBy       (String)
    │   │   ├── TriggerTime       (String)
    │   │   ├── AssignedTo        (String)
    │   │   ├── SignedOffBy       (String)
    │   │   ├── SignOffTime       (String)
    │   │   ├── Location          (String)
    │   │   ├── Product           (String)
    │   │   ├── SKU               (String)
    │   │   ├── RunID             (String)
    │   │   ├── CustomReference   (String)
    │   │   ├── RunStartDate      (String)
    │   │   ├── RunEndDate        (String)
    │   │   ├── RunSignOffTime    (String)
    │   │   └── RunSignOffBy      (String)
    │   ├── CriticalLimitsText    (String)
    │   ├── StartChilling/
    │   │   ├── BatchNumber       (Int64)
    │   │   ├── Temperature       (Double)
    │   │   ├── Time              (String)
    │   │   └── Pass              (Boolean)
    │   ├── ChillingProcess1/
    │   │   ├── BatchNumber       (Int64)
    │   │   ├── Temperature       (Double)
    │   │   ├── Time              (String)
    │   │   └── Pass              (Boolean)
    │   ├── ChillingProcess2/
    │   │   ├── BatchNumber       (Int64)
    │   │   ├── Temperature       (Double)
    │   │   ├── Time              (String)
    │   │   └── Pass              (Boolean)
    │   └── DirectObservation/
    │       ├── VerifiedBy        (String)
    │       ├── Time              (String)
    │       └── Results           (String)
    └── CCP3/                              — Baking/Line chilling
        ├── Header/                        (same 18 fields as CCP1)
        ├── CriticalLimitsText    (String)
        ├── BakingStartChilling/
        │   ├── BatchNumber       (Int64)
        │   ├── RackNumber        (Int64)
        │   ├── Temperature       (Double)
        │   ├── DateTime          (String)
        │   └── Pass              (Boolean)
        ├── BakingChilling1/
        │   ├── Temperature       (Double)
        │   ├── USL               (Double)
        │   ├── DateTime          (String)
        │   └── Pass              (Boolean)
        ├── BakingChilling2/
        │   ├── Temperature       (Double)
        │   ├── DateTime          (String)
        │   └── Pass              (Boolean)
        ├── DirectObservation/
        │   ├── VerifiedBy        (String)
        │   ├── Time              (String)
        │   ├── Results           (String)
        │   └── Comments          (String)
        └── LinkedItems           (String)  — Semicolon-delimited list
```

### OPC UA Type Mapping

When JSON values arrive from the API, the server automatically detects and assigns OPC UA data types:

| Python / JSON Type | OPC UA VariantType | Example |
|--------------------|--------------------|---------|
| `true` / `false` | `Boolean` | `passed: true` |
| Integer (`1`, `42`) | `Int64` | `batch_number: 1` |
| Float (`158.0`, `53.2`) | `Double` | `temperature: 158.0` |
| String (`"Kettle 1"`) | `String` | `location: "Kettle 1"` |
| Array (`["a", "b"]`) | `String` (joined with `; `) | `linked_items: ["a", "b"]` |

Once a node is created with a type, all subsequent updates are coerced to that same type for consistency.

## Data Flow: End-to-End

This section describes the complete lifecycle of a data point, from form entry in the browser to OPC UA node storage and acknowledgment.

### Step 1 — User Fills the Form

The user opens `http://localhost:8080` in a browser. The mock API serves the HTML frontend (`src/static/index.html`), which displays CCP1 and CCP3 form tabs with pre-filled default values. The user edits the fields (temperatures, batch numbers, pass/fail checkboxes, etc.) and clicks **"Send CCP1 to OPC Server"**.

### Step 2 — Frontend Builds the JSON Object

The browser JavaScript collects all form input values and constructs a JSON object matching the expected schema. For example, after the user edits the CCP1 start chilling temperature to 162.5:

```json
{
  "ccp1": {
    "header": {
      "quality_check_id": "QC-213091",
      "form_name": "Empanada (USDA/FDA) HACCP Record (CCP 2B) FSQ-2.4.3.12-CCP-2B",
      "product": "Ground Beef Empanadas RTE 24/3oz",
      "sku": "120001-C",
      "location": "Kettle 1",
      "...": "..."
    },
    "critical_limits_text": "All meat or poultry fillings must be chilled ...",
    "start_chilling": {
      "batch_number": 1,
      "temperature": 162.5,
      "time": "Feb-26-2026 01:15 PM",
      "passed": true
    },
    "chilling_process_1": { "..." : "..." },
    "chilling_process_2": { "..." : "..." },
    "direct_observation": { "..." : "..." }
  }
}
```

### Step 3 — Frontend POSTs to the Mock API

The browser sends:

```
POST /api/forms HTTP/1.1
Content-Type: application/json

{ "ccp1": { ... } }
```

The mock API's `_handle_form_submission()` method:

1. Parses the JSON body.
2. Stores the form data in the `_custom_forms` dictionary, keyed by form type (`"ccp1"`).
3. Appends an entry to the `_submission_log` with a unique ID, timestamp, the full payload, and `received: false`.
4. Returns `200 {"status": "accepted", "message": "..."}`.

At this point the data is stored inside the mock API, waiting to be picked up. The submission appears in the monitoring panel as **"Pending"** (yellow badge).

### Step 4 — OPC UA Server Polls `GET /api/forms`

The OPC UA server runs an async polling loop (`_poll_loop()` in `src/server.py`) that calls `GET /api/forms` every 5 seconds (configurable via `poll_interval_seconds`).

When the mock API receives this GET request, `_serve_forms()`:

1. Records the current timestamp as `_last_opc_poll_at`.
2. Iterates `_submission_log` and marks every entry where `received == false` as `received = true`, recording the poll timestamp in `received_at`.
3. Builds the response by starting with auto-generated data, then overlaying any `_custom_forms` entries (user-submitted data takes priority).
4. Returns the merged JSON.

**This is the acknowledgment mechanism** — the act of the OPC server polling `GET /api/forms` is what flips each submission's status from "Pending" to "Received by OPC".

### Step 5 — OPC UA Server Parses the JSON and Creates/Updates Nodes

The OPC UA server's `_fetch_forms()` method receives the JSON response and processes each form type:

```
For each form_type (e.g., "ccp1") in the response:
  │
  ├─ First encounter? → Create a new folder under QualityForms/
  │                      e.g., Objects/QualityForms/CCP1/
  │
  └─ Call create_or_update_form_nodes() recursively:
       │
       For each key-value pair in the form data:
       │
       ├─ Value is a dict? (nested section like "header", "start_chilling")
       │   ├─ Folder doesn't exist? → Create OPC UA folder node
       │   └─ Recurse into the dict
       │
       └─ Value is a leaf? (string, number, bool, list)
           ├─ Node exists? → Coerce value to the node's established type
           │                  and call node.write_value()
           └─ New node? → Detect type with _detect_variant()
                           → Create OPC UA variable node
                           → Store in registry (nodes, node_types)
```

For example, when `"start_chilling": {"temperature": 162.5}` arrives:

1. The server looks up the existing node at `QualityForms/CCP1/StartChilling/Temperature`.
2. The node was created as `VariantType.Double` on first encounter.
3. The value `162.5` is coerced to `float` and written via `node.write_value(162.5)`.
4. The OPC UA library stores this value in its internal address space.
5. Any connected OPC UA client reading this node now sees `162.5`.

### Step 6 — Frontend Detects the Acknowledgment

The browser JavaScript polls `GET /api/status` every 2 seconds. When the response shows a submission's `received` field has changed from `false` to `true`, the monitoring panel updates that entry's badge from **"Pending"** (yellow) to **"Received by OPC"** (green), and displays the `received_at` timestamp.

### Complete Sequence Diagram

```
 Browser                    Mock API (:8080)              OPC UA Server (:4840)       OPC UA Client
    │                           │                                │                        │
    │  POST /api/forms          │                                │                        │
    │  {"ccp1": {...}}          │                                │                        │
    │ ─────────────────────────▶│                                │                        │
    │                           │ Store in _custom_forms         │                        │
    │                           │ Append to _submission_log      │                        │
    │                           │   (received: false)            │                        │
    │  200 {"status":"accepted"}│                                │                        │
    │ ◀─────────────────────────│                                │                        │
    │                           │                                │                        │
    │  GET /api/status          │                                │                        │
    │ ─────────────────────────▶│                                │                        │
    │  [submission #1: pending] │                                │                        │
    │ ◀─────────────────────────│                                │                        │
    │                           │                                │                        │
    │  Shows "Pending" badge    │       GET /api/forms           │                        │
    │                           │ ◀──────────────────────────────│  (poll every 5s)       │
    │                           │ Mark submissions received=true │                        │
    │                           │ Return merged JSON             │                        │
    │                           │ ──────────────────────────────▶│                        │
    │                           │                                │                        │
    │                           │                                │ Parse JSON             │
    │                           │                                │ Create/update nodes    │
    │                           │                                │ Temperature = 162.5    │
    │                           │                                │                        │
    │  GET /api/status          │                                │   Browse/Read nodes    │
    │ ─────────────────────────▶│                                │ ◀──────────────────────│
    │  [submission #1: received]│                                │ Return 162.5           │
    │ ◀─────────────────────────│                                │ ──────────────────────▶│
    │                           │                                │                        │
    │  Shows "Received by OPC"  │                                │                        │
    │  badge (green)            │                                │                        │
```

## Configuration Reference

Edit `config.yaml` to customize all parameters:

```yaml
server:
  endpoint: "opc.tcp://0.0.0.0:4840/nuchas/server"
  name: "Nuchas OPC UA SPC Server"
  uri: "http://nuchas.opcua.spc.server"

api:
  url: "http://localhost:8080/api/data"
  forms_url: "http://localhost:8080/api/forms"
  poll_interval_seconds: 5
  timeout_seconds: 10
  headers: {}

spc:
  subgroup_size: 5
  max_subgroups: 25
  sigma_multiplier: 3.0
  upper_spec_limit: null    # Set to enable Cp/Cpk calculations
  lower_spec_limit: null
```

Environment variable overrides:

| Variable | Overrides | Example |
|----------|-----------|---------|
| `NUCHAS_API_URL` | `api.url` | `http://my-api:8080/measurements` |
| `NUCHAS_FORMS_URL` | `api.forms_url` | `http://my-api:8080/api/forms` |
| `NUCHAS_OPC_ENDPOINT` | `server.endpoint` | `opc.tcp://0.0.0.0:4841/server` |
| `NUCHAS_POLL_INTERVAL` | `api.poll_interval_seconds` | `10` |

## Supported JSON Formats

The measurement data API client accepts several common JSON response shapes:

| Format | Example |
|--------|---------|
| Flat array | `[1.2, 3.4, 5.6]` |
| Values key | `{"values": [1.2, 3.4, 5.6]}` |
| Array of objects | `[{"value": 1.2}, {"value": 3.4}]` |
| Measurements key | `{"measurements": [{"value": 1.2}]}` |

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

The test suite covers:
- SPC calculations (control limits, capability indices, out-of-control detection)
- JSON extraction across all supported formats
- YAML config loading and environment variable overrides
- CCP1/CCP3 form parsing and OPC UA node creation/update

## Deploying to AWS

### Option A — EC2 Instance (Simplest)

This is the most straightforward approach. You run both servers directly on an EC2 instance.

#### 1. Launch an EC2 instance

- AMI: **Amazon Linux 2023** or **Ubuntu 24.04 LTS**
- Instance type: **t3.micro** (sufficient for testing) or **t3.small** for production
- Security group inbound rules:
  - TCP **4840** (OPC UA) — from your OPC UA clients' IPs
  - TCP **8080** (Mock API / Web Frontend) — from your browser's IP
  - TCP **22** (SSH) — from your IP

#### 2. SSH in and install dependencies

```bash
ssh -i your-key.pem ec2-user@<ec2-public-ip>

# Amazon Linux 2023
sudo dnf install python3.11 python3.11-pip git -y

# Ubuntu 24.04
# sudo apt update && sudo apt install python3.11 python3.11-venv git -y
```

#### 3. Clone and set up

```bash
git clone https://github.com/Samuel1337/OPC-UA-Nuchas.git
cd OPC-UA-Nuchas
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 4. Configure for the EC2 environment

Update `config.yaml` or use environment variables to bind to the correct addresses:

```bash
# The OPC UA server should bind to 0.0.0.0 to accept external connections
export NUCHAS_OPC_ENDPOINT="opc.tcp://0.0.0.0:4840/nuchas/server"
```

#### 5. Run as background services with systemd

Create systemd service files so both servers start on boot and restart on failure.

**Mock API service** — `/etc/systemd/system/nuchas-api.service`:

```ini
[Unit]
Description=Nuchas Mock API Server
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/OPC-UA-Nuchas
ExecStart=/home/ec2-user/OPC-UA-Nuchas/.venv/bin/python -m src.mock_api
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**OPC UA server service** — `/etc/systemd/system/nuchas-opcua.service`:

```ini
[Unit]
Description=Nuchas OPC UA SPC Server
After=network.target nuchas-api.service

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/OPC-UA-Nuchas
Environment=NUCHAS_OPC_ENDPOINT=opc.tcp://0.0.0.0:4840/nuchas/server
ExecStart=/home/ec2-user/OPC-UA-Nuchas/.venv/bin/python -m src.server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nuchas-api nuchas-opcua
sudo systemctl start nuchas-api nuchas-opcua
```

Check status:

```bash
sudo systemctl status nuchas-api
sudo systemctl status nuchas-opcua
sudo journalctl -u nuchas-opcua -f   # live logs
```

#### 6. Connect

- **Web frontend:** `http://<ec2-public-ip>:8080`
- **OPC UA clients:** `opc.tcp://<ec2-public-ip>:4840/nuchas/server`

### Option B — Docker on ECS (Production)

For a containerized deployment on AWS Elastic Container Service.

#### 1. Create a Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 4840 8080
```

#### 2. Create a docker-compose.yml for local testing

```yaml
services:
  mock-api:
    build: .
    command: python -m src.mock_api
    ports:
      - "8080:8080"

  opcua-server:
    build: .
    command: python -m src.server
    ports:
      - "4840:4840"
    environment:
      - NUCHAS_FORMS_URL=http://mock-api:8080/api/forms
      - NUCHAS_API_URL=http://mock-api:8080/api/data
    depends_on:
      - mock-api
```

Test locally:

```bash
docker compose up --build
```

#### 3. Push to Amazon ECR

```bash
aws ecr create-repository --repository-name nuchas-opcua
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

docker build -t nuchas-opcua .
docker tag nuchas-opcua:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/nuchas-opcua:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/nuchas-opcua:latest
```

#### 4. Deploy to ECS

- Create an **ECS Cluster** (Fargate or EC2 launch type).
- Create a **Task Definition** with two containers (mock-api and opcua-server) using the ECR image, mapping ports 8080 and 4840.
- Create an **ECS Service** that runs the task definition.
- Attach a **Security Group** allowing inbound TCP 4840 and 8080.
- For the web frontend, optionally place an **Application Load Balancer** in front of port 8080.

Note: OPC UA uses a raw TCP binary protocol on port 4840 — it cannot go through an ALB (HTTP-only). Use a **Network Load Balancer (NLB)** if you need load balancing for OPC UA connections.

## Project Structure

```
├── config.yaml              # Server configuration
├── requirements.txt         # Python dependencies
├── src/
│   ├── server.py            # OPC UA server + main entry point
│   ├── spc.py               # SPC statistical calculations
│   ├── api_client.py        # HTTP JSON API client
│   ├── config.py            # Configuration loader
│   ├── quality_forms.py     # CCP1/CCP3 form definitions + OPC UA nodes
│   ├── mock_api.py          # Mock data API + web frontend server
│   └── static/
│       └── index.html       # Web frontend (form entry + monitoring)
└── tests/
    ├── test_spc.py          # SPC calculation tests
    ├── test_api_client.py   # JSON extraction tests
    ├── test_config.py       # Config loading tests
    └── test_quality_forms.py # CCP1/CCP3 parsing + node tests
```
