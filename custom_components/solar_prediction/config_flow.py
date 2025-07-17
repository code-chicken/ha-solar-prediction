"""Config flow for the Solar Prediction integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

# Wir brauchen aiohttp, um die API-Anfrage zu stellen
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

# Wir importieren unsere Konstanten
from .const import DOMAIN, CONF_PROJECT

_LOGGER = logging.getLogger(__name__)

# 1. Das Datenschema anpassen
# Wir ersetzen Host, Username, Password durch die Felder, die wir wirklich brauchen.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("access_token"): str,
        vol.Required(CONF_PROJECT): str,
    }
)


# 2. Die Validierungslogik ersetzen
async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect to the solarprediction API."""

    # Die Platzhalter-Logik ("hub") wird komplett ersetzt.
    # Stattdessen rufen wir direkt die API auf.

    api_url = "https://solarprognose.de/web/solarprediction/api/v1"
    params = {
        "access-token": data["access_token"],
        "project": data[CONF_PROJECT],
    }

    session = async_get_clientsession(hass)
    try:
        async with session.get(api_url, params=params) as response:
            # Wenn die API einen Fehler zurückgibt (z.B. 401 Unauthorized, 404 Not Found)
            # lösen wir eine Exception aus, die im Flow abgefangen wird.
            if response.status != 200:
                # Wir können nicht unterscheiden, ob der Token falsch ist oder
                # die Verbindung fehlschlägt, also verwenden wir CannotConnect.
                _LOGGER.error(
                    "API validation failed with status %s: %s",
                    response.status,
                    await response.text(),
                )
                raise CannotConnect

            # Wenn alles gut geht, geben wir die Infos zurück, die im Eintrag gespeichert
            # werden sollen. Wir nutzen den Projektnamen für den Titel des Eintrags.
            return {"title": data[CONF_PROJECT]}

    except Exception as exc:
        # Fängt alle anderen Fehler ab (z.B. DNS-Probleme, kein Internet)
        _LOGGER.error("Failed to connect to API during validation: %s", exc)
        raise CannotConnect from exc


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Prediction."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                # 3. Die Validierung aufrufen
                # Diese Zeile ruft unsere neue Logik von oben auf.
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                # Diese Exception wird von uns nicht mehr direkt ausgelöst,
                # aber wir behalten sie für den Fall der Fälle.
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Wenn `validate_input` erfolgreich war, erstellen wir den Eintrag.
                # `info["title"]` kommt aus unserer Funktion, `user_input` enthält die
                # eingegebenen Daten (Token, Projekt) zur Speicherung.
                return self.async_create_entry(title=info["title"], data=user_input)

        # Das Formular wird mit unserem neuen Schema angezeigt.
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


# 4. Die Fehlerklassen behalten wir bei
# Sie werden vom Flow in der `async_step_user` Methode verwendet.
class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
