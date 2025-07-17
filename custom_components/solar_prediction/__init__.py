"""The Solar Prediction integration."""

from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_PROJECT
from .coordinator import SolarPredictionDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
type SolarPredictionConfigEntry = ConfigEntry[SolarPredictionDataUpdateCoordinator]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: SolarPredictionConfigEntry
) -> bool:
    """Set up Solar Prediction from a config entry."""
    access_token = entry.data[CONF_ACCESS_TOKEN]
    project = entry.data[CONF_PROJECT]

    # Manuelle Instanz des Speichers, um den Cache vorab zu prüfen
    store = Store(hass, 1, f"solar_prediction_{entry.entry_id}")

    # Erstellen Sie die Koordinator-Instanz
    coordinator = SolarPredictionDataUpdateCoordinator(
        hass, access_token, project, entry.entry_id
    )

    # Prüfen, ob gültige, gecachte Daten vorhanden sind
    cached_data_wrapper = await store.async_load()
    initial_data_loaded_from_cache = False
    if cached_data_wrapper and "data" in cached_data_wrapper:
        cached_api_response = cached_data_wrapper["data"]
        try:
            next_request_epoch = cached_api_response["preferredNextApiRequestAt"][
                "epochTimeUtc"
            ]
            now_epoch = int(dt_util.utcnow().timestamp())

            if now_epoch < next_request_epoch:
                _LOGGER.info(
                    "Startup: Gültige Cache-Daten gefunden. Überspringe ersten API-Aufruf."
                )
                # Setzen Sie die Daten des Koordinators manuell aus dem Cache
                coordinator.async_set_updated_data(cached_api_response)
                initial_data_loaded_from_cache = True
        except (KeyError, TypeError):
            _LOGGER.warning(
                "Startup: Cache-Daten sind fehlerhaft. Erzwinge API-Aktualisierung."
            )

    # Nur wenn keine gültigen Cache-Daten geladen wurden, eine neue Anfrage stellen
    if not initial_data_loaded_from_cache:
        _LOGGER.info(
            "Startup: Kein gültiger Cache gefunden. Führe erste API-Aktualisierung durch."
        )
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SolarPredictionConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
