"""
Quality check form definitions for HACCP CCP records.

Provides a generic, dynamic approach to creating and updating OPC UA nodes
from arbitrary quality form JSON payloads.  The server does not need to know
the form schema in advance — nodes are created on first encounter and updated
in place on subsequent polls.  Missing fields are left at their last value.

Also retains typed dataclasses and specific parsers for CCP1/CCP3 as
documentation and for unit testing.
"""

import logging
from dataclasses import dataclass, field

from asyncua import Server, ua

logger = logging.getLogger(__name__)

# ── Display-name helpers ─────────────────────────────────────────

_ABBREVIATIONS = {"id": "ID", "sku": "SKU", "usl": "USL", "url": "URL"}


def _snake_to_display(key: str) -> str:
    """Convert a snake_case key to PascalCase for OPC UA display names."""
    parts = key.split("_")
    return "".join(_ABBREVIATIONS.get(p.lower(), p.capitalize()) for p in parts)


# ── OPC UA type detection ────────────────────────────────────────

def _detect_variant(value):
    """Return (VariantType, coerced_value) for a Python value."""
    # bool check must come before int (bool is a subclass of int)
    if isinstance(value, bool):
        return ua.VariantType.Boolean, value
    if isinstance(value, int):
        return ua.VariantType.Int64, value
    if isinstance(value, float):
        return ua.VariantType.Double, value
    if isinstance(value, list):
        return ua.VariantType.String, "; ".join(str(v) for v in value)
    return ua.VariantType.String, str(value) if value is not None else ""


def _coerce_to_variant(value, variant_type):
    """Coerce a Python value to match an existing node's variant type."""
    if variant_type == ua.VariantType.Boolean:
        return bool(value)
    if variant_type == ua.VariantType.Int64:
        return int(value) if value is not None else 0
    if variant_type == ua.VariantType.Double:
        return float(value) if value is not None else 0.0
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value) if value is not None else ""


# ── Dynamic form node registry ───────────────────────────────────

@dataclass
class FormNodeRegistry:
    """Tracks the OPC UA folder and variable nodes for a single form type."""
    root_folder: object
    nodes: dict[str, object] = field(default_factory=dict)
    node_types: dict[str, object] = field(default_factory=dict)
    folders: dict[str, object] = field(default_factory=dict)


async def create_or_update_form_nodes(
    registry: FormNodeRegistry,
    idx: int,
    data: dict,
    prefix: str = "",
) -> None:
    """Create or update OPC UA nodes from a form data dict.

    - New keys  → new folder/variable nodes are created automatically
    - Existing keys → variable nodes are updated with the new value
    - Missing keys  → nodes are left at their last written value
    """
    parent = registry.folders.get(prefix, registry.root_folder)

    for key, value in data.items():
        node_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            if node_key not in registry.folders:
                folder = await parent.add_folder(idx, _snake_to_display(key))
                registry.folders[node_key] = folder
            await create_or_update_form_nodes(registry, idx, value, prefix=node_key)
        else:
            if node_key in registry.nodes:
                # Update existing node, coercing to its established type
                vtype = registry.node_types[node_key]
                coerced = _coerce_to_variant(value, vtype)
                await registry.nodes[node_key].write_value(coerced)
            else:
                # Create new variable node
                variant_type, coerced_value = _detect_variant(value)
                node = await parent.add_variable(
                    idx, _snake_to_display(key), coerced_value, variant_type
                )
                await node.set_writable(False)
                registry.nodes[node_key] = node
                registry.node_types[node_key] = variant_type


# ── Typed dataclasses (documentation + unit tests) ───────────────

@dataclass
class FormHeader:
    quality_check_id: str = ""
    form_name: str = ""
    authenticated_by: str = ""
    auth_time: str = ""
    triggered_by: str = ""
    trigger_time: str = ""
    assigned_to: str = ""
    signed_off_by: str = ""
    sign_off_time: str = ""
    location: str = ""
    product: str = ""
    sku: str = ""
    run_id: str = ""
    custom_reference: str = ""
    run_start_date: str = ""
    run_end_date: str = ""
    run_sign_off_time: str = ""
    run_sign_off_by: str = ""


@dataclass
class ChillingRecord:
    batch_number: int = 0
    temperature: float = 0.0
    time: str = ""
    passed: bool = False


@dataclass
class BakingChillingStartRecord:
    batch_number: int = 0
    rack_number: int = 0
    temperature: float = 0.0
    date_time: str = ""
    passed: bool = False


