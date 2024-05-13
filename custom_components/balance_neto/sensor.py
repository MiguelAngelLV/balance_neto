"""Create and add sensors to Home Assistant."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Mapping

import pytz
from typing_extensions import override

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change,
)

from .const import GRID_EXPORT, GRID_IMPORT, HOURLY, MAX_DIFF, OFFSET, PERIOD

if TYPE_CHECKING:
    from decimal import Decimal

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import StateType

EXPORT_DESCRIPTION = SensorEntityDescription(
    key="net_exported",
    icon="mdi:home-export-outline",
    name="Net exported",
    translation_key="net_exported",
    has_entity_name=True,
    native_unit_of_measurement="kWh",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    suggested_display_precision=2,
)

IMPORT_DESCRIPTION = SensorEntityDescription(
    key="net_imported",
    icon="mdi:home-import-outline",
    name="Net imported",
    translation_key="net_imported",
    has_entity_name=True,
    device_class=SensorDeviceClass.ENERGY,
    native_unit_of_measurement="kWh",
    state_class=SensorStateClass.TOTAL_INCREASING,
    suggested_display_precision=2,
)

BALANCE_DESCRIPTION = SensorEntityDescription(
    key="net_balance",
    icon="mdi:scale-balance",
    name="Net Balance",
    translation_key="net_balance",
    has_entity_name=True,
    native_unit_of_measurement="kWh",
    suggested_display_precision=2,
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.MEASUREMENT
)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-locals
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialise sensors and add to Home Assistant."""
    offset = entry.data[OFFSET]
    period = entry.data[PERIOD]
    import_id = entry.data[GRID_IMPORT]
    export_id = entry.data[GRID_EXPORT]
    grid_import = GridNetSensor(IMPORT_DESCRIPTION, f"{entry.entry_id}-import")
    grid_export = GridNetSensor(EXPORT_DESCRIPTION, f"{entry.entry_id}-export")

    grid_balance = BalanceSensor(
        BALANCE_DESCRIPTION,
        grid_import,
        grid_export,
        import_id,
        export_id,
        f"{entry.entry_id}-balance",
    )

    async_add_entities([grid_import, grid_export, grid_balance])

    minutes = 60 if period == HOURLY else 15

    def update_values(
        _changed_entity: str, _old_state: State | None, _new_state: State | None
    ) -> None:
        grid_balance.update_values()

    async_track_state_change(hass, import_id, update_values)
    async_track_state_change(hass, export_id, update_values)

    _LOGGER.debug(
        "Starting Balance Neto with %s for import and %s for export",
        import_id,
        export_id,
    )

    @callback
    async def update_totals_and_schedule(_now: datetime) -> None:
        grid_balance.update_totals()
        async_track_point_in_time(
            hass, update_totals_and_schedule, now + timedelta(minutes=minutes)
        )

    async def first_after_reboot(_now: datetime) -> None:
        grid_export.after_reboot()
        grid_import.after_reboot()

    now = datetime.now(tz=pytz.UTC).replace(second=0, microsecond=0)

    next_minutes = minutes - now.minute % minutes
    next_reset = (
        now.replace(second=0)
        + timedelta(minutes=next_minutes)
        - timedelta(seconds=offset)
    )

    async_track_point_in_time(hass, update_totals_and_schedule, next_reset)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, first_after_reboot)


class GridNetSensor(SensorEntity, RestoreEntity):
    """Grid (Import o Export) sensor."""

    def __init__(self, description: SensorEntityDescription, unique_id: str) -> None:
        """Initialize values."""
        super().__init__()
        self._state = 0
        self._attrs: Mapping[str, Any] = {}
        self._attr_unique_id = unique_id
        self.entity_description = description
        self._reboot = None

    @override
    async def async_added_to_hass(self) -> None:
        _LOGGER.debug("Added %s", self._attr_unique_id)
        if (last_sensor_data := await self.async_get_last_state()) is not None:
            self._state = float(last_sensor_data.state)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return {
            "Reboot": self._reboot,
        }

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        return self._state

    def update_value(self, value: float) -> None:
        """Update with balance."""
        self._state = float(self._state) + value
        self.schedule_update_ha_state()
        _LOGGER.debug("Updating value %f for %s", self._state, self._attr_unique_id)

    def after_reboot(self) -> None:
        """Set after reboot."""
        self._reboot = datetime.now(tz=pytz.UTC).isoformat()
        self.schedule_update_ha_state()


class BalanceSensor(SensorEntity, RestoreEntity):
    """Net Balance Sensor."""

    # pylint: disable=too-many-instance-attributes too-many-arguments
    def __init__(  # noqa: PLR0913
        self,
        description: SensorEntityDescription,
        import_sensor: GridNetSensor,
        export_sensor: GridNetSensor,
        import_id: str,
        export_id: str,
        unique_id: str,
    ) -> None:
        """Initialise values."""
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

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_state()) is not None:
            self._state = last_sensor_data.state
            self._import = last_sensor_data.attributes.get("Import", 0)
            self._export = last_sensor_data.attributes.get("Export", 0)
            self._import_offset = last_sensor_data.attributes.get("Import Offset", 0)
            self._export_offset = last_sensor_data.attributes.get("Export Offset", 0)

        self.async_write_ha_state()

    @property
    @override
    def native_value(self) -> StateType | date | datetime | Decimal:
        return self._state

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return {
            "Import": self._import,
            "Export": self._export,
            "Import Offset": self._import_offset,
            "Export Offset": self._export_offset,
        }

    def _update_value(self) -> None:
        self._state = (self._export - self._export_offset) - (
            self._import - self._import_offset
        )
        _LOGGER.debug("Actual Balance %f", self._state)
        self.schedule_update_ha_state()

    def update_values(self) -> None:
        """Update Net Balance state."""
        try:
            _LOGGER.debug(
                "Import (%s): %s",
                self._import_id,
                self.hass.states.get(self._import_id).state,
            )
            _LOGGER.debug(
                "Export (%s): %s",
                self._export_id,
                self.hass.states.get(self._export_id).state,
            )

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

            _LOGGER.debug(
                "Updating Balance Neto. Actual Import %f, Export %f. Import offset %f, Export offset %f",
                import_state,
                export_state,
                self._import_offset,
                self._export_offset,
            )

            self._import = import_state
            self._export = export_state

            self._update_value()
        except ValueError:
            _LOGGER.exception(
                "Errors values, Import %s and Export %s",
                self.hass.states.get(self._import_id).state,
                self.hass.states.get(self._export_id).state,
            )
            return

    def update_totals(self) -> None:
        """Update Net Total values."""
        value = float(self._state)
        _LOGGER.debug("Updating net values. Balance %f")
        self._import_offset = self._import
        self._export_offset = self._export
        if value > 0:
            self._export_sensor.update_value(value)
        else:
            self._import_sensor.update_value(-value)

        self._update_value()

    def _reset(self) -> None:
        self._import_offset = 0
        self._export_offset = 0
