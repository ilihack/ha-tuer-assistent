"""Diagnose zum Herunterladen (Einstellungen → Geräte & Dienste → Tür-Assistent → drei Punkte → „Diagnose herunterladen“).

Enthält, was zur Fehlersuche taugt, und nichts, was nicht aus dem Haus soll: keinen Schlüssel, kein Passwort, keine Adresse der
Station, keine Namen und keine Mitschrift. Das Tagebuch der letzten Rufe kommt mit Zeiten, Zahlen, dem technischen Ablauf und dem
Grund des Endes; was Besucher und Empfang gesagt haben, bleibt in `.storage/tuer_assistent.rufe`. Version und Manifest setzt
Home Assistant selbst dazu.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN, STAND, agenten, gewaehlt

OHNE = ("mitschrift",)  # Felder eines Rufs, die nicht in die Diagnose gehören


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    daten = hass.data.get(DOMAIN) or {}
    bruecke = daten.get("bruecke")
    stand = hass.states.get(STAND)
    stoerung = hass.states.get("binary_sensor.empfang_stoerung")
    aus: dict = {
        "stand": dict(stand.attributes) if stand else {},
        "stoerung": {"zustand": stoerung.state, "grund": stoerung.attributes.get("grund")} if stoerung else None,
        "agenten": agenten(hass), "gewaehlt": gewaehlt(hass)[0],
        "grok_voice": "eingetragen" if daten.get("grok_voice") else "nicht eingetragen",
    }
    if bruecke is not None:
        aus["innenstation"] = {"kennung": bruecke.kennung, "port": bruecke.port, "angemeldet": bruecke.angemeldet, "xai": bruecke.xai,
                               "stimme": bruecke.stimme, "im_gespraech": bruecke.ruf is not None, "stoerung": bruecke.stoerung()}
        aus["rufe"] = [{k: v for k, v in r.items() if k not in OHNE} for r in bruecke.rufe]
    return aus
