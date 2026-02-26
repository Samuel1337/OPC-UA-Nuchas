"""Tests for quality form JSON parsing and dynamic node helpers."""

import pytest
import pytest_asyncio

from asyncua import ua

from src.quality_forms import (
    _coerce_to_variant,
    _detect_variant,
    _snake_to_display,
    parse_ccp1_json,
    parse_ccp3_json,
    CCP1Form,
    CCP3Form,
    FormNodeRegistry,
    create_or_update_form_nodes,
)


# ── Helper unit tests ────────────────────────────────────────────

class TestSnakeToDisplay:
    def test_single_word(self):
        assert _snake_to_display("temperature") == "Temperature"

    def test_multi_word(self):
        assert _snake_to_display("batch_number") == "BatchNumber"

    def test_abbreviation_id(self):
        assert _snake_to_display("quality_check_id") == "QualityCheckID"

    def test_abbreviation_sku(self):
        assert _snake_to_display("sku") == "SKU"

    def test_abbreviation_usl(self):
        assert _snake_to_display("usl") == "USL"


class TestDetectVariant:
    def test_bool_true(self):
        vtype, val = _detect_variant(True)
        assert vtype == ua.VariantType.Boolean
        assert val is True

    def test_bool_false(self):
        vtype, val = _detect_variant(False)
        assert vtype == ua.VariantType.Boolean
        assert val is False

    def test_int(self):
        vtype, val = _detect_variant(42)
        assert vtype == ua.VariantType.Int64
        assert val == 42

    def test_float(self):
        vtype, val = _detect_variant(3.14)
        assert vtype == ua.VariantType.Double
        assert val == 3.14

    def test_string(self):
        vtype, val = _detect_variant("hello")
        assert vtype == ua.VariantType.String
        assert val == "hello"

    def test_list(self):
        vtype, val = _detect_variant(["a", "b", "c"])
        assert vtype == ua.VariantType.String
        assert val == "a; b; c"

    def test_none(self):
        vtype, val = _detect_variant(None)
        assert vtype == ua.VariantType.String
        assert val == ""

    def test_bool_before_int(self):
        """bool is subclass of int — make sure True maps to Boolean, not Int64."""
        vtype, _ = _detect_variant(True)
        assert vtype == ua.VariantType.Boolean


class TestCoerceToVariant:
    def test_coerce_bool(self):
        assert _coerce_to_variant(1, ua.VariantType.Boolean) is True
        assert _coerce_to_variant(0, ua.VariantType.Boolean) is False

    def test_coerce_int(self):
        assert _coerce_to_variant(3.7, ua.VariantType.Int64) == 3
        assert _coerce_to_variant(None, ua.VariantType.Int64) == 0

    def test_coerce_double(self):
        assert _coerce_to_variant(5, ua.VariantType.Double) == 5.0
        assert _coerce_to_variant(None, ua.VariantType.Double) == 0.0

    def test_coerce_string(self):
        assert _coerce_to_variant(42, ua.VariantType.String) == "42"
        assert _coerce_to_variant(None, ua.VariantType.String) == ""

    def test_coerce_list_to_string(self):
        assert _coerce_to_variant(["x", "y"], ua.VariantType.String) == "x; y"


# ── CCP1 dataclass parser tests ──────────────────────────────────

