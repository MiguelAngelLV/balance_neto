"""Config flow for Net Balance integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import override
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, GRID_EXPORT, GRID_IMPORT, HOURLY, OFFSET, PERIOD, QUARTER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Net Balance."""

    VERSION = 3

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionFlowHandler:
        return OptionFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Config flow for Net Balance."""
        schema = vol.Schema(
            {
                vol.Required(GRID_IMPORT): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False, device_class=SensorDeviceClass.ENERGY
                    )
                ),
                vol.Required(GRID_EXPORT): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False, device_class=SensorDeviceClass.ENERGY
                    )
                ),
                vol.Required(PERIOD, default=HOURLY): SelectSelector(
                    SelectSelectorConfig(
                        multiple=False,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="periods",
                        options=[
                            SelectOptionDict(label="Hourly", value=HOURLY),
                            SelectOptionDict(label="Quarter of an hour", value=QUARTER),
                        ],
                    )
                ),
                vol.Required(OFFSET, default=5): NumberSelector(
                    NumberSelectorConfig(min=0, max=300, unit_of_measurement="s")
                ),
            }
        )

        # Handle the initial step.
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=schema)

        return self.async_create_entry(title="", data=user_input)


class OptionFlowHandler(config_entries.OptionsFlow):
    """Reconfigure Flow for Net Balance."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize values."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Flow to configure all sensors."""
        grid_import = self.config_entry.options.get(
            GRID_IMPORT, self.config_entry.data[GRID_IMPORT]
        )
        grid_export = self.config_entry.options.get(
            GRID_EXPORT, self.config_entry.data[GRID_EXPORT]
        )
        period = self.config_entry.options.get(PERIOD, self.config_entry.data[PERIOD])
        offset = self.config_entry.options.get(OFFSET, self.config_entry.data[OFFSET])

        schema = vol.Schema(
            {
                vol.Required(GRID_IMPORT, default=grid_import): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False, device_class=SensorDeviceClass.ENERGY
                    )
                ),
                vol.Required(GRID_EXPORT, default=grid_export): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False, device_class=SensorDeviceClass.ENERGY
                    )
                ),
                vol.Required(PERIOD, default=period): SelectSelector(
                    SelectSelectorConfig(
                        multiple=False,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="periods",
                        options=[
                            SelectOptionDict(label="Hourly", value=HOURLY),
                            SelectOptionDict(label="Quarter of an hour", value=QUARTER),
                        ],
                    )
                ),
                vol.Required(OFFSET, default=offset): NumberSelector(
                    NumberSelectorConfig(min=0, max=300, unit_of_measurement="s")
                ),
            }
        )

        # Handle the initial step.
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=schema)

        return self.async_create_entry(title="", data=user_input)
