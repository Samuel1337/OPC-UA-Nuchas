"""Tests for quality form JSON parsing."""

from src.quality_forms import (
    parse_ccp1_json,
    parse_ccp3_json,
    CCP1Form,
    CCP3Form,
)


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