SAMPLE_CCP1 = {
    "header": {
        "quality_check_id": "QC-213091",
        "form_name": "Empanada (USDA/FDA) HACCP Record (CCP 2B)",
        "authenticated_by": "Alejandro Anzoategui (aanzo)",
        "auth_time": "Jun-23-2025 11:12 AM",
        "triggered_by": "CCP1B Pass = CCP2B",
        "trigger_time": "Jun-23-2025 8:54 AM",
        "assigned_to": "Chilling CCP1&2 Cooking",
        "signed_off_by": "Sandra Echeverry (secheverry)",
        "sign_off_time": "Jun-23-2025 12:08 PM",
        "location": "Kettle 1",
        "product": "Ground Beef Empanadas RTE 24/3oz",
        "sku": "120001-C",
        "run_id": "25174-001 USDA",
        "custom_reference": "1",
        "run_start_date": "Jun-23-2025 8:06 AM",
        "run_end_date": "Jun-23-2025 9:07 AM",
        "run_sign_off_time": "Jun-23-2025 12:08 PM",
        "run_sign_off_by": "Sandra Echeverry (secheverry)",
    },
    "critical_limits_text": "All meat or poultry fillings must be chilled...",
    "start_chilling": {
        "batch_number": 1,
        "temperature": 158.0,
        "time": "Jun-23-2025 9:09 AM",
        "passed": True,
    },
    "chilling_process_1": {
        "batch_number": 1,
        "temperature": 53.0,
        "time": "Jun-23-2025 10:38 AM",
        "passed": True,
    },
    "chilling_process_2": {
        "batch_number": 1,
        "temperature": 38.0,
        "time": "Jun-23-2025 11:12 AM",
        "passed": True,
    },
    "direct_observation": {
        "verified_by": "Sandra Echeverry",
        "time": "Jun-23-2025 12:08 PM",
        "results": "Acceptable Monitoring Procedures",
    },
}

SAMPLE_CCP3 = {
    "header": {
        "quality_check_id": "QC-213092",
        "form_name": "Empanada (USDA/FDA) HACCP Record (CCP 4B)",
        "authenticated_by": "Camilo Triana (ctriana)",
        "auth_time": "Jun-17-2025 10:44 AM",
        "location": "Baking Line",
        "product": "Italian Sausage Empanadas RTE 24/3oz",
        "sku": "122003-B",
        "run_id": "25167-002 (1-1)",
    },
    "critical_limits_text": "All meat or poultry fillings must be chilled...",
    "baking_start_chilling": {
        "batch_number": 1,
        "rack_number": 1,
        "temperature": 138.0,
        "date_time": "Jun-17-2025 9:15 AM",
        "passed": True,
    },
    "baking_chilling_1": {
        "temperature": 26.0,
        "usl": 80.0,
        "date_time": "Jun-17-2025 10:43 AM",
        "passed": True,
    },
    "baking_chilling_2": {
        "temperature": 0.0,
        "date_time": "",
        "passed": False,
    },
    "direct_observation": {
        "verified_by": "Sandra Echeverry",
        "time": "Jun-17-2025 10:43 AM",
        "results": "Acceptable Monitoring Procedures",
        "comments": "All OK",
    },
    "linked_items": [
        "Quality Check - CCP 3B - Pass",
        "Action Review - CCP 4B Review",
    ],
}


class TestParseCCP1:
    def test_header_fields(self):
        form = parse_ccp1_json(SAMPLE_CCP1)
        assert form.header.quality_check_id == "QC-213091"
        assert form.header.location == "Kettle 1"
        assert form.header.product == "Ground Beef Empanadas RTE 24/3oz"
        assert form.header.sku == "120001-C"
        assert form.header.run_id == "25174-001 USDA"
        assert form.header.signed_off_by == "Sandra Echeverry (secheverry)"

    def test_start_chilling(self):
        form = parse_ccp1_json(SAMPLE_CCP1)
        assert form.start_chilling.batch_number == 1
        assert form.start_chilling.temperature == 158.0
        assert form.start_chilling.passed is True

    def test_chilling_process_1(self):
        form = parse_ccp1_json(SAMPLE_CCP1)
        assert form.chilling_process_1.temperature == 53.0
        assert form.chilling_process_1.passed is True

    def test_chilling_process_2(self):
        form = parse_ccp1_json(SAMPLE_CCP1)
        assert form.chilling_process_2.temperature == 38.0
        assert form.chilling_process_2.passed is True

    def test_direct_observation(self):
        form = parse_ccp1_json(SAMPLE_CCP1)
        assert form.direct_observation.verified_by == "Sandra Echeverry"
        assert form.direct_observation.results == "Acceptable Monitoring Procedures"

    def test_critical_limits_text(self):
        form = parse_ccp1_json(SAMPLE_CCP1)
        assert "chilled" in form.critical_limits_text

    def test_empty_input(self):
        form = parse_ccp1_json({})
        assert form.header.quality_check_id == ""
        assert form.start_chilling.temperature == 0.0

    def test_partial_sections(self):
        """Only start_chilling present — other sections stay at defaults."""
        data = {
            "start_chilling": {"temperature": 160.0, "passed": True},
        }
        form = parse_ccp1_json(data)
        assert form.start_chilling.temperature == 160.0
        assert form.chilling_process_1.temperature == 0.0
        assert form.chilling_process_2.temperature == 0.0

    def test_extra_header_fields_ignored(self):
        """Unknown header keys should not raise."""
        data = {
            "header": {"quality_check_id": "QC-999", "unknown_field": "ignored"},
        }
        form = parse_ccp1_json(data)
        assert form.header.quality_check_id == "QC-999"


