"""Tests for the SPC calculation module."""

import math
import pytest
from src.spc import SPCCalculator, SPCResult


class TestSPCCalculator:
    def test_default_init(self):
        calc = SPCCalculator()
        assert calc.subgroup_size == 5
        assert calc.max_subgroups == 25
        assert calc.subgroups == []

    def test_invalid_subgroup_size(self):
        with pytest.raises(ValueError):
            SPCCalculator(subgroup_size=1)
        with pytest.raises(ValueError):
            SPCCalculator(subgroup_size=11)

    def test_add_values_creates_subgroups(self):
        calc = SPCCalculator(subgroup_size=3)
        calc.add_values([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        subgroups = calc.subgroups
        assert len(subgroups) == 3  # 2 complete + 1 partial
        assert subgroups[0] == [1.0, 2.0, 3.0]
        assert subgroups[1] == [4.0, 5.0, 6.0]
        assert subgroups[2] == [7.0]

    def test_add_subgroup(self):
        calc = SPCCalculator(subgroup_size=3)
        calc.add_subgroup([1.0, 2.0, 3.0])
        calc.add_subgroup([4.0, 5.0, 6.0])
        assert len(calc.subgroups) == 2

    def test_add_subgroup_wrong_size(self):
        calc = SPCCalculator(subgroup_size=3)
        with pytest.raises(ValueError):
            calc.add_subgroup([1.0, 2.0])

    def test_max_subgroups_trimming(self):
        calc = SPCCalculator(subgroup_size=2, max_subgroups=3)
        for i in range(10):
            calc.add_subgroup([float(i), float(i + 1)])
        assert len(calc.subgroups) == 3
        # Should keep the last 3
        assert calc.subgroups[0] == [7.0, 8.0]

    def test_compute_empty_returns_defaults(self):
        calc = SPCCalculator()
        result = calc.compute()
        assert result.x_bar == 0.0
        assert result.subgroup_count == 0

    def test_compute_basic_stats(self):
        calc = SPCCalculator(subgroup_size=5)
        # 5 subgroups of 5 values each — all values = 10.0
        for _ in range(5):
            calc.add_subgroup([10.0, 10.0, 10.0, 10.0, 10.0])

        result = calc.compute()
        assert result.x_bar == pytest.approx(10.0)
        assert result.r_bar == pytest.approx(0.0)
        assert result.x_bar_ucl == pytest.approx(10.0)
        assert result.x_bar_lcl == pytest.approx(10.0)
        assert result.subgroup_count == 5
        assert result.sample_count == 25

    def test_compute_with_variation(self):
        calc = SPCCalculator(subgroup_size=5)
        calc.add_subgroup([10.0, 12.0, 11.0, 9.0, 10.5])
        calc.add_subgroup([10.5, 11.0, 10.0, 9.5, 11.5])
        calc.add_subgroup([9.8, 10.2, 10.6, 11.0, 10.4])

        result = calc.compute()
        assert result.subgroup_count == 3
        assert result.x_bar > 0
        assert result.r_bar > 0
        assert result.x_bar_ucl > result.x_bar
        assert result.x_bar_lcl < result.x_bar
        assert result.r_ucl > result.r_bar
        assert result.std_dev > 0

    def test_control_limits_formula(self):
        """Verify X-bar/R limits match hand calculation for n=5."""
        calc = SPCCalculator(subgroup_size=5)
        calc.add_subgroup([10.0, 12.0, 11.0, 9.0, 10.0])
        calc.add_subgroup([11.0, 10.0, 12.0, 11.0, 10.0])

        result = calc.compute()

        # Hand calculation:
        # Subgroup means: 10.4, 10.8 => X-double-bar = 10.6
        # Subgroup ranges: 3.0, 2.0 => R-bar = 2.5
        # A2 for n=5 = 0.577
        # UCL_xbar = 10.6 + 0.577*2.5 = 12.0425
        # LCL_xbar = 10.6 - 0.577*2.5 = 9.1575
        # D4 for n=5 = 2.114  => UCL_R = 2.114*2.5 = 5.285
        # D3 for n=5 = 0.0    => LCL_R = 0.0
        assert result.x_bar == pytest.approx(10.6)
        assert result.r_bar == pytest.approx(2.5)
        assert result.x_bar_ucl == pytest.approx(12.0425)
        assert result.x_bar_lcl == pytest.approx(9.1575)
        assert result.r_ucl == pytest.approx(5.285)
        assert result.r_lcl == pytest.approx(0.0)

    def test_process_capability(self):
        calc = SPCCalculator(
            subgroup_size=5,
            upper_spec_limit=15.0,
            lower_spec_limit=5.0,
        )
        calc.add_subgroup([10.0, 12.0, 11.0, 9.0, 10.0])
        calc.add_subgroup([11.0, 10.0, 12.0, 11.0, 10.0])

        result = calc.compute()
        assert result.cp is not None
        assert result.cpk is not None
        assert result.cp > 0
        assert result.cpk > 0
        assert result.cpk <= result.cp

    def test_no_capability_without_spec_limits(self):
        calc = SPCCalculator(subgroup_size=5)
        calc.add_subgroup([10.0, 12.0, 11.0, 9.0, 10.0])
        calc.add_subgroup([11.0, 10.0, 12.0, 11.0, 10.0])

        result = calc.compute()
        assert result.cp is None
        assert result.cpk is None

    def test_out_of_control_detection(self):
        calc = SPCCalculator(subgroup_size=5)
        # Normal subgroups
        for _ in range(5):
            calc.add_subgroup([10.0, 10.1, 9.9, 10.0, 10.1])
        # Out-of-control subgroup (extreme mean)
        calc.add_subgroup([20.0, 21.0, 19.0, 20.5, 20.0])

        result = calc.compute()
        assert len(result.x_bar_ooc_points) > 0
        assert 5 in result.x_bar_ooc_points  # The 6th subgroup (index 5)

    def test_clear(self):
        calc = SPCCalculator(subgroup_size=3)
        calc.add_subgroup([1.0, 2.0, 3.0])
        calc.clear()
        assert calc.subgroups == []

    def test_partial_subgroup_ignored_in_compute(self):
        calc = SPCCalculator(subgroup_size=5)
        calc.add_subgroup([10.0, 10.0, 10.0, 10.0, 10.0])
        calc.add_values([99.0, 99.0])  # Partial subgroup

        result = calc.compute()
        # Only the complete subgroup should be used
        assert result.subgroup_count == 1
        assert result.x_bar == pytest.approx(10.0)
