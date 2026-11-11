"""Stimme „Empfang“: liest mit der Stimme von Grok und wählt die Sprache selbst; fällt Grok aus, liest Katja (Home Assistant Cloud).

Warum: Grok liest auch fremde Sprachen richtig, aber nur, wenn die Sprache stimmt: Mit „de“ wird Türkisch unverständlich, mit „tr“
klar (11.11.2026 geprüft, r51/stimmen.py). xAI kann die Sprache selbst erkennen („auto“), Home Assistant lässt „auto“ aber im
Sprachassistenten nicht zu. Diese Entität steht im Sprachassistenten „Tür“ mit Deutsch und reicht an Grok mit „auto“ weiter.
Wort des Betreibers vom 11.11.2026: „Grok ist das Beste als Lese-Engine … Probier das mal. Das würde dann auf automatisch gestellt werden.“
Preis: Grok liefert die Datei erst ganz (0,7 bis 1,4 s); Katja beginnt nach 0,3 bis 0,5 s. Fällt Grok aus oder braucht länger als
ZEIT, liest Katja (dann nur Deutsch gut).
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.components.tts.const import DATA_COMPONENT

from . import DOMAIN, TTS_ERSATZ, TTS_QUELLE, TTS_STIMME

_LOGGER = logging.getLogger(__name__)
ZEIT = 6  # s bis zum Ersatz durch Katja


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EmpfangTTS()])


class EmpfangTTS(TextToSpeechEntity):
    _attr_name = "Empfang (Grok, Sprache automatisch)"
    _attr_unique_id = f"{DOMAIN}_tts"
    _attr_supported_languages = ["de-DE", "en-US", "en-GB"]
    _attr_default_language = "de-DE"
    _attr_supported_options: list[str] = []

    def __init__(self) -> None:
        self.entity_id = "tts.empfang"

    def _entity(self, entity_id: str):
        return self.hass.data[DATA_COMPONENT].get_entity(entity_id)

    async def async_get_tts_audio(self, message, language, options):
        grund = ""
        try:
            grok = self._entity(TTS_QUELLE)
            if grok is None:
                grund = "Stimme %s fehlt" % TTS_QUELLE
            else:
                ergebnis = await asyncio.wait_for(
                    grok.async_internal_get_tts_audio(message, "auto", {"voice": TTS_STIMME, "preferred_format": "mp3"}), ZEIT)
                if ergebnis and ergebnis[1]:
                    return ergebnis
                grund = "leer"
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001  jeder Fehler der fremden Stimme heißt hier nur „Katja liest“
            grund = type(err).__name__
        _LOGGER.warning("Stimme von Grok nicht verfügbar (%s): Katja liest", grund)
        katja = self._entity(TTS_ERSATZ[0])
        if katja is None:
            return None, None
        return await katja.async_internal_get_tts_audio(message, TTS_ERSATZ[1], dict(TTS_ERSATZ[2]))
