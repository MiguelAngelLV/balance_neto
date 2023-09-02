"""Balance Neto"""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_migrate_entries
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry):
    version = config_entry.version

    if version == 1:
        @callback
        def _async_migrator(entity_entry: er.RegistryEntry):
            new_unique_id = entity_entry.unique_id
            old_unique_id = entity_entry.unique_id
            if "import" in entity_entry.unique_id:
                new_unique_id = f"{entity_entry.config_entry_id}-import"
            if "export" in entity_entry.unique_id:
                new_unique_id = f"{entity_entry.config_entry_id}-export"
            if "balance" in entity_entry.unique_id:
                new_unique_id = f"{entity_entry.config_entry_id}-balance"

            _LOGGER.debug("Updating unique_id from %s to %s", old_unique_id, new_unique_id)
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, config_entry.entry_id, _async_migrator)
        config_entry.version = 2

    return True
