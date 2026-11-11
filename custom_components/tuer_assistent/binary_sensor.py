"""Sensor „Empfang Störung“: an, wenn der Empfang am obersten Knopf nicht gehen würde (Wort des Betreibers vom 11.11.2026 spätabends: „in der
Überwachung haben, dass diese Integration funktioniert, unsere xAI-Keys nicht ausgelaufen sind und ansonsten im Notfall eine Plakette
kommt“). Gründe: Grok Voice ist eingetragen, aber nicht gestartet; seit 3 min nicht an der Station angemeldet; xAI-Schlüssel abgelehnt
oder gesperrt; xAI seit 6 h nicht erreichbar (`Bruecke.stoerung()` in sprache.py). Fragt alle 30 s nach; darauf hört die Plakette
„Empfang“ auf den Hubs.
"""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from . import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EmpfangStoerung()], update_before_add=True)


class EmpfangStoerung(BinarySensorEntity):
    _attr_name = "Empfang Störung"
    _attr_unique_id = f"{DOMAIN}_stoerung"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:account-voice-off"
    _attr_should_poll = True

    def __init__(self) -> None:
        self.entity_id = "binary_sensor.empfang_stoerung"

    async def async_update(self) -> None:
        daten = self.hass.data.get(DOMAIN) or {}
        if not daten.get("grok_voice"):            # nicht eingetragen: nichts zu überwachen
            grund = ""
        elif daten.get("bruecke") is None:
            grund = "Grok Voice nicht gestartet (Log)"
        else:
            bruecke = daten["bruecke"]
            grund = bruecke.stoerung()
        self._attr_is_on = bool(grund)
        self._attr_extra_state_attributes = {"grund": grund}
        if daten.get("bruecke") is not None:
            self._attr_extra_state_attributes.update(anmeldung="angemeldet" if daten["bruecke"].angemeldet else "nicht angemeldet",
                                                     xai=daten["bruecke"].xai)