@dataclass
class BakingChillingRecord:
    temperature: float = 0.0
    usl: float = 0.0
    date_time: str = ""
    passed: bool = False


@dataclass
class DirectObservation:
    verified_by: str = ""
    time: str = ""
    results: str = ""
    comments: str = ""


@dataclass
class CCP1Form:
    """CCP1/2 — Cooking chilling stabilization (Kettle)."""
    header: FormHeader = field(default_factory=FormHeader)
    critical_limits_text: str = ""
    start_chilling: ChillingRecord = field(default_factory=ChillingRecord)
    chilling_process_1: ChillingRecord = field(default_factory=ChillingRecord)
    chilling_process_2: ChillingRecord = field(default_factory=ChillingRecord)
    direct_observation: DirectObservation = field(default_factory=DirectObservation)


@dataclass
class CCP3Form:
    """CCP3/4 — Baking chilling stabilization (Baking Line)."""
    header: FormHeader = field(default_factory=FormHeader)
    critical_limits_text: str = ""
    baking_start_chilling: BakingChillingStartRecord = field(default_factory=BakingChillingStartRecord)
    baking_chilling_1: BakingChillingRecord = field(default_factory=BakingChillingRecord)
    baking_chilling_2: BakingChillingRecord = field(default_factory=BakingChillingRecord)
    direct_observation: DirectObservation = field(default_factory=DirectObservation)
    linked_items: list[str] = field(default_factory=list)


# ── JSON parsers (used by tests, kept for schema documentation) ──

def parse_ccp1_json(data: dict) -> CCP1Form:
    """Parse a JSON dict into a CCP1Form dataclass."""
    form = CCP1Form()
    if "header" in data:
        h = data["header"]
        form.header = FormHeader(**{k: str(v) for k, v in h.items() if k in FormHeader.__dataclass_fields__})
    form.critical_limits_text = data.get("critical_limits_text", "")

    for section, attr in [
        ("start_chilling", "start_chilling"),
        ("chilling_process_1", "chilling_process_1"),
        ("chilling_process_2", "chilling_process_2"),
    ]:
        if section in data:
            s = data[section]
            setattr(form, attr, ChillingRecord(
                batch_number=int(s.get("batch_number", 0)),
                temperature=float(s.get("temperature", 0.0)),
                time=str(s.get("time", "")),
                passed=bool(s.get("passed", False)),
            ))

    if "direct_observation" in data:
        do = data["direct_observation"]
        form.direct_observation = DirectObservation(
            verified_by=str(do.get("verified_by", "")),
            time=str(do.get("time", "")),
            results=str(do.get("results", "")),
        )
    return form


def parse_ccp3_json(data: dict) -> CCP3Form:
    """Parse a JSON dict into a CCP3Form dataclass."""
    form = CCP3Form()
    if "header" in data:
        h = data["header"]
        form.header = FormHeader(**{k: str(v) for k, v in h.items() if k in FormHeader.__dataclass_fields__})
    form.critical_limits_text = data.get("critical_limits_text", "")

    if "baking_start_chilling" in data:
        s = data["baking_start_chilling"]
        form.baking_start_chilling = BakingChillingStartRecord(
            batch_number=int(s.get("batch_number", 0)),
            rack_number=int(s.get("rack_number", 0)),
            temperature=float(s.get("temperature", 0.0)),
            date_time=str(s.get("date_time", "")),
            passed=bool(s.get("passed", False)),
        )

    if "baking_chilling_1" in data:
        s = data["baking_chilling_1"]
        form.baking_chilling_1 = BakingChillingRecord(
            temperature=float(s.get("temperature", 0.0)),
            usl=float(s.get("usl", 0.0)),
            date_time=str(s.get("date_time", "")),
            passed=bool(s.get("passed", False)),
        )

    if "baking_chilling_2" in data:
        s = data["baking_chilling_2"]
        form.baking_chilling_2 = BakingChillingRecord(
            temperature=float(s.get("temperature", 0.0)),
            date_time=str(s.get("date_time", "")),
            passed=bool(s.get("passed", False)),
        )

    if "direct_observation" in data:
        do = data["direct_observation"]
        form.direct_observation = DirectObservation(
            verified_by=str(do.get("verified_by", "")),
            time=str(do.get("time", "")),
            results=str(do.get("results", "")),
            comments=str(do.get("comments", "")),
        )

    form.linked_items = [str(item) for item in data.get("linked_items", [])]
    return form
