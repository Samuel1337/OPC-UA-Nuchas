"""
OPC UA Server that exposes SPC data and HACCP quality check forms.

Fetches JSON measurement data from an HTTP API, computes SPC statistics
(X-bar/R charts, control limits, process capability), and publishes
the results as OPC UA variables for client consumption.  Also serves
CCP1 and CCP3 quality check form data from a forms API endpoint.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from asyncua import Server, ua

from src.api_client import APIClient
from src.config import AppConfig, load_config
from src.quality_forms import (
    FormNodeRegistry,
    create_or_update_form_nodes,
)
from src.spc import SPCCalculator, SPCResult

logger = logging.getLogger(__name__)


class OPCUASPCServer:
    """OPC UA server that exposes SPC metrics and quality forms."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.server = Server()
        self.spc = SPCCalculator(
            subgroup_size=config.spc.subgroup_size,
            max_subgroups=config.spc.max_subgroups,
            sigma_multiplier=config.spc.sigma_multiplier,
            upper_spec_limit=config.spc.upper_spec_limit,
            lower_spec_limit=config.spc.lower_spec_limit,
        )
        self.api_client = APIClient(
            url=config.api.url,
            poll_interval=config.api.poll_interval_seconds,
            timeout=config.api.timeout_seconds,
            headers=config.api.headers,
        )
        self._forms_client: APIClient | None = None
        self._running = False
        self._nodes: dict[str, object] = {}
        self._form_registries: dict[str, FormNodeRegistry] = {}
        self._forms_folder = None
        self._idx: int = 0

    async def init(self) -> None:
        """Initialize the OPC UA server and create the address space."""
        await self.server.init()
        self.server.set_endpoint(self.config.server.endpoint)
        self.server.set_server_name(self.config.server.name)

        idx = await self.server.register_namespace(self.config.server.uri)
        self._idx = idx

        # ── Root folder ────────────────────────────────────────────
        spc_folder = await self.server.nodes.objects.add_folder(idx, "SPC")

        # ── X-bar chart nodes ──────────────────────────────────────
        xbar_folder = await spc_folder.add_folder(idx, "XBarChart")
        self._nodes["x_bar"] = await xbar_folder.add_variable(
            idx, "GrandMean", 0.0, ua.VariantType.Double
        )
        self._nodes["x_bar_ucl"] = await xbar_folder.add_variable(
            idx, "UCL", 0.0, ua.VariantType.Double
        )
        self._nodes["x_bar_lcl"] = await xbar_folder.add_variable(
            idx, "LCL", 0.0, ua.VariantType.Double
        )

        # ── R chart nodes ──────────────────────────────────────────
        r_folder = await spc_folder.add_folder(idx, "RChart")
        self._nodes["r_bar"] = await r_folder.add_variable(
            idx, "AverageRange", 0.0, ua.VariantType.Double
        )
        self._nodes["r_ucl"] = await r_folder.add_variable(
            idx, "UCL", 0.0, ua.VariantType.Double
        )
        self._nodes["r_lcl"] = await r_folder.add_variable(
            idx, "LCL", 0.0, ua.VariantType.Double
        )

        # ── Process statistics ─────────────────────────────────────
        stats_folder = await spc_folder.add_folder(idx, "ProcessStats")
        self._nodes["std_dev"] = await stats_folder.add_variable(
            idx, "StdDev", 0.0, ua.VariantType.Double
        )
        self._nodes["sample_count"] = await stats_folder.add_variable(
            idx, "SampleCount", 0, ua.VariantType.Int64
        )
        self._nodes["subgroup_count"] = await stats_folder.add_variable(
            idx, "SubgroupCount", 0, ua.VariantType.Int64
        )

        # ── Process capability ─────────────────────────────────────
        cap_folder = await spc_folder.add_folder(idx, "Capability")
        self._nodes["cp"] = await cap_folder.add_variable(
            idx, "Cp", 0.0, ua.VariantType.Double
        )
        self._nodes["cpk"] = await cap_folder.add_variable(
            idx, "Cpk", 0.0, ua.VariantType.Double
        )
        self._nodes["cpu"] = await cap_folder.add_variable(
            idx, "Cpu", 0.0, ua.VariantType.Double
        )
        self._nodes["cpl"] = await cap_folder.add_variable(
            idx, "Cpl", 0.0, ua.VariantType.Double
        )

        # ── Out-of-control indicators ─────────────────────────────
        ooc_folder = await spc_folder.add_folder(idx, "OutOfControl")
        self._nodes["x_bar_ooc_count"] = await ooc_folder.add_variable(
            idx, "XBarOOCCount", 0, ua.VariantType.Int64
        )
        self._nodes["r_ooc_count"] = await ooc_folder.add_variable(
            idx, "ROOCCount", 0, ua.VariantType.Int64
        )

        # ── Configuration (read-only info) ─────────────────────────
        config_folder = await spc_folder.add_folder(idx, "Configuration")
        self._nodes["subgroup_size"] = await config_folder.add_variable(
            idx, "SubgroupSize", self.config.spc.subgroup_size, ua.VariantType.Int64
        )
        self._nodes["max_subgroups"] = await config_folder.add_variable(
            idx, "MaxSubgroups", self.config.spc.max_subgroups, ua.VariantType.Int64
        )
        self._nodes["sigma_multiplier"] = await config_folder.add_variable(
            idx, "SigmaMultiplier", self.config.spc.sigma_multiplier, ua.VariantType.Double
        )
        self._nodes["api_url"] = await config_folder.add_variable(
            idx, "APISourceURL", self.config.api.url, ua.VariantType.String
        )
        self._nodes["poll_interval"] = await config_folder.add_variable(
            idx, "PollIntervalSec", self.config.api.poll_interval_seconds, ua.VariantType.Double
        )

        # Make all variable nodes writable=False by default (read-only)
        for node in self._nodes.values():
            await node.set_writable(False)

        # ── Quality Check Forms (dynamic — populated on first API poll) ──
        self._forms_folder = await self.server.nodes.objects.add_folder(idx, "QualityForms")

        logger.info("OPC UA address space initialized")

    async def _update_nodes(self, result: SPCResult) -> None:
        """Write SPC result values into OPC UA nodes."""
        await self._nodes["x_bar"].write_value(result.x_bar)
        await self._nodes["x_bar_ucl"].write_value(result.x_bar_ucl)
        await self._nodes["x_bar_lcl"].write_value(result.x_bar_lcl)

        await self._nodes["r_bar"].write_value(result.r_bar)
        await self._nodes["r_ucl"].write_value(result.r_ucl)
        await self._nodes["r_lcl"].write_value(result.r_lcl)

        await self._nodes["std_dev"].write_value(result.std_dev)
        await self._nodes["sample_count"].write_value(result.sample_count)
        await self._nodes["subgroup_count"].write_value(result.subgroup_count)

        await self._nodes["cp"].write_value(result.cp if result.cp is not None else 0.0)
        await self._nodes["cpk"].write_value(result.cpk if result.cpk is not None else 0.0)
        await self._nodes["cpu"].write_value(result.cpu if result.cpu is not None else 0.0)
        await self._nodes["cpl"].write_value(result.cpl if result.cpl is not None else 0.0)

        await self._nodes["x_bar_ooc_count"].write_value(len(result.x_bar_ooc_points))
        await self._nodes["r_ooc_count"].write_value(len(result.r_ooc_points))

    async def _fetch_forms(self) -> None:
        """Fetch quality form JSON from the forms API and update OPC UA nodes.

        Handles any number of form types dynamically.  New form types get
        a folder created on first encounter.  Missing fields in a form
        update are left at their last written value.
        """
        if not self._forms_client:
            return
        try:
            async with self._forms_client._session.get(
                self.config.api.forms_url
            ) as response:
                response.raise_for_status()
                data = await response.json()
        except Exception as e:
            logger.error("Forms API request failed: %s", e)
            return

        for form_type, form_data in data.items():
            if not isinstance(form_data, dict):
                continue

            # Create a registry + folder for form types we haven't seen yet
            if form_type not in self._form_registries:
                folder = await self._forms_folder.add_folder(
                    self._idx, form_type.upper()
                )
                self._form_registries[form_type] = FormNodeRegistry(root_folder=folder)
                logger.info("New form type discovered: %s", form_type.upper())

            registry = self._form_registries[form_type]
            await create_or_update_form_nodes(registry, self._idx, form_data)

            header = form_data.get("header", {})
            logger.info(
                "%s form updated: %s / %s",
                form_type.upper(),
                header.get("product", "N/A"),
                header.get("sku", "N/A"),
            )

    async def _poll_loop(self) -> None:
        """Continuously fetch data from the API and update nodes."""
        await self.api_client.start()

        # Set up forms client if forms_url is configured
        if self.config.api.forms_url:
            self._forms_client = APIClient(
                url=self.config.api.forms_url,
                poll_interval=self.config.api.poll_interval_seconds,
                timeout=self.config.api.timeout_seconds,
                headers=self.config.api.headers,
            )
            await self._forms_client.start()

        try:
            while self._running:
                # SPC data
                values = await self.api_client.fetch()
                if values:
                    self.spc.add_values(values)
                    result = self.spc.compute()
                    await self._update_nodes(result)
                    logger.info(
                        "SPC updated: X̄=%.4f [%.4f, %.4f]  R̄=%.4f  n=%d subgroups",
                        result.x_bar,
                        result.x_bar_lcl,
                        result.x_bar_ucl,
                        result.r_bar,
                        result.subgroup_count,
                    )

                # Quality forms
                await self._fetch_forms()

                await asyncio.sleep(self.config.api.poll_interval_seconds)
        finally:
            await self.api_client.stop()
            if self._forms_client:
                await self._forms_client.stop()

    async def start(self) -> None:
        """Start the OPC UA server and begin polling."""
        await self.init()
        async with self.server:
            self._running = True
            logger.info("OPC UA server started at %s", self.config.server.endpoint)
            logger.info("Polling API at %s every %.1fs", self.config.api.url, self.config.api.poll_interval_seconds)
            await self._poll_loop()

    def stop(self) -> None:
        """Signal the server to stop."""
        self._running = False
        logger.info("Shutdown signal received")


async def run(config_path: str | None = None) -> None:
    """Entry point: load config, create server, handle signals, run."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(config_path)
    server = OPCUASPCServer(config)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, server.stop)

    await server.start()


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run(config_path))


if __name__ == "__main__":
    main()
