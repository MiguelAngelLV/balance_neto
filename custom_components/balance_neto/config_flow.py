"""Config flow for Esios Indexada integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectOptionDict,
    SelectSelectorMode,
    SelectSelectorConfig, NumberSelector, NumberSelectorConfig,
)

from .const import DOMAIN, HOURLY, QUARTER, GRID_IMPORT, GRID_EXPORT, PERIOD, OFFSET

_LOGGER = logging.getLogger(__name__)


class PlaceholderHub:
    def __init__(self, grid_import: str, grid_export: str) -> None:
        """Initialize."""
        self.grid_import = grid_import
        self.grid_export = grid_export


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionFlowHandler(config_entry)

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        schema = vol.Schema({
            vol.Required(GRID_IMPORT): EntitySelector(
                EntitySelectorConfig(multiple=False, device_class=SensorDeviceClass.ENERGY)
            ),
            vol.Required(GRID_EXPORT): EntitySelector(
                EntitySelectorConfig(multiple=False, device_class=SensorDeviceClass.ENERGY)
            ),
            vol.Required(PERIOD, default=HOURLY): SelectSelector(
                SelectSelectorConfig(multiple=False, mode=SelectSelectorMode.DROPDOWN,
                                     translation_key="periods",
                                     options=[
                                         SelectOptionDict(label="Hourly", value=HOURLY),
                                         SelectOptionDict(label="Quarter of an hour", value=QUARTER),
                                     ])
            ),
            vol.Required(OFFSET, default=5): NumberSelector(
                NumberSelectorConfig(min=0, max=300, unit_of_measurement="s")
            ),
        })

        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=schema
            )
        else:
            return self.async_create_entry(title="", data=user_input)



class OptionFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        grid_import = self.config_entry.options.get(GRID_IMPORT, self.config_entry.data[GRID_IMPORT])
        grid_export = self.config_entry.options.get(GRID_EXPORT, self.config_entry.data[GRID_EXPORT])
        period = self.config_entry.options.get(PERIOD, self.config_entry.data[PERIOD])
        offset = self.config_entry.options.get(OFFSET, self.config_entry.data[OFFSET])

        schema = vol.Schema({
            vol.Required(GRID_IMPORT, default=grid_import): EntitySelector(
                EntitySelectorConfig(multiple=False, device_class=SensorDeviceClass.ENERGY)
            ),
            vol.Required(GRID_EXPORT, default=grid_export): EntitySelector(
                EntitySelectorConfig(multiple=False, device_class=SensorDeviceClass.ENERGY)
            ),
            vol.Required(PERIOD, default=period): SelectSelector(
                SelectSelectorConfig(multiple=False, mode=SelectSelectorMode.DROPDOWN,
                                     translation_key="periods",
                                     options=[
                                         SelectOptionDict(label="Hourly", value=HOURLY),
                                         SelectOptionDict(label="Quarter of an hour", value=QUARTER),
                                     ])
            ),
            vol.Required(OFFSET, default=offset): NumberSelector(
                NumberSelectorConfig(min=0, max=300, unit_of_measurement="s")
            ),
        })

        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="init", data_schema=schema
            )
        else:
            return self.async_create_entry(title="", data=user_input)
