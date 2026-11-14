"""Diagnose zum Herunterladen (Einstellungen → Geräte & Dienste → Tür-Assistent → drei Punkte → „Diagnose herunterladen“).

Enthält, was zur Fehlersuche taugt, und nichts, was nicht aus dem Haus soll: keinen Schlüssel, kein Passwort, keine Adresse der
Station, keine Namen, keine Anweisung und keine Mitschrift; von den Einstellungen nur, woher sie kommen (Oberfläche oder
configuration.yaml), welche gesetzt sind und wie die Angaben heißen, nie ihre Werte. Das Tagebuch der letzten Rufe kommt mit Zeiten,
Zahlen, dem technischen Ablauf und dem Grund des Endes; was Besucher und Empfang gesagt haben, bleibt in `.storage/tuer_assistent.rufe`. Version und Manifest setzt
Home Assistant selbst dazu.
"""
from __future__ import annotations

import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN, STAND, VORGABEN, agenten, angaben_lesen, gewaehlt

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
        # woher die Einstellungen kommen: „Oberfläche“ (Optionen des Eintrags) oder „configuration.yaml“ (nur bis es den Eintrag gibt)
        "eingerichtet_in": daten.get("grok_voice") or "",
        "yaml_block": bool(daten.get("yaml")),  # steht grok_voice noch in configuration.yaml (ignoriert, Hinweis unter Reparaturen)?
    }
    e = entry.options
    try:
        angaben: object = sorted(angaben_lesen(e.get("angaben")))
    except ValueError:
        angaben = "nicht lesbar"
    aus["einstellungen"] = {"bewohner": bool(e.get("bewohner")), "anrede": e.get("anrede") or VORGABEN["anrede"], "angaben": angaben,
                            "begruessung": "eigene" if e.get("begruessung") else "Vorgabe",
                            "anweisung": "eigene, %d Zeichen" % len(str(e["anweisung"])) if e.get("anweisung") else "Vorgabe",
                            "stichwoerter": bool(e.get("stichwoerter")), "modell": e.get("modell") or VORGABEN["modell"]}
    if bruecke is not None:
        jetzt = time.monotonic()  # seit wann: Die Störung kommt erst nach 3 min (Anmeldung) und 6 h (xAI), die Diagnose zeigt den Weg dahin
        aus["innenstation"] = {"kennung": bruecke.kennung, "port": bruecke.port, "angemeldet": bruecke.angemeldet, "xai": bruecke.xai,
                               "stimme": bruecke.stimme, "modell": bruecke.modell, "modell_ist": bruecke.modell_ist, "im_gespraech": bruecke.ruf is not None, "stoerung": bruecke.stoerung(),
                               "nicht_angemeldet_seit_s": None if bruecke.anmelde_fehler_seit is None else round(jetzt - bruecke.anmelde_fehler_seit),
                               "xai_bestaetigt_vor_s": round(jetzt - bruecke.xai_ok_seit)}
        aus["rufe"] = [{k: v for k, v in r.items() if k not in OHNE} for r in bruecke.rufe]
    return aus
