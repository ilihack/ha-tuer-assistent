"""Gesprächsagent „Empfang“: reicht jede Nachricht an den Agenten von Grok weiter, fängt dessen Ausfall ab und meldet die Mitschrift.

Warum: Antwortet xAI nicht oder zu spät, wirft SuperGrok einen Fehler, und der VoIP Stack legt sofort stumm auf. Dieser Agent antwortet
dann mit einem festen Satz, den die Stimme noch vorlesen kann; der Besucher weiß, woran er ist, und das Gespräch bleibt bestehen.
Er hat selbst keine Werkzeuge und kein Modell. Werkzeuge und Anweisung bleiben beim Agenten dahinter; welcher das ist, sagt
`select.empfang_ki` (nur Agenten aus configuration.yaml, siehe `__init__.py`).
Schreibt das Modell ein Werkzeug als Text in die Antwort, statt es aufzurufen (Gemini Lite einmal in 60 Antworten, 11.11.2026:
„nachricht_weitergeben(fuer: …)“), würde die Stimme das vorlesen; dann sagt er stattdessen, der Besucher möge es wiederholen.
Antwortet das Modell ohne Text und ohne Werkzeug (Gemini Lite auf „Tschüss.“ zweimal in vier Läufen, 11.11.2026 abends), hörte der
Besucher nichts; dann fragt er es ein zweites Mal (in derselben Zeitgrenze) und bittet erst danach um Wiederholung.
Nebenbei feuert er je Wortwechsel das Ereignis `tuer_assistent_gespraech` (was die Erkennung verstand, was geantwortet wurde, wie
lange es dauerte); `automations/tuer_assistent_mitschrift.json` schickt es aufs Handy, solange der Schalter dafür an ist.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import re
import time

from homeassistant.components import conversation
from homeassistant.helpers import intent

from . import DOMAIN, GERAET, LAENGE, MITSCHRIFT, STAND, gewaehlt

_LOGGER = logging.getLogger(__name__)
WERKZEUG_ALS_TEXT = re.compile(r"bewohner_rufen|nachricht_weitergeben|\bauflegen\s*\(")
NOCHMAL = {"de": "Entschuldigung, sagen Sie das bitte noch einmal?", "en": "Sorry, could you say that again?"}
ERSATZ = {
    "de": "Entschuldigung, ich habe gerade keine Verbindung. Bitte drücken Sie direkt den Klingelknopf der Wohnung.",
    "en": "Sorry, I have no connection right now. Please press the bell button of the apartment directly.",
}


def _gesagt(ergebnis) -> str:
    return str(((ergebnis.response.speech or {}).get("plain") or {}).get("speech") or "")


def _sprache(user_input) -> str:
    return "en" if str(user_input.language or "").lower().startswith("en") else "de"


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EmpfangAgent()])


class EmpfangAgent(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "agent"
    _attr_entity_registry_enabled_default = False  # gehört zum Weg über einen VoIP Stack; für Grok Voice nicht nötig
    _attr_unique_id = f"{DOMAIN}_agent"
    _attr_device_info = GERAET

    def __init__(self) -> None:
        self.entity_id = "conversation.empfang"

    @property
    def supported_languages(self):
        return "*"

    def _quelle(self, name: str):
        from homeassistant.components.conversation.const import DATA_COMPONENT

        return self.hass.data[DATA_COMPONENT].get_entity(name)

    def _aufrufe(self) -> int:
        stand = self.hass.states.get(STAND)
        return int((stand.attributes.get("aufrufe") if stand else 0) or 0)

    def _zuletzt(self) -> str:
        stand = self.hass.states.get(STAND)
        return str(stand.attributes.get("zuletzt") or "") if stand else ""

    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        beginn, grund, ergebnis = time.monotonic(), "", None
        aufrufe = self._aufrufe()
        name, zeit = gewaehlt(self.hass)
        try:
            quelle = self._quelle(name)
            if quelle is None:
                grund = "Agent %s fehlt" % name
            else:
                quelle.async_set_context(user_input.context)
                verarbeiten = getattr(quelle, "internal_async_process", None) or quelle.async_process
                eingabe = dataclasses.replace(user_input, agent_id=name)
                for versuch in (1, 2):
                    # Eigene Aufgabe und nicht wait_for: Das wartet nach Ablauf der Zeit, bis die abgebrochene Anfrage wirklich endet.
                    # Hier zählt, dass der Besucher nach der Zeitgrenze eine Antwort hört, auch wenn die Anfrage noch hängt. Beide
                    # Versuche zusammen haben diese Zeit.
                    aufgabe = asyncio.ensure_future(verarbeiten(eingabe))
                    try:
                        fertig, _ = await asyncio.wait({aufgabe}, timeout=max(0.0, zeit - (time.monotonic() - beginn)))
                    finally:
                        if not aufgabe.done():
                            aufgabe.cancel()
                    if not fertig:
                        grund, ergebnis = "keine Antwort in %g s" % zeit, None
                        break
                    ergebnis = aufgabe.result()
                    if ergebnis.response.response_type == intent.IntentResponseType.ERROR:
                        grund, ergebnis = "Fehlerantwort", None
                        break
                    gesagt = _gesagt(ergebnis)
                    if WERKZEUG_ALS_TEXT.search(gesagt):
                        grund = "Werkzeug als Text"
                        _LOGGER.warning("Werkzeug als Text in der Antwort, statt dessen Bitte um Wiederholung")
                        ergebnis.response.async_set_speech(NOCHMAL[_sprache(user_input)])
                        break
                    if gesagt.strip() or self._aufrufe() != aufrufe:  # ohne Text nach einem Werkzeug: so lassen, kein zweites Werkzeug
                        break
                    if versuch == 2:
                        grund = "leere Antwort"
                        ergebnis.response.async_set_speech(NOCHMAL[_sprache(user_input)])
                    else:
                        _LOGGER.warning("Leere Antwort von %s, frage noch einmal", name)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001  jeder Fehler des fremden Agenten heißt hier nur „Ersatzantwort“
            grund = type(err).__name__
        if ergebnis is None:
            _LOGGER.warning("Ersatzantwort: %s", grund)
            antwort = intent.IntentResponse(language=user_input.language)
            antwort.async_set_speech(ERSATZ[_sprache(user_input)])
            ergebnis = conversation.ConversationResult(response=antwort, conversation_id=user_input.conversation_id)
        try:
            gesagt = _gesagt(ergebnis)
            self.hass.bus.async_fire(MITSCHRIFT, {
                "besucher": " ".join(str(user_input.text or "").split())[:LAENGE], "empfang": " ".join(str(gesagt).split())[:LAENGE],
                "sekunden": round(time.monotonic() - beginn, 1), "ersatz": grund,
                "werkzeug": self._zuletzt() if self._aufrufe() != aufrufe else "", "ki": name.split(".", 1)[-1],
                "gespraech": str(ergebnis.conversation_id or user_input.conversation_id or "")[-6:]})
        except Exception:  # noqa: BLE001  die Mitschrift darf das Gespräch nie stören
            _LOGGER.debug("Mitschrift nicht gefeuert", exc_info=True)
        return ergebnis
