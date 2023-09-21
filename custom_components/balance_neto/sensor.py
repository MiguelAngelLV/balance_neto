from datetime import datetime
from datetime import timedelta
import logging
from typing import Mapping, Any

from homeassistant.components.sensor import (
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    DEVICE_CLASS_ENERGY,
    SensorEntityDescription,
    RestoreEntity
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.core import State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.event import async_track_state_change
from .const import MAX_DIFF

EXPORT_DESCRIPTION = SensorEntityDescription(
    key="net_exported",
    icon="mdi:home-export-outline",
    name="Net exported",
    translation_key="net_exported",
    has_entity_name=True,
    native_unit_of_measurement="kWh",
    device_class=DEVICE_CLASS_ENERGY,
    state_class=STATE_CLASS_TOTAL_INCREASING,
    suggested_display_precision=2
)

IMPORT_DESCRIPTION = SensorEntityDescription(
    key="net_imported",
    icon="mdi:home-import-outline",
    name="Net imported",
    translation_key="net_imported",
    has_entity_name=True,
    device_class=DEVICE_CLASS_ENERGY,
    native_unit_of_measurement="kWh",
    state_class=STATE_CLASS_TOTAL_INCREASING,
    suggested_display_precision=2
)

BALANCE_DESCRIPTION = SensorEntityDescription(
    key="net_balance",
    icon="mdi:scale-balance",
    name="Net Balance",
    translation_key="net_balance",
    has_entity_name=True,
    native_unit_of_measurement="kWh",
    suggested_display_precision=2
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    import_id = entry.data['grid_import']
    export_id = entry.data['grid_export']

    grid_import = GridSensor(IMPORT_DESCRIPTION, f"{entry.entry_id}-import")
    grid_export = GridSensor(EXPORT_DESCRIPTION, f"{entry.entry_id}-export")

    grid_balance = BalanceSensor(BALANCE_DESCRIPTION, grid_import, grid_export, import_id, export_id, f"{entry.entry_id}-balance")

    async_add_entities([grid_import, grid_export, grid_balance])

    def update_values(changed_entity: str, old_state: State | None, new_state: State | None):
        grid_balance.update_values()

    async_track_state_change(hass, import_id, update_values)
    async_track_state_change(hass, export_id, update_values)

    _LOGGER.debug("Starting Balance Neto with %s for import and %s for export", import_id, export_id)

    async def update_totals_and_schedule(now):
        grid_balance.update_totals()
        async_track_point_in_time(hass, update_totals_and_schedule, now + timedelta(hours=1))

    async def first_after_reboot(now):
        grid_export.after_reboot()
        grid_import.after_reboot()

    next = datetime.now().replace(minute=59, second=55, microsecond=0)
    async_track_point_in_time(hass, update_totals_and_schedule, next)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, first_after_reboot)


class GridSensor(SensorEntity, RestoreEntity):
    def __init__(self, description: SensorEntityDescription, unique_id) -> None:
        super().__init__()
        self._state = 0
        self._attrs: Mapping[str, Any] = {}
        self._attr_unique_id = unique_id
        self.entity_description = description
        self._reboot = None

    async def async_added_to_hass(self):
        _LOGGER.debug("Added %s", self._attr_unique_id)
        if (last_sensor_data := await self.async_get_last_state()) is not None:
            self._state = float(last_sensor_data.state)

    @property
    def extra_state_attributes(self):
        return {
            'Reboot': self._reboot,
        }

    @property
    def native_value(self):
        return self._state

    def update_value(self, value: float):
        self._state = float(self._state) + value
        self.async_write_ha_state()
        _LOGGER.debug("Updating value %f for %s", self._state, self._attr_unique_id)

    def after_reboot(self):
        self._reboot = datetime.now().isoformat()
        self.async_write_ha_state()


class BalanceSensor(SensorEntity, RestoreEntity):
    def __init__(self, description: SensorEntityDescription,
                 import_sensor: GridSensor,
                 export_sensor: GridSensor,
                 import_id: str,
                 export_id: str,
                 unique_id
                 ) -> None:
        super().__init__()
        self._import = 0
        self._export = 0
        self._import_offset = 0
        self._import_id = import_id
        self._export_offset = 0
        self._export_id = export_id
        self._import_sensor = import_sensor
        self._export_sensor = export_sensor
        self._state = 0
        self._attrs: Mapping[str, Any] = {}
        self._attr_unique_id = unique_id
        self.entity_description = description

        self._last_reset = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_state()) is not None:
            self._state = last_sensor_data.state
            self._import = last_sensor_data.attributes.get('Import', 0)
            self._export = last_sensor_data.attributes.get('Export', 0)
            self._import_offset = last_sensor_data.attributes.get('Import Offset', 0)
            self._export_offset = last_sensor_data.attributes.get('Export Offset', 0)
            self._last_reset = last_sensor_data.attributes.get('Last Reset')

        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            'Import': self._import,
            'Export': self._export,
            'Import Offset': self._import_offset,
            'Export Offset': self._export_offset,
            'Last Reset': self._last_reset
        }

    def _update_value(self):
        self._state = (self._export - self._export_offset) - (self._import - self._import_offset)
        _LOGGER.debug("Actual Balance %f", self._state)
        self.async_write_ha_state()

    def update_values(self):

        try:

            _LOGGER.debug("Import (%s): %s", self._import_id, self.hass.states.get(self._import_id).state)
            _LOGGER.debug("Export (%s): %s", self._export_id, self.hass.states.get(self._export_id).state)

            import_state = float(self.hass.states.get(self._import_id).state)
            export_state = float(self.hass.states.get(self._export_id).state)

            if self._import_offset == 0:
                self._import_offset = import_state

            diff = import_state - self._import_offset
            if diff > MAX_DIFF or diff < 0:
                self._import_offset = import_state

            if self._export_offset == 0:
                self._export_offset = export_state

            diff = export_state - self._export_offset
            if diff > MAX_DIFF or diff < 0:
                self._export_offset = export_state

            _LOGGER.debug("Updating Balance Neto. Actual Import %f, Export %f. Import offset %f, Export offset %f",
                            import_state, export_state, self._import_offset, self._export_offset)

            self._import = import_state
            self._export = export_state

            self._update_value()
        except ValueError as e:
            _LOGGER.error(e)
            return

    def update_totals(self):
        value = float(self._state)
        _LOGGER.debug("Updating net values. Balance %f")
        self._last_reset = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:00:00")
        self._import_offset = self._import
        self._export_offset = self._export
        if value > 0:
            self._export_sensor.update_value(value)
        else:
            self._import_sensor.update_value(-value)

        self._update_value()

    def _reset(self):
        self._import_offset = 0
        self._export_offset = 0

    @staticmethod
    def _is_value_valid(export_state, import_state):
        try:
            float(export_state.state)
            float(import_state.state)
            return True
        except ValueError:
            return False
