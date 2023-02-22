from datetime import datetime
from datetime import timedelta
from typing import Mapping, Any
import asyncio
from .const import MAX_DIFF

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    DEVICE_CLASS_ENERGY,
    SensorEntityDescription,
    RestoreEntity
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.core import State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.event import async_track_point_in_time

EXPORT_DESCRIPTION = SensorEntityDescription(
    key="exportado_a_la_red",
    icon="mdi:home-export-outline",
    name="Exportación Neta",
    native_unit_of_measurement="kWh",
    device_class=DEVICE_CLASS_ENERGY,
    state_class=STATE_CLASS_TOTAL_INCREASING,
)

IMPORT_DESCRIPTION = SensorEntityDescription(
    key="importado_de_la_red",
    icon="mdi:home-import-outline",
    name="Importación Neta",
    device_class=DEVICE_CLASS_ENERGY,
    native_unit_of_measurement="kWh",
    state_class=STATE_CLASS_TOTAL_INCREASING,
)

BALANCE_DESCRIPTION = SensorEntityDescription(
    key="balance_neto",
    icon="mdi:scale-balance",
    name="Balance Neto",
    native_unit_of_measurement="kWh",
)


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    grid_import = GridSensor(IMPORT_DESCRIPTION)
    grid_export = GridSensor(EXPORT_DESCRIPTION)

    import_id = entry.data['grid_import']
    export_id = entry.data['grid_export']
    grid_balance = BalanceSensor(BALANCE_DESCRIPTION, grid_import, grid_export, import_id, export_id, hass)

    async_add_entities([grid_import, grid_export, grid_balance])

    def update_import(changed_entity: str, old_state: State | None, new_state: State | None):
        grid_balance.update_import(new_state)

    def update_export(changed_entity: str, old_state: State | None, new_state: State | None):
        grid_balance.update_export(new_state)

    async_track_state_change(hass, import_id, update_import)
    async_track_state_change(hass, export_id, update_export)

    async def update_totals_and_schedule(now):
        grid_balance.update_totals()
        async_track_point_in_time(hass, update_totals_and_schedule, now + timedelta(hours=1))

    next = datetime.now().replace(minute=59, second=55, microsecond=0)
    async_track_point_in_time(hass, update_totals_and_schedule, next)


class GridSensor(SensorEntity, RestoreEntity):

    def __init__(self, description: SensorEntityDescription, ) -> None:
        super().__init__()
        self._state = 0
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = description.name
        self._attr_unique_id = description.key
        self.entity_description = description

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_state()) is not None:
            self._state = float(last_sensor_data.state)

        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._state

    def update_value(self, value: float):
        self._state = float(self._state) + value
        self.async_write_ha_state()


class BalanceSensor(SensorEntity, RestoreEntity):
    def __init__(self, description: SensorEntityDescription,
                 import_sensor: GridSensor,
                 export_sensor: GridSensor,
                 import_id: str,
                 export_id: str,
                 hass
                 ) -> None:
        super().__init__()
        self._import = 0
        self._export = 0
        self._import_offset = 0
        self._export_offset = 0
        self._import_sensor = import_sensor
        self._export_sensor = export_sensor

        self._state = 0
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = description.name
        self._attr_unique_id = description.key
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

        # Si se restablece en hora distinta, se evita usar valores antiguos
        date = datetime.utcnow().strftime("%Y-%m-%d %H:00:00")
        if date != self._last_reset:
            self.update_totals()
            self._reset()

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
        self._state = round((self._export - self._export_offset) - (self._import - self._import_offset), 2)
        self.async_write_ha_state()

    def update_import(self, state: State | None):
        if state is None:
            return

        value = float(state.state)

        if self._import_offset == 0:
            self._import_offset = value

        self._import = value

        self._update_value()

    def update_export(self, state: State | None):
        if state is None or state.state == 0:
            return

        value = float(state.state)

        if self._export_offset == 0:
            self._export_offset = value

        self._export = value
        self._update_value()

    def update_totals(self):

        value = float(self._state)
        self._last_reset = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:00:00")
        self._import_offset = self._import
        self._export_offset = self._export
        if value > 0:
            self._export_sensor.update_value(value)
        else:
            self._import_sensor.update_value(-value)

    def _reset(self):
        self._import_offset = 0
        self._export_offset = 0
