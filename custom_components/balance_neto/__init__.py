"""Balance Neto."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import HOURLY, OFFSET, PERIOD

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialise entry configuration."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Remove entry after unload component."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    # update entry replacing data with new options
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, **config_entry.options}
    )
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migration scripts."""
    version = config_entry.version

    if version == 1:

        @callback
        def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, str]:
            new_unique_id = entity_entry.unique_id
            old_unique_id = entity_entry.unique_id
            if "import" in entity_entry.unique_id:
                new_unique_id = f"{entity_entry.config_entry_id}-import"
            if "export" in entity_entry.unique_id:
                new_unique_id = f"{entity_entry.config_entry_id}-export"
            if "balance" in entity_entry.unique_id:
                new_unique_id = f"{entity_entry.config_entry_id}-balance"

            _LOGGER.debug(
                "Updating unique_id from %s to %s", old_unique_id, new_unique_id
            )
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, config_entry.entry_id, _async_migrator)
        config_entry.version = 2

    if version == 2:  # noqa: PLR2004
        data = {
            **config_entry.data,
            PERIOD: HOURLY,
            OFFSET: 5,
        }

        hass.config_entries.async_update_entry(config_entry, data=data)

        config_entry.version = 3

    return True
