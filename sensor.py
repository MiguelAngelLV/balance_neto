from datetime import datetime
from datetime import timedelta
from typing import Mapping, Any

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
    grid_balance = BalanceSensor(BALANCE_DESCRIPTION, grid_import, grid_export)

    def update_import(changed_entity: str,
                      old_state: State | None,
                      new_state: State | None):
        grid_balance.update_import(new_state)

    def update_export(changed_entity: str,
                      old_state: State | None,
                      new_state: State | None):
        grid_balance.update_export(new_state)

    async_add_entities([grid_import, grid_export, grid_balance])
    async_track_state_change(hass, entry.data['grid_import'], update_import)
    async_track_state_change(hass, entry.data['grid_export'], update_export)

    async def update_totals_and_schedule(now):
        grid_balance.update_totals()
        n = datetime.now()
        next = n.replace(hour=n.hour, minute=0, second=0) + timedelta(hours=1)
        async_track_point_in_time(hass, update_totals_and_schedule, next)

    now = datetime.now()
    next = now.replace(hour=now.hour, minute=0, second=0) + timedelta(hours=1)
    async_track_point_in_time(hass, update_totals_and_schedule, next)




class GridSensor(SensorEntity, RestoreEntity):

    def __init__(self, description: SensorEntityDescription,) -> None:
        super().__init__()
        self._native_value = 0
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = description.name
        self._attr_unique_id = description.key
        self.entity_description = description
        self._task = None


    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_state()) is not None:
            if last_sensor_data.state.isnumeric():
                self._native_value = last_sensor_data.state

        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._native_value

    def update_value(self, value: float):
        self._native_value = value
        self.async_write_ha_state()


class BalanceSensor(SensorEntity, RestoreEntity):
    def __init__(self, description: SensorEntityDescription,
                 import_sensor: GridSensor,
                 export_sensor: GridSensor) -> None:
        super().__init__()
        self._import = 0
        self._export = 0
        self._import_offset = 0
        self._export_offset = 0
        self._import_sensor = import_sensor
        self._export_sensor = export_sensor

        self._native_value = 0
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = description.name
        self._attr_unique_id = description.key
        self.entity_description = description

        self._last_reset = None
        self._task = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_state()) is not None:
            self._native_value = last_sensor_data.state
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
        return self._native_value

    @property
    def extra_state_attributes(self):
        return {'Import Offset': self._import_offset, 'Export Offset': self._export_offset,
                'Last Reset': self._last_reset}

    def _update_value(self):
        self._native_value = (self._export - self._export_offset) - (self._import - self._import_offset)
        self.async_write_ha_state()

    def update_import(self, state: State | None):
        if state is None:
            return

        self._import = float(state.state)
        if self._import_offset == 0:
            self._import_offset = self._import

        self._update_value()

    def update_export(self, state: State | None):
        if state is None:
            return
        self._export = float(state.state)
        if self._export_offset == 0:
            self._export_offset = self._export

        self._update_value()

    def update_totals(self):
        self._last_reset = datetime.utcnow().strftime("%Y-%m-%d %H:00:00")
        self._import_offset = self._import
        self._export_offset = self._export
        if self._native_value > 0:
            self._export_sensor.update_value(self._native_value)
        else:
            self._import_sensor.update_value(-self._native_value)

    def _reset(self):
        self._import_offset = 0
        self._export_offset = 0
