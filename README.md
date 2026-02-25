<<<<<<< HEAD
# OPC-UA-Nuchas
=======
# Nuchas OPC UA SPC Server

An OPC UA server that ingests JSON measurement data from an HTTP API, computes Statistical Process Control (SPC) statistics, and exposes the results as OPC UA variables for client connections.

## Features

- **JSON API ingestion** — Polls a configurable HTTP endpoint for measurement data. Supports multiple JSON formats (flat arrays, keyed objects, arrays of records).
- **SPC calculations** — X-bar/R control charts, control limits (UCL/LCL), process standard deviation, and process capability indices (Cp, Cpk).
- **OPC UA endpoint** — Publishes all SPC metrics as browsable OPC UA variables that any OPC UA client can connect to.
- **Out-of-control detection** — Flags subgroups that exceed control limits.
- **Configurable** — YAML config file with environment variable overrides.

## OPC UA Address Space

```
Objects/
└── SPC/
    ├── XBarChart/
    │   ├── GrandMean       (Double)
    │   ├── UCL             (Double)
    │   └── LCL             (Double)
    ├── RChart/
    │   ├── AverageRange    (Double)
    │   ├── UCL             (Double)
    │   └── LCL             (Double)
    ├── ProcessStats/
    │   ├── StdDev          (Double)
    │   ├── SampleCount     (Int64)
    │   └── SubgroupCount   (Int64)
    ├── Capability/
    │   ├── Cp              (Double)
    │   ├── Cpk             (Double)
    │   ├── Cpu             (Double)
    │   └── Cpl             (Double)
    ├── OutOfControl/
    │   ├── XBarOOCCount    (Int64)
    │   └── ROOCCount       (Int64)
    └── Configuration/
        ├── SubgroupSize    (Int64)
        ├── MaxSubgroups    (Int64)
        ├── SigmaMultiplier (Double)
        ├── APISourceURL    (String)
        └── PollIntervalSec (Double)
```

## Quick Start

### Install

```bash
pip install -r requirements.txt
```

### Configure

Edit `config.yaml` to set your API URL, polling interval, SPC parameters, and specification limits:

```yaml
server:
  endpoint: "opc.tcp://0.0.0.0:4840/nuchas/server"

api:
  url: "http://localhost:8080/api/data"
  poll_interval_seconds: 5

spc:
  subgroup_size: 5
  max_subgroups: 25
  upper_spec_limit: 15.0
  lower_spec_limit: 5.0
```

Or use environment variables:

```bash
export NUCHAS_API_URL="http://my-api:8080/measurements"
export NUCHAS_OPC_ENDPOINT="opc.tcp://0.0.0.0:4841/server"
export NUCHAS_POLL_INTERVAL=10
```

### Run

```bash
python -m src.server                 # uses config.yaml
python -m src.server /path/to/config.yaml  # custom config path
```

### Connect

Use any OPC UA client (e.g., UaExpert, Prosys OPC UA Browser) and connect to:

```
opc.tcp://localhost:4840/nuchas/server
```

Browse to `Objects → SPC` to see all SPC variables updating in real time.

## Supported JSON Formats

The API client accepts several common JSON response shapes:

| Format | Example |
|--------|---------|
| Flat array | `[1.2, 3.4, 5.6]` |
| Values key | `{"values": [1.2, 3.4, 5.6]}` |
| Array of objects | `[{"value": 1.2}, {"value": 3.4}]` |
| Measurements key | `{"measurements": [{"value": 1.2}]}` |

## Running Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
├── config.yaml           # Server configuration
├── requirements.txt      # Python dependencies
├── src/
│   ├── server.py         # OPC UA server + main entry point
│   ├── spc.py            # SPC statistical calculations
│   ├── api_client.py     # HTTP JSON API client
│   └── config.py         # Configuration loader
└── tests/
    ├── test_spc.py       # SPC calculation tests
    ├── test_api_client.py # JSON extraction tests
    └── test_config.py    # Config loading tests
```
>>>>>>> 9ba6d1cffda0a3c6fbe527b06e0ce6a864b29d8a
