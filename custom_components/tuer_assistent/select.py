"""Auswahl „Empfang KI“: an welchen Gesprächsagenten der Empfang weiterreicht. Zur Wahl steht nur, was configuration.yaml nennt."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, GERAET, agenten

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EmpfangWahl(list(agenten(hass)))])


class EmpfangWahl(SelectEntity, RestoreEntity):
    _attr_name = "Empfang KI"
    _attr_unique_id = f"{DOMAIN}_ki"
    _attr_icon = "mdi:account-voice"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_info = GERAET
    _attr_should_poll = False

    def __init__(self, liste: list[str]) -> None:
        self.entity_id = "select.empfang_ki"
        self._attr_options = liste
        self._attr_current_option = liste[0]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        alt = await self.async_get_last_state()
        if alt is not None and alt.state in self._attr_options:
            self._attr_current_option = alt.state

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
