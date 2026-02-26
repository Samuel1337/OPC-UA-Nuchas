"""
Quality check form definitions for HACCP CCP records.

Defines the OPC UA address space structure for CCP1 (Cooking/Kettle chilling)
and CCP3 (Baking/Line chilling) quality check forms.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from asyncua import Server, ua

logger = logging.getLogger(__name__)


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


async def _add_header_nodes(parent, idx: int) -> dict[str, object]:
    """Create OPC UA nodes for the shared form header fields."""
    folder = await parent.add_folder(idx, "Header")
    nodes = {}
    string_fields = [
        ("QualityCheckID", "quality_check_id"),
        ("FormName", "form_name"),
        ("AuthenticatedBy", "authenticated_by"),
        ("AuthTime", "auth_time"),
        ("TriggeredBy", "triggered_by"),
        ("TriggerTime", "trigger_time"),
        ("AssignedTo", "assigned_to"),
        ("SignedOffBy", "signed_off_by"),
        ("SignOffTime", "sign_off_time"),
        ("Location", "location"),
        ("Product", "product"),
        ("SKU", "sku"),
        ("RunID", "run_id"),
        ("CustomReference", "custom_reference"),
        ("RunStartDate", "run_start_date"),
        ("RunEndDate", "run_end_date"),
        ("RunSignOffTime", "run_sign_off_time"),
        ("RunSignOffBy", "run_sign_off_by"),
    ]
    for display_name, key in string_fields:
        nodes[f"header_{key}"] = await folder.add_variable(
            idx, display_name, "", ua.VariantType.String
        )
    return nodes


async def _add_chilling_nodes(parent, idx: int, folder_name: str, prefix: str) -> dict[str, object]:
    """Create OPC UA nodes for a chilling record (CCP1-style)."""
    folder = await parent.add_folder(idx, folder_name)
    nodes = {}
    nodes[f"{prefix}_batch_number"] = await folder.add_variable(
        idx, "BatchNumber", 0, ua.VariantType.Int64
    )
    nodes[f"{prefix}_temperature"] = await folder.add_variable(
        idx, "Temperature", 0.0, ua.VariantType.Double
    )
    nodes[f"{prefix}_time"] = await folder.add_variable(
        idx, "Time", "", ua.VariantType.String
    )
    nodes[f"{prefix}_passed"] = await folder.add_variable(
        idx, "Pass", False, ua.VariantType.Boolean
    )
    return nodes


async def _add_direct_observation_nodes(parent, idx: int, prefix: str, include_comments: bool = False) -> dict[str, object]:
    """Create OPC UA nodes for direct observation section."""
    folder = await parent.add_folder(idx, "DirectObservation")
    nodes = {}
    nodes[f"{prefix}_verified_by"] = await folder.add_variable(
        idx, "VerifiedBy", "", ua.VariantType.String
    )
    nodes[f"{prefix}_time"] = await folder.add_variable(
        idx, "Time", "", ua.VariantType.String
    )
    nodes[f"{prefix}_results"] = await folder.add_variable(
        idx, "Results", "", ua.VariantType.String
    )
    if include_comments:
        nodes[f"{prefix}_comments"] = await folder.add_variable(
            idx, "Comments", "", ua.VariantType.String
        )
    return nodes


async def create_ccp1_nodes(server: Server, idx: int, parent) -> dict[str, object]:
    """Build the full OPC UA address space for a CCP1 form."""
    ccp1_folder = await parent.add_folder(idx, "CCP1")
    nodes = {}

    # Critical limits text
    nodes["ccp1_critical_limits"] = await ccp1_folder.add_variable(
        idx, "CriticalLimitsText", "", ua.VariantType.String
    )

    # Header
    header_nodes = await _add_header_nodes(ccp1_folder, idx)
    nodes.update({f"ccp1_{k}": v for k, v in header_nodes.items()})

    # Start Chilling
    sc_nodes = await _add_chilling_nodes(ccp1_folder, idx, "StartChilling", "start_chilling")
    nodes.update({f"ccp1_{k}": v for k, v in sc_nodes.items()})

    # Chilling Process 1
    c1_nodes = await _add_chilling_nodes(ccp1_folder, idx, "ChillingProcess1", "chilling1")
    nodes.update({f"ccp1_{k}": v for k, v in c1_nodes.items()})

    # Chilling Process 2
    c2_nodes = await _add_chilling_nodes(ccp1_folder, idx, "ChillingProcess2", "chilling2")
    nodes.update({f"ccp1_{k}": v for k, v in c2_nodes.items()})

    # Direct Observation
    do_nodes = await _add_direct_observation_nodes(ccp1_folder, idx, "obs")
    nodes.update({f"ccp1_{k}": v for k, v in do_nodes.items()})

    # Make all read-only
    for node in nodes.values():
        await node.set_writable(False)

    logger.info("CCP1 quality form nodes created")
    return nodes


async def create_ccp3_nodes(server: Server, idx: int, parent) -> dict[str, object]:
    """Build the full OPC UA address space for a CCP3 form."""
    ccp3_folder = await parent.add_folder(idx, "CCP3")
    nodes = {}

    # Critical limits text
    nodes["ccp3_critical_limits"] = await ccp3_folder.add_variable(
        idx, "CriticalLimitsText", "", ua.VariantType.String
    )

    # Header
    header_nodes = await _add_header_nodes(ccp3_folder, idx)
    nodes.update({f"ccp3_{k}": v for k, v in header_nodes.items()})

    # Baking Start Chilling
    bsc_folder = await ccp3_folder.add_folder(idx, "BakingStartChilling")
    nodes["ccp3_bsc_batch_number"] = await bsc_folder.add_variable(
        idx, "BatchNumber", 0, ua.VariantType.Int64
    )
    nodes["ccp3_bsc_rack_number"] = await bsc_folder.add_variable(
        idx, "RackNumber", 0, ua.VariantType.Int64
    )
    nodes["ccp3_bsc_temperature"] = await bsc_folder.add_variable(
        idx, "Temperature", 0.0, ua.VariantType.Double
    )
    nodes["ccp3_bsc_date_time"] = await bsc_folder.add_variable(
        idx, "DateTime", "", ua.VariantType.String
    )
    nodes["ccp3_bsc_passed"] = await bsc_folder.add_variable(
        idx, "Pass", False, ua.VariantType.Boolean
    )

    # Baking Chilling 1
    bc1_folder = await ccp3_folder.add_folder(idx, "BakingChilling1")
    nodes["ccp3_bc1_temperature"] = await bc1_folder.add_variable(
        idx, "Temperature", 0.0, ua.VariantType.Double
    )
    nodes["ccp3_bc1_usl"] = await bc1_folder.add_variable(
        idx, "USL", 0.0, ua.VariantType.Double
    )
    nodes["ccp3_bc1_date_time"] = await bc1_folder.add_variable(
        idx, "DateTime", "", ua.VariantType.String
    )
    nodes["ccp3_bc1_passed"] = await bc1_folder.add_variable(
        idx, "Pass", False, ua.VariantType.Boolean
    )

    # Baking Chilling 2
    bc2_folder = await ccp3_folder.add_folder(idx, "BakingChilling2")
    nodes["ccp3_bc2_temperature"] = await bc2_folder.add_variable(
        idx, "Temperature", 0.0, ua.VariantType.Double
    )
    nodes["ccp3_bc2_date_time"] = await bc2_folder.add_variable(
        idx, "DateTime", "", ua.VariantType.String
    )
    nodes["ccp3_bc2_passed"] = await bc2_folder.add_variable(
        idx, "Pass", False, ua.VariantType.Boolean
    )

    # Direct Observation (with comments for CCP3)
    do_nodes = await _add_direct_observation_nodes(ccp3_folder, idx, "obs", include_comments=True)
    nodes.update({f"ccp3_{k}": v for k, v in do_nodes.items()})

    # Linked Items (semicolon-delimited string)
    nodes["ccp3_linked_items"] = await ccp3_folder.add_variable(
        idx, "LinkedItems", "", ua.VariantType.String
    )

    # Make all read-only
    for node in nodes.values():
        await node.set_writable(False)

    logger.info("CCP3 quality form nodes created")
    return nodes


async def update_ccp1_nodes(nodes: dict[str, object], form: CCP1Form) -> None:
    """Write CCP1 form data into OPC UA nodes."""
    h = form.header
    await nodes["ccp1_header_quality_check_id"].write_value(h.quality_check_id)
    await nodes["ccp1_header_form_name"].write_value(h.form_name)
    await nodes["ccp1_header_authenticated_by"].write_value(h.authenticated_by)
    await nodes["ccp1_header_auth_time"].write_value(h.auth_time)
    await nodes["ccp1_header_triggered_by"].write_value(h.triggered_by)
    await nodes["ccp1_header_trigger_time"].write_value(h.trigger_time)
    await nodes["ccp1_header_assigned_to"].write_value(h.assigned_to)
    await nodes["ccp1_header_signed_off_by"].write_value(h.signed_off_by)
    await nodes["ccp1_header_sign_off_time"].write_value(h.sign_off_time)
    await nodes["ccp1_header_location"].write_value(h.location)
    await nodes["ccp1_header_product"].write_value(h.product)
    await nodes["ccp1_header_sku"].write_value(h.sku)
    await nodes["ccp1_header_run_id"].write_value(h.run_id)
    await nodes["ccp1_header_custom_reference"].write_value(h.custom_reference)
    await nodes["ccp1_header_run_start_date"].write_value(h.run_start_date)
    await nodes["ccp1_header_run_end_date"].write_value(h.run_end_date)
    await nodes["ccp1_header_run_sign_off_time"].write_value(h.run_sign_off_time)
    await nodes["ccp1_header_run_sign_off_by"].write_value(h.run_sign_off_by)

    await nodes["ccp1_critical_limits"].write_value(form.critical_limits_text)

    # Start Chilling
    sc = form.start_chilling
    await nodes["ccp1_start_chilling_batch_number"].write_value(sc.batch_number)
    await nodes["ccp1_start_chilling_temperature"].write_value(sc.temperature)
    await nodes["ccp1_start_chilling_time"].write_value(sc.time)
    await nodes["ccp1_start_chilling_passed"].write_value(sc.passed)

    # Chilling Process 1
    c1 = form.chilling_process_1
    await nodes["ccp1_chilling1_batch_number"].write_value(c1.batch_number)
    await nodes["ccp1_chilling1_temperature"].write_value(c1.temperature)
    await nodes["ccp1_chilling1_time"].write_value(c1.time)
    await nodes["ccp1_chilling1_passed"].write_value(c1.passed)

    # Chilling Process 2
    c2 = form.chilling_process_2
    await nodes["ccp1_chilling2_batch_number"].write_value(c2.batch_number)
    await nodes["ccp1_chilling2_temperature"].write_value(c2.temperature)
    await nodes["ccp1_chilling2_time"].write_value(c2.time)
    await nodes["ccp1_chilling2_passed"].write_value(c2.passed)

    # Direct Observation
    do = form.direct_observation
    await nodes["ccp1_obs_verified_by"].write_value(do.verified_by)
    await nodes["ccp1_obs_time"].write_value(do.time)
    await nodes["ccp1_obs_results"].write_value(do.results)


async def update_ccp3_nodes(nodes: dict[str, object], form: CCP3Form) -> None:
    """Write CCP3 form data into OPC UA nodes."""
    h = form.header
    await nodes["ccp3_header_quality_check_id"].write_value(h.quality_check_id)
    await nodes["ccp3_header_form_name"].write_value(h.form_name)
    await nodes["ccp3_header_authenticated_by"].write_value(h.authenticated_by)
    await nodes["ccp3_header_auth_time"].write_value(h.auth_time)
    await nodes["ccp3_header_triggered_by"].write_value(h.triggered_by)
    await nodes["ccp3_header_trigger_time"].write_value(h.trigger_time)
    await nodes["ccp3_header_assigned_to"].write_value(h.assigned_to)
    await nodes["ccp3_header_signed_off_by"].write_value(h.signed_off_by)
    await nodes["ccp3_header_sign_off_time"].write_value(h.sign_off_time)
    await nodes["ccp3_header_location"].write_value(h.location)
    await nodes["ccp3_header_product"].write_value(h.product)
    await nodes["ccp3_header_sku"].write_value(h.sku)
    await nodes["ccp3_header_run_id"].write_value(h.run_id)
    await nodes["ccp3_header_custom_reference"].write_value(h.custom_reference)
    await nodes["ccp3_header_run_start_date"].write_value(h.run_start_date)
    await nodes["ccp3_header_run_end_date"].write_value(h.run_end_date)
    await nodes["ccp3_header_run_sign_off_time"].write_value(h.run_sign_off_time)
    await nodes["ccp3_header_run_sign_off_by"].write_value(h.run_sign_off_by)

    await nodes["ccp3_critical_limits"].write_value(form.critical_limits_text)

    # Baking Start Chilling
    bsc = form.baking_start_chilling
    await nodes["ccp3_bsc_batch_number"].write_value(bsc.batch_number)
    await nodes["ccp3_bsc_rack_number"].write_value(bsc.rack_number)
    await nodes["ccp3_bsc_temperature"].write_value(bsc.temperature)
    await nodes["ccp3_bsc_date_time"].write_value(bsc.date_time)
    await nodes["ccp3_bsc_passed"].write_value(bsc.passed)

    # Baking Chilling 1
    bc1 = form.baking_chilling_1
    await nodes["ccp3_bc1_temperature"].write_value(bc1.temperature)
    await nodes["ccp3_bc1_usl"].write_value(bc1.usl)
    await nodes["ccp3_bc1_date_time"].write_value(bc1.date_time)
    await nodes["ccp3_bc1_passed"].write_value(bc1.passed)

    # Baking Chilling 2
    bc2 = form.baking_chilling_2
    await nodes["ccp3_bc2_temperature"].write_value(bc2.temperature)
    await nodes["ccp3_bc2_date_time"].write_value(bc2.date_time)
    await nodes["ccp3_bc2_passed"].write_value(bc2.passed)

    # Direct Observation
    do = form.direct_observation
    await nodes["ccp3_obs_verified_by"].write_value(do.verified_by)
    await nodes["ccp3_obs_time"].write_value(do.time)
    await nodes["ccp3_obs_results"].write_value(do.results)
    await nodes["ccp3_obs_comments"].write_value(do.comments)

    # Linked Items
    await nodes["ccp3_linked_items"].write_value("; ".join(form.linked_items))


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
