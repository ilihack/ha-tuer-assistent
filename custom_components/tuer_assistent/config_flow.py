"""Eintrag ohne Maske: Er entsteht aus der Zeile „tuer_assistent:“ in configuration.yaml.

Home Assistant nimmt Entitäten für Spracherkennung und Gesprächsagenten nur über einen Eintrag an; mehr tut diese Datei nicht.
"""
from homeassistant.config_entries import ConfigFlow

from . import DOMAIN


class TuerAssistentFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_import(self, import_data=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Tür-Assistent (Empfang)", data={})

    async def async_step_user(self, user_input=None):
        return self.async_abort(reason="single_instance_allowed")
