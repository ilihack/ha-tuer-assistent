"""Spracherkennung „Empfang“: reicht den Ton an die Erkennung von Grok weiter und fängt ihr Scheitern ab.

Warum: Liefert die Erkennung keinen Text (ein Geräusch, ein Räuspern, ein Aussetzer bei xAI), meldet SuperGrok einen Fehler, und der
VoIP Stack legt bei jedem Fehler des Sprachassistenten sofort auf. So endeten am 11.11.2026 drei von vier echten Rufen. Diese Entität
gibt dann stattdessen den Platzhalter UNVERSTAENDLICH zurück; das Gespräch läuft weiter, und der Empfang bittet, es zu wiederholen.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components import stt

from . import DOMAIN, GERAET, STT_QUELLE, UNVERSTAENDLICH

_LOGGER = logging.getLogger(__name__)
ZEIT = 40  # s; der Ton eines Satzes läuft bis zu 15 s ein, dazu die Erkennung


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EmpfangSTT()])


class EmpfangSTT(stt.SpeechToTextEntity):
    _attr_name = "Empfang (Grok, fängt Unverständliches ab)"
    _attr_unique_id = f"{DOMAIN}_stt"
    _attr_device_info = GERAET

    def __init__(self) -> None:
        self.entity_id = "stt.empfang"

    def _quelle(self):
        return stt.async_get_speech_to_text_entity(self.hass, STT_QUELLE)

    def _von_quelle(self, name: str, sonst: list):
        q = self._quelle()
        return list(getattr(q, name)) if q is not None else sonst

    @property
    def supported_languages(self) -> list[str]:
        return self._von_quelle("supported_languages", ["de-DE", "de", "en-US", "en"])

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        return self._von_quelle("supported_formats", [stt.AudioFormats.WAV])

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        return self._von_quelle("supported_codecs", [stt.AudioCodecs.PCM])

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        return self._von_quelle("supported_bit_rates", [stt.AudioBitRates.BITRATE_16])

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        return self._von_quelle("supported_sample_rates", [stt.AudioSampleRates.SAMPLERATE_16000])

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        return self._von_quelle("supported_channels", [stt.AudioChannels.CHANNEL_MONO])

    async def async_process_audio_stream(self, metadata, stream) -> stt.SpeechResult:
        grund = ""
        try:
            quelle = self._quelle()
            if quelle is None:
                grund = "Erkennung %s fehlt" % STT_QUELLE
            else:
                ergebnis = await asyncio.wait_for(quelle.async_process_audio_stream(metadata, stream), ZEIT)
                if ergebnis.result == stt.SpeechResultState.SUCCESS and (ergebnis.text or "").strip():
                    return ergebnis
                grund = "kein Text"
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001  jeder Fehler der fremden Erkennung heißt hier nur „nicht verstanden“
            grund = type(err).__name__
        _LOGGER.info("Erkennung ohne Ergebnis (%s): Das Gespräch läuft mit dem Platzhalter weiter", grund)
        return stt.SpeechResult(UNVERSTAENDLICH, stt.SpeechResultState.SUCCESS)
