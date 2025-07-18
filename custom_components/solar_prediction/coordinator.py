"""DataUpdateCoordinator for the Solar Prediction integration."""
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from aiohttp.client_exceptions import ClientResponseError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers import event
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
FALLBACK_SCAN_INTERVAL = timedelta(hours=1, minutes=5)
CACHE_VERSION = 1

class SolarPredictionDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API with dynamic scheduling and caching."""

    def __init__(self, hass: HomeAssistant, access_token: str, project: str, config_entry_id: str):
        # ... __init__ bleibt unverändert ...
        self.access_token = access_token
        self.project = project
        self._store = Store(hass, CACHE_VERSION, f"solar_prediction_{config_entry_id}")
        self.last_api_error: str | None = None
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=FALLBACK_SCAN_INTERVAL
        )

    # _async_refresh bleibt unverändert
    async def _async_refresh(self, *args, **kwargs) -> None:
        if self.data is None:
            cached_file_content = await self._store.async_load()
            if cached_file_content:
                self.data = cached_file_content.get("data")
                if self.data:
                    self.last_update_success = True
        if self.data:
            try:
                next_request_epoch = self.data["preferredNextApiRequestAt"]["epochTimeUtc"]
                now_epoch = int(dt_util.utcnow().timestamp())
                if now_epoch < next_request_epoch:
                    _LOGGER.debug("Skipping API refresh, using cached data as it is still valid.")
                    self._schedule_refresh()
                    return
            except (KeyError, TypeError):
                _LOGGER.warning("Cached data is malformed, forcing a new API request.")
        await super()._async_refresh(*args, **kwargs)

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint and fallback to cache."""
        try:
            # ... API-Abruf bleibt unverändert ...
            api_url = "https://solarprognose.de/web/solarprediction/api/v1"
            params = {"access-token": self.access_token, "project": self.project, "type": "hourly"}
            session = async_get_clientsession(self.hass)
            async with session.get(api_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                # === NEU: DATEN-TRANSFORMATION ===
                # Wir berechnen die kumulativen kWh-Werte basierend auf den kW-Leistungswerten neu.
                forecast_data = data.get("data")
                if forecast_data:
                    # 1. Zeitstempel sortieren, um eine korrekte Reihenfolge sicherzustellen
                    timestamps = sorted([int(ts) for ts in forecast_data.keys()])

                    recalculated_cumulative_kwh = 0.0
                    # Setze den ersten kumulativen Wert explizit auf 0
                    if timestamps:
                        forecast_data[str(timestamps[0])][2] = 0.0

                    # 2. Iteriere durch die Zeit-Intervalle
                    for i in range(len(timestamps) - 1):
                        current_ts = timestamps[i]
                        next_ts = timestamps[i+1]

                        # Verarbeite nur lückenlose Stunden-Intervalle
                        if next_ts - current_ts == 3600:
                            power_current = float(forecast_data[str(current_ts)][1])
                            power_next = float(forecast_data[str(next_ts)][1])

                            # 3. Berechne Energie für diese Stunde (Trapez-Formel)
                            # Energie (kWh) = Durchschnittsleistung (kW) * 1 Stunde
                            hourly_energy = (power_current + power_next) / 2.0
                            recalculated_cumulative_kwh += hourly_energy

                        # 4. Überschreibe den alten kumulativen Wert mit dem neuen, korrekten Wert
                        forecast_data[str(next_ts)][2] = round(recalculated_cumulative_kwh, 3)

                await self._store.async_save({"data": data})
                self.last_api_error = None
                return data
        except Exception as err:
            # ... Fehlerbehandlung bleibt unverändert ...
            if isinstance(err, ClientResponseError):
                self.last_api_error = f"API Fehler {err.status}: {err.message}"
            else:
                self.last_api_error = str(err)
            _LOGGER.warning("API request failed (%s). Trying to load from cache.", err)
            cached_file_content = await self._store.async_load()
            if cached_file_content and "data" in cached_file_content:
                cached_data = cached_file_content["data"]
                _LOGGER.info("Successfully loaded data from cache during operation.")
                return cached_data
            _LOGGER.error("API failed and no cached data available.")
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    # _schedule_refresh bleibt unverändert
    def _schedule_refresh(self) -> None:
        if self.last_api_error:
            _LOGGER.warning(
                "API error detected. Falling back to the default refresh interval of %s.",
                self.update_interval
            )
            super()._schedule_refresh()
            return
        if self.last_update_success and self.data:
            try:
                next_request_epoch = self.data["preferredNextApiRequestAt"]["epochTimeUtc"]
                now_epoch = int(dt_util.utcnow().timestamp())
                delay_seconds = max(0, next_request_epoch - now_epoch) + 5
                _LOGGER.debug(
                    "Scheduling next API refresh in %s seconds as suggested by API",
                    delay_seconds
                )
                event.async_call_later(
                    self.hass, delay_seconds, self._handle_refresh_interval
                )
                return
            except (KeyError, TypeError) as e:
                _LOGGER.warning(
                    "Could not determine next refresh time, falling back. Error: %s", e
                )
        super()._schedule_refresh()