"""Sensor platform for Solar Prediction."""

from __future__ import annotations
import logging  # Import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import SolarPredictionDataUpdateCoordinator
from . import SolarPredictionConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)  # Initialisiere Logger


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarPredictionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # ... (Rest der Funktion bleibt gleich)
    coordinator = entry.runtime_data
    sensors_to_add: list[SensorEntity] = [
        SolarPredictionDailyTotalSensor(coordinator, "today"),
        SolarPredictionDailyTotalSensor(coordinator, "tomorrow"),
        SolarPredictionStatusSensor(coordinator),
    ]
    if coordinator.data and coordinator.data.get("data"):
        for timestamp_str in coordinator.data["data"].keys():
            sensors_to_add.append(
                SolarPredictionHourlySensor(coordinator, timestamp_str)
            )
    async_add_entities(sensors_to_add)


class SolarPredictionStatusSensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    # ... (Diese Klasse bleibt unverändert)
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: SolarPredictionDataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project}_status"
        self._attr_name = "API Status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> str:
        if self.coordinator.last_api_error:
            return self.coordinator.last_api_error[:255]
        return "OK"

    @property
    def icon(self) -> str:
        return (
            "mdi:cloud-alert" if self.coordinator.last_api_error else "mdi:cloud-check"
        )

    @property
    def available(self) -> bool:
        return True


class SolarPredictionDailyTotalSensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    # ... (Der Anfang dieser Klasse bleibt gleich)
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:solar-power"
    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPredictionDataUpdateCoordinator, day: str):
        super().__init__(coordinator)
        self._day = day
        self._attr_unique_id = f"{coordinator.project}_{day}_total"
        self._attr_name = f"{day.title()} Total"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> float | None:
        """Find the last cumulative kWh value of the day."""
        forecast_data = self.coordinator.data and self.coordinator.data.get("data")
        if not forecast_data:
            return None
        try:
            hass_tz = dt_util.get_time_zone(self.hass.config.time_zone)
            today_in_tz = dt_util.now(hass_tz).date()
            target_date = (
                today_in_tz if self._day == "today" else today_in_tz + timedelta(days=1)
            )

            last_timestamp = 0
            for ts_str in forecast_data.keys():
                ts = int(ts_str)
                timestamp_dt = dt_util.as_local(dt_util.utc_from_timestamp(ts))
                if timestamp_dt.date() == target_date and ts > last_timestamp:
                    last_timestamp = ts

            if last_timestamp > 0:
                values = forecast_data[str(last_timestamp)]

                # KORREKTUR: Prüft die Länge des Arrays für mehr Robustheit
                if len(values) > 2:
                    final_value = values[2]  # Bevorzugt das dritte Element
                else:
                    final_value = values[1]  # Fallback auf das zweite Element

                return round(float(final_value), 3)
            return 0.0
        except (ValueError, KeyError, IndexError) as e:
            _LOGGER.error("Error calculating daily total for %s: %s", self.name, e)
            return None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success or self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        # ... (Diese Methode bleibt unverändert)
        forecast_data = self.coordinator.data and self.coordinator.data.get("data")
        if not forecast_data:
            return None
        try:
            hass_tz = dt_util.get_time_zone(self.hass.config.time_zone)
            today_in_tz = dt_util.now(hass_tz).date()
            target_date = (
                today_in_tz if self._day == "today" else today_in_tz + timedelta(days=1)
            )

            daily_timestamps = sorted(
                [
                    ts_str
                    for ts_str in forecast_data
                    if dt_util.as_local(dt_util.utc_from_timestamp(int(ts_str))).date()
                    == target_date
                ],
                key=int,
            )

            if not daily_timestamps:
                return None

            daily_forecast_transformed = {}
            first_ts_of_day = int(daily_timestamps[0])
            ts_before_first = str(first_ts_of_day - 3600)
            previous_cumulative_kwh = 0.0
            if ts_before_first in forecast_data:
                # KORREKTUR: Auch hier die Länge prüfen
                prev_values = forecast_data[ts_before_first]
                previous_cumulative_kwh = float(
                    prev_values[2] if len(prev_values) > 2 else prev_values[1]
                )

            for ts_str in daily_timestamps:
                values = forecast_data[ts_str]
                # KORREKTUR: Auch hier die Länge prüfen
                current_cumulative_kwh = float(
                    values[2] if len(values) > 2 else values[1]
                )

                hourly_kwh = current_cumulative_kwh - previous_cumulative_kwh
                if hourly_kwh < 0:
                    hourly_kwh = current_cumulative_kwh

                daily_forecast_transformed[ts_str] = {
                    "power_kw": round(
                        float(values[1]), 3
                    ),  # Annahme: Leistung ist immer an Index 1
                    "hourly_kwh": round(hourly_kwh, 3),
                }
                previous_cumulative_kwh = current_cumulative_kwh
            return {"hourly_forecast": daily_forecast_transformed}
        except (ValueError, KeyError, IndexError) as e:
            _LOGGER.error("Error calculating daily attributes for %s: %s", self.name, e)
            return None


class SolarPredictionHourlySensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    # ... (Diese Klasse bleibt unverändert)
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:solar-power"
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SolarPredictionDataUpdateCoordinator, timestamp_str: str
    ):
        super().__init__(coordinator)
        self._timestamp_str = timestamp_str
        timestamp_dt = dt_util.as_local(dt_util.utc_from_timestamp(int(timestamp_str)))
        self._attr_unique_id = f"{coordinator.project}_hourly_{timestamp_str}"
        self._attr_name = f"{timestamp_dt.strftime('%d.%m %H:%M')}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> float | None:
        forecast_data = self.coordinator.data and self.coordinator.data.get("data")
        if not forecast_data or self._timestamp_str not in forecast_data:
            return None
        try:
            current_ts = int(self._timestamp_str)
            values = forecast_data[self._timestamp_str]
            current_cumulative_kwh = float(values[2] if len(values) > 2 else values[1])

            previous_ts_str = str(current_ts - 3600)
            previous_cumulative_kwh = 0.0
            if previous_ts_str in forecast_data:
                prev_values = forecast_data[previous_ts_str]
                previous_cumulative_kwh = float(
                    prev_values[2] if len(prev_values) > 2 else prev_values[1]
                )

            hourly_energy = current_cumulative_kwh - previous_cumulative_kwh
            if hourly_energy < 0:
                hourly_energy = current_cumulative_kwh
            return round(hourly_energy, 3)
        except (KeyError, IndexError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        forecast_data = self.coordinator.data and self.coordinator.data.get("data")
        if not forecast_data or self._timestamp_str not in forecast_data:
            return None
        try:
            values = forecast_data[self._timestamp_str]
            power_kw = values[1]
            cumulative_kwh = values[2] if len(values) > 2 else values[1]
            return {
                "power_kw": round(float(power_kw), 3),
                "cumulative_kwh": round(float(cumulative_kwh), 3),
            }
        except (KeyError, IndexError, ValueError):
            return None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success or self.coordinator.data is not None