class TestParseCCP3:
    def test_header_fields(self):
        form = parse_ccp3_json(SAMPLE_CCP3)
        assert form.header.quality_check_id == "QC-213092"
        assert form.header.location == "Baking Line"
        assert form.header.product == "Italian Sausage Empanadas RTE 24/3oz"
        assert form.header.sku == "122003-B"

    def test_baking_start_chilling(self):
        form = parse_ccp3_json(SAMPLE_CCP3)
        assert form.baking_start_chilling.batch_number == 1
        assert form.baking_start_chilling.rack_number == 1
        assert form.baking_start_chilling.temperature == 138.0
        assert form.baking_start_chilling.passed is True

    def test_baking_chilling_1_with_usl(self):
        form = parse_ccp3_json(SAMPLE_CCP3)
        assert form.baking_chilling_1.temperature == 26.0
        assert form.baking_chilling_1.usl == 80.0
        assert form.baking_chilling_1.passed is True

    def test_baking_chilling_2_incomplete(self):
        form = parse_ccp3_json(SAMPLE_CCP3)
        assert form.baking_chilling_2.temperature == 0.0
        assert form.baking_chilling_2.passed is False

    def test_direct_observation_with_comments(self):
        form = parse_ccp3_json(SAMPLE_CCP3)
        assert form.direct_observation.comments == "All OK"

    def test_linked_items(self):
        form = parse_ccp3_json(SAMPLE_CCP3)
        assert len(form.linked_items) == 2
        assert "CCP 3B" in form.linked_items[0]

    def test_empty_input(self):
        form = parse_ccp3_json({})
        assert form.header.quality_check_id == ""
        assert form.linked_items == []

    def test_partial_sections(self):
        """Only baking_chilling_1 present — others stay at defaults."""
        data = {
            "baking_chilling_1": {"temperature": 55.0, "usl": 80.0, "passed": True},
        }
        form = parse_ccp3_json(data)
        assert form.baking_chilling_1.temperature == 55.0
        assert form.baking_start_chilling.temperature == 0.0

    def test_empty_linked_items(self):
        data = {"linked_items": []}
        form = parse_ccp3_json(data)
        assert form.linked_items == []


# ── Dynamic node creation tests (async, requires OPC UA server) ──

@pytest_asyncio.fixture
async def opcua_env():
    """Spin up a minimal OPC UA server for node creation tests."""
    from asyncua import Server
    server = Server()
    await server.init()
    async with server:
        idx = await server.register_namespace("urn:test")
        root = await server.nodes.objects.add_folder(idx, "TestForms")
        yield server, idx, root


