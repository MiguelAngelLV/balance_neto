"""Config flow for Esios Indexada integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig
)



from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("grid_import"): EntitySelector(
            EntitySelectorConfig(multiple=False, device_class=SensorDeviceClass.ENERGY)
        ),
        vol.Required("grid_export"): EntitySelector(
            EntitySelectorConfig(multiple=False, device_class=SensorDeviceClass.ENERGY)
        )
    }
)


class PlaceholderHub:
    def __init__(self, grid_import: str, grid_export: str) -> None:
        """Initialize."""
        self.grid_import = grid_import
        self.grid_export = grid_export


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        else:
            return self.async_create_entry(title="", data=user_input)

