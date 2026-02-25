"""
Statistical Process Control (SPC) calculations.

Provides X-bar/R chart statistics, control limits, and process capability
indices from raw measurement data organized into subgroups.
"""

import math
from dataclasses import dataclass, field

# Control chart constants (A2, D3, D4) indexed by subgroup size n=2..10
# Source: ASTM/AIAG SPC reference tables
_A2 = {2: 1.880, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308}
_D3 = {2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223}
_D4 = {2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777}
_d2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}


@dataclass
class SPCResult:
    """Holds all SPC statistics computed from subgroup data."""

    # X-bar chart
    x_bar: float = 0.0               # Grand mean (X-double-bar)
    x_bar_ucl: float = 0.0           # X-bar upper control limit
    x_bar_lcl: float = 0.0           # X-bar lower control limit
    subgroup_means: list[float] = field(default_factory=list)

    # R chart
    r_bar: float = 0.0               # Average range
    r_ucl: float = 0.0               # R upper control limit
    r_lcl: float = 0.0               # R lower control limit
    subgroup_ranges: list[float] = field(default_factory=list)

    # Process statistics
    std_dev: float = 0.0             # Estimated process standard deviation
    sample_count: int = 0            # Total number of individual measurements
    subgroup_count: int = 0          # Number of subgroups

    # Process capability (only when spec limits are provided)
    cp: float | None = None
    cpk: float | None = None
    cpu: float | None = None
    cpl: float | None = None

    # Out-of-control flags
    x_bar_ooc_points: list[int] = field(default_factory=list)
    r_ooc_points: list[int] = field(default_factory=list)


class SPCCalculator:
    """Computes SPC statistics from raw measurement subgroups."""

    def __init__(
        self,
        subgroup_size: int = 5,
        max_subgroups: int = 25,
        sigma_multiplier: float = 3.0,
        upper_spec_limit: float | None = None,
        lower_spec_limit: float | None = None,
    ):
        if subgroup_size < 2 or subgroup_size > 10:
            raise ValueError("subgroup_size must be between 2 and 10")

        self.subgroup_size = subgroup_size
        self.max_subgroups = max_subgroups
        self.sigma_multiplier = sigma_multiplier
        self.usl = upper_spec_limit
        self.lsl = lower_spec_limit

        self._subgroups: list[list[float]] = []

    @property
    def subgroups(self) -> list[list[float]]:
        return list(self._subgroups)

    def add_values(self, values: list[float]) -> None:
        """Add individual values that get chunked into subgroups."""
        for v in values:
            if not self._subgroups or len(self._subgroups[-1]) >= self.subgroup_size:
                self._subgroups.append([])
            self._subgroups[-1].append(v)

        # Trim to max_subgroups (keep only complete ones + current partial)
        complete = [sg for sg in self._subgroups if len(sg) == self.subgroup_size]
        partial = self._subgroups[-1] if self._subgroups and len(self._subgroups[-1]) < self.subgroup_size else None
        if len(complete) > self.max_subgroups:
            complete = complete[-self.max_subgroups:]
        self._subgroups = complete
        if partial:
            self._subgroups.append(partial)

    def add_subgroup(self, subgroup: list[float]) -> None:
        """Add a pre-formed subgroup of measurements."""
        if len(subgroup) != self.subgroup_size:
            raise ValueError(f"Subgroup must contain exactly {self.subgroup_size} values, got {len(subgroup)}")
        self._subgroups.append(subgroup)
        complete = [sg for sg in self._subgroups if len(sg) == self.subgroup_size]
        if len(complete) > self.max_subgroups:
            complete = complete[-self.max_subgroups:]
        self._subgroups = complete

    def clear(self) -> None:
        """Remove all stored subgroup data."""
        self._subgroups.clear()

    def compute(self) -> SPCResult:
        """Compute all SPC statistics from stored subgroups."""
        result = SPCResult()

        # Only use complete subgroups for calculations
        complete = [sg for sg in self._subgroups if len(sg) == self.subgroup_size]
        if not complete:
            return result

        n = self.subgroup_size
        a2 = _A2[n]
        d3 = _D3[n]
        d4 = _D4[n]
        d2 = _d2[n]

        # Subgroup means and ranges
        means = [sum(sg) / len(sg) for sg in complete]
        ranges = [max(sg) - min(sg) for sg in complete]

        result.subgroup_means = means
        result.subgroup_ranges = ranges
        result.subgroup_count = len(complete)
        result.sample_count = sum(len(sg) for sg in complete)

        # Grand mean and average range
        x_bar = sum(means) / len(means)
        r_bar = sum(ranges) / len(ranges)
        result.x_bar = x_bar
        result.r_bar = r_bar

        # Control limits - X-bar chart
        result.x_bar_ucl = x_bar + a2 * r_bar
        result.x_bar_lcl = x_bar - a2 * r_bar

        # Control limits - R chart
        result.r_ucl = d4 * r_bar
        result.r_lcl = d3 * r_bar

        # Process standard deviation estimate (R-bar / d2)
        sigma = r_bar / d2 if d2 > 0 else 0.0
        result.std_dev = sigma

        # Process capability indices
        if sigma > 0:
            if self.usl is not None and self.lsl is not None:
                result.cp = (self.usl - self.lsl) / (2 * self.sigma_multiplier * sigma)
                result.cpu = (self.usl - x_bar) / (self.sigma_multiplier * sigma)
                result.cpl = (x_bar - self.lsl) / (self.sigma_multiplier * sigma)
                result.cpk = min(result.cpu, result.cpl)
            elif self.usl is not None:
                result.cpu = (self.usl - x_bar) / (self.sigma_multiplier * sigma)
            elif self.lsl is not None:
                result.cpl = (x_bar - self.lsl) / (self.sigma_multiplier * sigma)

        # Out-of-control detection
        for i, m in enumerate(means):
            if m > result.x_bar_ucl or m < result.x_bar_lcl:
                result.x_bar_ooc_points.append(i)
        for i, r in enumerate(ranges):
            if r > result.r_ucl or r < result.r_lcl:
                result.r_ooc_points.append(i)

        return result