@pytest.mark.asyncio
async def test_create_nodes_from_flat_dict(opcua_env):
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    data = {"temperature": 158.0, "batch_number": 1, "passed": True, "time": "9:00 AM"}
    await create_or_update_form_nodes(registry, idx, data)

    assert "temperature" in registry.nodes
    assert "batch_number" in registry.nodes
    assert "passed" in registry.nodes
    assert "time" in registry.nodes

    val = await registry.nodes["temperature"].read_value()
    assert val == 158.0
    val = await registry.nodes["batch_number"].read_value()
    assert val == 1
    val = await registry.nodes["passed"].read_value()
    assert val is True


@pytest.mark.asyncio
async def test_create_nodes_from_nested_dict(opcua_env):
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    data = {
        "header": {"product": "Empanadas", "sku": "120001-C"},
        "start_chilling": {"temperature": 158.0, "passed": True},
    }
    await create_or_update_form_nodes(registry, idx, data)

    assert "header.product" in registry.nodes
    assert "header.sku" in registry.nodes
    assert "start_chilling.temperature" in registry.nodes

    val = await registry.nodes["header.product"].read_value()
    assert val == "Empanadas"


@pytest.mark.asyncio
async def test_update_existing_nodes(opcua_env):
    """Second call updates values without creating duplicate nodes."""
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    await create_or_update_form_nodes(registry, idx, {"temperature": 158.0})
    assert await registry.nodes["temperature"].read_value() == 158.0

    await create_or_update_form_nodes(registry, idx, {"temperature": 72.5})
    assert await registry.nodes["temperature"].read_value() == 72.5

    # Still only one node
    assert len(registry.nodes) == 1


@pytest.mark.asyncio
async def test_missing_fields_retain_last_value(opcua_env):
    """Fields not present in the update keep their previous value."""
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    await create_or_update_form_nodes(
        registry, idx, {"temperature": 158.0, "batch_number": 1}
    )
    # Second update only has temperature — batch_number should stay at 1
    await create_or_update_form_nodes(registry, idx, {"temperature": 72.5})

    assert await registry.nodes["temperature"].read_value() == 72.5
    assert await registry.nodes["batch_number"].read_value() == 1


@pytest.mark.asyncio
async def test_new_fields_added_dynamically(opcua_env):
    """Fields appearing for the first time in a later update get new nodes."""
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    await create_or_update_form_nodes(registry, idx, {"temperature": 158.0})
    assert "rack_number" not in registry.nodes

    await create_or_update_form_nodes(
        registry, idx, {"temperature": 140.0, "rack_number": 2}
    )
    assert await registry.nodes["rack_number"].read_value() == 2
    assert await registry.nodes["temperature"].read_value() == 140.0


@pytest.mark.asyncio
async def test_list_field_as_string(opcua_env):
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    await create_or_update_form_nodes(
        registry, idx, {"linked_items": ["item1", "item2", "item3"]}
    )
    val = await registry.nodes["linked_items"].read_value()
    assert val == "item1; item2; item3"


@pytest.mark.asyncio
async def test_new_subfolder_added_dynamically(opcua_env):
    """A new nested section appearing later gets its own folder."""
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    await create_or_update_form_nodes(
        registry, idx, {"header": {"product": "Empanadas"}}
    )
    assert "header" in registry.folders

    # New section appears
    await create_or_update_form_nodes(
        registry, idx, {"chilling_1": {"temperature": 53.0}}
    )
    assert "chilling_1" in registry.folders
    assert await registry.nodes["chilling_1.temperature"].read_value() == 53.0
    # Old data still there
    assert await registry.nodes["header.product"].read_value() == "Empanadas"


@pytest.mark.asyncio
async def test_type_coercion_on_update(opcua_env):
    """When a field was created as Double, an int update is coerced."""
    server, idx, root = opcua_env
    registry = FormNodeRegistry(root_folder=root)

    await create_or_update_form_nodes(registry, idx, {"temperature": 158.0})
    # Send an int for a Double node
    await create_or_update_form_nodes(registry, idx, {"temperature": 72})
    val = await registry.nodes["temperature"].read_value()
    assert isinstance(val, float)
    assert val == 72.0
