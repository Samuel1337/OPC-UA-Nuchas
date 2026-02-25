"""Tests for the API client JSON extraction logic."""

import pytest
from src.api_client import APIClient


class TestExtractValues:
    def test_flat_array(self):
        data = [1.0, 2.5, 3.7, 4.1]
        assert APIClient._extract_values(data) == [1.0, 2.5, 3.7, 4.1]

    def test_values_key(self):
        data = {"values": [10, 20, 30]}
        assert APIClient._extract_values(data) == [10.0, 20.0, 30.0]

    def test_array_of_objects(self):
        data = [
            {"value": 1.1, "timestamp": "2024-01-01"},
            {"value": 2.2, "timestamp": "2024-01-02"},
            {"value": 3.3},
        ]
        assert APIClient._extract_values(data) == [1.1, 2.2, 3.3]

    def test_measurements_key(self):
        data = {
            "measurements": [
                {"value": 5.0, "id": 1},
                {"value": 6.0, "id": 2},
            ]
        }
        assert APIClient._extract_values(data) == [5.0, 6.0]

    def test_fallback_dict_with_numeric_list(self):
        data = {"readings": [100, 200, 300]}
        assert APIClient._extract_values(data) == [100.0, 200.0, 300.0]

    def test_empty_list(self):
        assert APIClient._extract_values([]) == []

    def test_empty_dict(self):
        assert APIClient._extract_values({}) == []

    def test_non_numeric_ignored_in_flat_array(self):
        data = [1.0, "bad", 3.0, None, 5.0]
        assert APIClient._extract_values(data) == [1.0, 3.0, 5.0]

    def test_mixed_int_float(self):
        data = [1, 2.5, 3, 4.0]
        result = APIClient._extract_values(data)
        assert result == [1.0, 2.5, 3.0, 4.0]
        assert all(isinstance(v, float) for v in result)

    def test_objects_missing_value_key_skipped(self):
        data = [
            {"value": 1.0},
            {"temperature": 25.0},
            {"value": 3.0},
        ]
        assert APIClient._extract_values(data) == [1.0, 3.0]

    def test_string_input_returns_empty(self):
        assert APIClient._extract_values("not json") == []

    def test_integer_input_returns_empty(self):
        assert APIClient._extract_values(42) == []
