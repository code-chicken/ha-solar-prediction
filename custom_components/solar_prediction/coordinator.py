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

    def __init__(
        self, hass: HomeAssistant, access_token: str, project: str, config_entry_id: str
    ):
        """Initialize."""
        self.access_token = access_token
        self.project = project
        self._store = Store(hass, CACHE_VERSION, f"solar_prediction_{config_entry_id}")
        self.last_api_error: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=FALLBACK_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from API endpoint and fallback to cache."""
        try:
            api_url = "https://solarprognose.de/web/solarprediction/api/v1"
            params = {
                "access-token": self.access_token,
                "project": self.project,
                "type": "hourly",
            }
            session = async_get_clientsession(self.hass)
            async with session.get(api_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                # Speichern der Rohdaten der API in einem Wrapper
                await self._store.async_save({"data": data})
                self.last_api_error = None
                return data
        except Exception as err:
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

    def _schedule_refresh(self) -> None:
        """Schedule the next refresh based on API suggestion."""
        # Diese Methode bleibt unverändert
        if self.last_update_success and self.data:
            try:
                next_request_epoch = self.data["preferredNextApiRequestAt"][
                    "epochTimeUtc"
                ]
                now_epoch = int(dt_util.utcnow().timestamp())
                delay_seconds = max(0, next_request_epoch - now_epoch) + 5
                _LOGGER.debug(
                    "Scheduling next API refresh in %s seconds as suggested by API",
                    delay_seconds,
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
