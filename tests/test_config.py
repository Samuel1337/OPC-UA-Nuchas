"""Tests for configuration loading."""

import os
import tempfile
import pytest
import yaml
from src.config import load_config, AppConfig


class TestLoadConfig:
    def test_defaults_when_no_file(self):
        config = load_config("/nonexistent/path.yaml")
        assert config.server.endpoint == "opc.tcp://0.0.0.0:4840/nuchas/server"
        assert config.api.url == "http://localhost:8080/api/data"
        assert config.spc.subgroup_size == 5

    def test_load_from_yaml(self, tmp_path):
        cfg = {
            "server": {"endpoint": "opc.tcp://1.2.3.4:4840/test"},
            "api": {"url": "http://example.com/data", "poll_interval_seconds": 10},
            "spc": {"subgroup_size": 3, "upper_spec_limit": 100.0},
        }
        path = tmp_path / "test_config.yaml"
        path.write_text(yaml.dump(cfg))

        config = load_config(str(path))
        assert config.server.endpoint == "opc.tcp://1.2.3.4:4840/test"
        assert config.api.url == "http://example.com/data"
        assert config.api.poll_interval_seconds == 10
        assert config.spc.subgroup_size == 3
        assert config.spc.upper_spec_limit == 100.0
        # Defaults preserved for unspecified fields
        assert config.spc.lower_spec_limit is None

    def test_env_var_override(self, tmp_path, monkeypatch):
        cfg = {"api": {"url": "http://yaml-url.com/data"}}
        path = tmp_path / "test_config.yaml"
        path.write_text(yaml.dump(cfg))

        monkeypatch.setenv("NUCHAS_API_URL", "http://env-url.com/data")
        config = load_config(str(path))
        assert config.api.url == "http://env-url.com/data"

    def test_env_var_poll_interval(self, monkeypatch):
        monkeypatch.setenv("NUCHAS_POLL_INTERVAL", "30")
        config = load_config("/nonexistent/path.yaml")
        assert config.api.poll_interval_seconds == 30.0
