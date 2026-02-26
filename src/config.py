"""Configuration loader for the OPC UA SPC server."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ServerConfig:
    endpoint: str = "opc.tcp://0.0.0.0:4840/nuchas/server"
    name: str = "Nuchas OPC UA SPC Server"
    uri: str = "http://nuchas.opcua.spc.server"


@dataclass
class APIConfig:
    url: str = "http://localhost:8080/api/data"
    forms_url: str = "http://localhost:8080/api/forms"
    poll_interval_seconds: float = 5.0
    timeout_seconds: float = 10.0
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class SPCConfig:
    subgroup_size: int = 5
    max_subgroups: int = 25
    sigma_multiplier: float = 3.0
    upper_spec_limit: float | None = None
    lower_spec_limit: float | None = None


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    api: APIConfig = field(default_factory=APIConfig)
    spc: SPCConfig = field(default_factory=SPCConfig)


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load configuration from a YAML file.

    Falls back to environment variables, then defaults.
    """
    config = AppConfig()

    # Try loading from YAML
    if path is None:
        path = Path(os.environ.get("NUCHAS_CONFIG", "config.yaml"))
    else:
        path = Path(path)

    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        srv = raw.get("server", {})
        config.server.endpoint = srv.get("endpoint", config.server.endpoint)
        config.server.name = srv.get("name", config.server.name)
        config.server.uri = srv.get("uri", config.server.uri)

        api = raw.get("api", {})
        config.api.url = api.get("url", config.api.url)
        config.api.forms_url = api.get("forms_url", config.api.forms_url)
        config.api.poll_interval_seconds = api.get("poll_interval_seconds", config.api.poll_interval_seconds)
        config.api.timeout_seconds = api.get("timeout_seconds", config.api.timeout_seconds)
        config.api.headers = api.get("headers", config.api.headers) or {}

        spc = raw.get("spc", {})
        config.spc.subgroup_size = spc.get("subgroup_size", config.spc.subgroup_size)
        config.spc.max_subgroups = spc.get("max_subgroups", config.spc.max_subgroups)
        config.spc.sigma_multiplier = spc.get("sigma_multiplier", config.spc.sigma_multiplier)
        config.spc.upper_spec_limit = spc.get("upper_spec_limit", config.spc.upper_spec_limit)
        config.spc.lower_spec_limit = spc.get("lower_spec_limit", config.spc.lower_spec_limit)

    # Environment variable overrides
    if env_url := os.environ.get("NUCHAS_API_URL"):
        config.api.url = env_url
    if env_forms_url := os.environ.get("NUCHAS_FORMS_URL"):
        config.api.forms_url = env_forms_url
    if env_endpoint := os.environ.get("NUCHAS_OPC_ENDPOINT"):
        config.server.endpoint = env_endpoint
    if env_interval := os.environ.get("NUCHAS_POLL_INTERVAL"):
        config.api.poll_interval_seconds = float(env_interval)

    return config
