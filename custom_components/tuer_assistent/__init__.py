"""Tür-Assistent („Empfang“): drei eigene Werkzeuge für den Gesprächsagenten an der Haustür, ein Dienst zum Auflegen, Grok Voice als
eigene Innenstation (`sprache.py`), der Sensor „Empfang Störung“ (`binary_sensor.py`) und drei Entitäten für die Sprachkette des
Text-Agenten (`stt.py`: Erkennung ohne Text; `conversation.py`: KI ohne Antwort, Mitschrift; `tts.py`: Stimme von Grok mit selbst
erkannter Sprache, Katja als Ersatz; derzeit ungenutzt, sie gehören zum Weg über einen VoIP Stack).

Wozu: Der Empfang spricht mit Fremden. Er darf im Haus nichts schalten und keinen Zustand lesen, soll aber dem Bewohner Bescheid geben,
eine Nachricht weitergeben und auflegen können (Wort des Betreibers vom 10.11.2026: „Mach die Integration, dass mein Handy da klingelt“).
Die Werkzeuge von Home Assistant („Assist“) gibt es nur im Ganzen, mit allen freigegebenen Geräten. Darum hier eine eigene, enge
Werkzeugliste, die ein Gesprächsagent statt „Assist“ wählt (in SuperGrok: „Home Assistant steuern“ → „Tür-Assistent“).

Was ein Werkzeug tut: Es feuert das Ereignis `tuer_assistent_werkzeug` mit dem Namen des Werkzeugs und seinen Textfeldern. Mehr nicht.
Was daraus folgt (Handy, Auflegen), steht in der Automation `automations/tuer_assistent_werkzeuge.json`; dort lässt es sich ändern.
- bewohner_rufen(anliegen): ein Besucher möchte zu Herrn Muster.
- nachricht_weitergeben(fuer, nachricht): ein Besucher hinterlässt eine Nachricht, oder ein Zusteller meldet ein abgegebenes Paket.
- auflegen(): der Besucher hat sich verabschiedet.

Der Dienst `tuer_assistent.auflegen` beendet das laufende Gespräch des Empfangs; die Automation ruft ihn. Der VoIP Stack hat
dafür keinen öffentlichen Dienst: `voip_stack.hangup` nimmt nur Rufe, die einer Automation oder einem Telefon in der Oberfläche
gehören, und antwortet bei einem Ruf des Assistenten „belongs to another phone endpoint“ (11.11.2026 gemessen). Darum nimmt der
Dienst denselben Weg, den `voip_stack.hangup` für Rufe einer Automation selbst geht (`request_termination` am Ruf-Register), und
greift dafür auf zwei Namen im Inneren des VoIP Stack zu. Ändert ein Update sie, legt der Dienst nicht mehr auf, meldet das im Log
und in `tuer_assistent.stand` (Attribut `auflegen`), und sonst geschieht nichts: Die Türstation beendet jeden Ruf nach 2 min selbst.

Das schnelle Modell ruft ein Werkzeug gern mehrfach hintereinander (am 10.11.2026 zehnmal `auflegen` in einer Antwort, bis SuperGrok
abbrach). Darum sagt jedes Ergebnis dem Modell, dass es jetzt antworten und kein Werkzeug mehr rufen soll, und derselbe Aufruf mit
denselben Feldern feuert binnen 20 s nur einmal ein Ereignis.

Gegen Missbrauch (Wort des Betreibers vom 10.11.2026: „Stelle sicher, dass man nicht Hacking betreiben kann“): Ein Besucher kann die KI
überreden, Werkzeuge zu rufen. Darum gibt es hier nichts, was im Haus etwas bewirkt, und harte Grenzen, die nicht vom Modell
abhängen: höchstens 6 Ereignisse je Minute, je Feld 300 druckbare Zeichen, immer dasselbe Ergebnis.

Grenzen, mit Absicht: Die Werkzeuge rufen keinen Dienst und lesen keinen Zustand, als Antwort nur ein fester Satz. Was der Besucher
sagt, landet nur als Text im Ereignis (je Feld höchstens 300 Zeichen) und nie im Log. `tuer_assistent.stand` zeigt „aktiv“, das
zuletzt gerufene Werkzeug und, ob Auflegen möglich ist.
Der Sprachassistent „Tür“ nutzt als Erkennung `stt.empfang` und als Agenten `conversation.empfang`; beide reichen weiter
(STT_QUELLE; der Agent an den, der in `select.empfang_ki` gewählt ist). Werkzeuge und Anweisung bleiben beim Agenten dahinter.
Welche Agenten zur Wahl stehen, steht nur in configuration.yaml, je mit der Zeit in Sekunden, nach der die Ersatzantwort kommt:
    tuer_assistent:
      agenten:
        conversation.tur_assistent: 8
        conversation.tur_assistent_b: 15
So lässt sich ein zweites Modell oder ein anderer Anbieter am echten Klingeln vergleichen, ohne den Sprachassistenten umzustellen
(Wort des Betreibers vom 11.11.2026: „Lass uns zwei machen, dann kann man sie hin und her testen“). Die Liste ist die Grenze: Ein Agent mit den
Werkzeugen von Home Assistant gehört nie hinein, denn wer hier steht, spricht mit Fremden. Jeder Agent der Liste braucht dieselbe
Anweisung und als Werkzeuge nur „Tür-Assistent“.
Grok Voice (Sprache zu Sprache, `sprache.py`; seit 11.11.2026): Steht in configuration.yaml
    tuer_assistent:
      grok_voice:
        schluessel: !secret xai_api_key
        station: !secret vto_eg_adresse
        passwort: !secret vto_9904_passwort
meldet sich die Integration selbst als Innenstation 9904 an der Station EG an (kennung, port 5062, station_port 5060 und stimme eve
wählbar; `mitschrift_speichern: false` hält die Mitschriften aus dem Tagebuch heraus) und nimmt deren Rufe an; einen Ersatzweg gibt
es nicht (sein Wort vom 11.11.2026 abends: „wenn es kaputt geht, dann bleibt es
halt kaputt“). `tuer_assistent.auflegen` beendet auch dieses Gespräch.
Nachsehen: `tuer_assistent.stand` (Anmeldung, xAI, letzter Ruf), der Sensor „Empfang Störung“, Einstellungen → Reparaturen (Schlüssel,
Anmeldung), das Tagebuch der letzten Rufe in `.storage/tuer_assistent.rufe` und die Diagnose am Eintrag (`diagnostics.py`, ohne
Mitschriften, Namen und Schlüssel). Was von der Qualitätsskala von Home Assistant hier gilt und was nicht: `quality_scale.yaml`.
Einbinden: Ordner nach /config/custom_components/tuer_assistent, in configuration.yaml die Zeile „tuer_assistent:“, Neustart (der
Eintrag unter „Geräte & Dienste“ entsteht dabei von selbst). Entfernen: erst im Sprachassistenten „Tür“ wieder die Erkennung und den
Agenten von SuperGrok wählen und bei diesem die Werkzeugliste abwählen, dann Eintrag und Zeile löschen, Neustart.
"""
from __future__ import annotations

import logging
import sys

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

DOMAIN = "tuer_assistent"
EREIGNIS = "tuer_assistent_werkzeug"
MITSCHRIFT = "tuer_assistent_gespraech"
STT_QUELLE = "stt.grok_voice_stt"
TTS_QUELLE = "tts.grok_voice_tts"
TTS_STIMME = "eve"
TTS_ERSATZ = ("tts.home_assistant_cloud", "de-DE", {"voice": "KatjaNeural"})
KI_QUELLE = "conversation.tur_assistent"
UNVERSTAENDLICH = "(unverständlich)"  # steht so auch in der Anweisung
WAHL = "select.empfang_ki"
ZEIT = 8  # s bis zur Ersatzantwort, wenn configuration.yaml nichts nennt
PLATTFORMEN = ["stt", "conversation", "select", "tts", "binary_sensor"]
STAND = f"{DOMAIN}.stand"
# Ein Gerät (Dienst) für alle Entitäten: eine Seite mit Zustand, Wahl der KI und dem Knopf „Diagnose herunterladen“.
GERAET = DeviceInfo(identifiers={(DOMAIN, "empfang")}, name="Empfang", manufacturer="ilihack", model="Tür-Assistent (Grok Voice)",
                    entry_type=DeviceEntryType.SERVICE)
LAENGE = 300
SPERRE = 20  # s, in denen derselbe Aufruf kein zweites Ereignis feuert
EINMAL = 3  # s, in denen dasselbe Werkzeug auch mit anderen Feldern kein zweites Ereignis feuert (ein Aufruf je Antwort)
JE_MINUTE = 6  # Ereignisse aller Werkzeuge zusammen
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.All(lambda v: v or {}, vol.Schema({
    vol.Optional("agenten"): vol.All(vol.Schema({cv.entity_domain("conversation"): vol.All(vol.Coerce(float), vol.Range(min=2, max=60))}),
                                     vol.Length(min=1)),
    vol.Optional("grok_voice"): vol.Schema({vol.Required("schluessel"): cv.string, vol.Required("station"): cv.string,
                                            vol.Required("passwort"): cv.string, vol.Optional("kennung", default="9904"): cv.string,
                                            vol.Optional("port", default=5062): cv.port, vol.Optional("station_port", default=5060): cv.port,
                                            vol.Optional("stimme", default="eve"): cv.string,
                                            vol.Optional("mitschrift_speichern", default=True): cv.boolean}),
}))}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)

# Name, Beschreibung für das Modell, Textfelder, Ergebnis für das Modell
WEITER = " Rufe jetzt kein Werkzeug mehr auf, sondern antworte dem Besucher mit dem vorgesehenen Satz."
WERKZEUGE = (
    ("bewohner_rufen",
     "Gibt Herrn Muster Bescheid, dass ein Besucher zu ihm möchte. Nur verwenden, wenn das Anliegen des Besuchers Herrn Muster gilt. "
     "anliegen: in wenigen Worten, wer da ist und was er möchte.",
     ("anliegen",), "Herr Muster hat Bescheid bekommen."),
    ("nachricht_weitergeben",
     "Gibt eine Nachricht des Besuchers an Herrn Muster weiter, auch die Meldung eines Zustellers über eine Sendung für ihn. Nur für "
     "Herrn Muster, nie für andere Bewohner. fuer: Herr Muster. nachricht: die Nachricht in den Worten des Besuchers.",
     ("fuer", "nachricht"), "Die Nachricht ist weitergegeben."),
    ("auflegen",
     "Beendet das Gespräch. Nur verwenden, wenn der Besucher sich mit Tschüss, Auf Wiedersehen oder Ähnlichem verabschiedet hat, "
     "und nie zusammen mit einem anderen Werkzeug.",
     (), "Das Gespräch wird gleich beendet."),
)


VOIP = "custom_components.voip_stack."


def agenten(hass: HomeAssistant) -> dict[str, float]:
    """Die Agenten, an die der Empfang weiterreichen darf (aus configuration.yaml), je mit ihrer Zeitgrenze."""
    return (hass.data.get(DOMAIN) or {}).get("agenten") or {KI_QUELLE: ZEIT}


def gewaehlt(hass: HomeAssistant) -> tuple[str, float]:
    """Der in select.empfang_ki gewählte Agent, wenn er in der Liste steht; sonst der erste der Liste."""
    liste = agenten(hass)
    wahl = hass.states.get(WAHL)
    name = wahl.state if wahl is not None and wahl.state in liste else next(iter(liste))
    return name, liste[name]


def _voip():
    """Ruf-Register und Beenden-Absicht des VoIP Stack, oder (None, None). Kein import: Ist er geladen, stehen sie in sys.modules."""
    return (getattr(sys.modules.get(VOIP + "endpoint_lifecycle"), "call_registry", None),
            getattr(sys.modules.get(VOIP + "endpoint_session"), "TerminationIntent", None))


def auflegen(hass: HomeAssistant) -> str:
    """Beendet jedes laufende Gespräch mit dem Assistenten der Nebenstelle und das von Grok Voice; sagt, was geschah. Wirft nie."""
    bruecke = (hass.data.get(DOMAIN) or {}).get("bruecke")
    try:
        grok_voice = bool(bruecke and bruecke.auflegen())
    except Exception:  # noqa: BLE001
        grok_voice = False
    register, absicht = _voip()
    if register is None or absicht is None:  # ohne VoIP Stack (abgeschaltet, seit es Grok Voice als eigene Innenstation gibt)
        if grok_voice:
            return "aufgelegt (Grok Voice)"
        return "kein Gespräch" if bruecke is not None else "nicht möglich: VoIP Stack nicht geladen oder geändert"
    try:
        reg = register(hass)
        rufe = [s for s in list(reg.calls.values()) if s.route_kind == "assist" and s.live]
        for s in rufe:
            reg.request_termination(s.call_id, absicht("local_hangup"), generation=s.generation)
    except Exception as err:  # noqa: BLE001  fremdes Inneres: jede Abweichung heißt nur „legt nicht auf“
        return "nicht möglich: %s" % type(err).__name__
    return "aufgelegt" if rufe or grok_voice else "kein Gespräch"


def _stand(hass: HomeAssistant, plus: int = 0, **neu) -> None:
    """Schreibt tuer_assistent.stand fort; `plus` zählt die Aufrufe hoch."""
    alt = hass.states.get(STAND)
    attr = {"friendly_name": "Tür-Assistent Werkzeuge", "werkzeuge": [w[0] for w in WERKZEUGE], "zuletzt": "", "zuletzt_um": "",
            "aufrufe": 0, "auflegen": "", **(dict(alt.attributes) if alt else {}), **neu}
    attr["aufrufe"] = int(attr["aufrufe"] or 0) + plus
    hass.states.async_set(STAND, "aktiv", attr)


class Werkzeug(llm.Tool):
    """Ein Werkzeug, das nur ein Ereignis feuert."""

    integration = DOMAIN

    def __init__(self, name: str, beschreibung: str, felder: tuple[str, ...], ergebnis: str) -> None:
        self.name = name
        self.description = beschreibung
        self.felder = felder
        self.ergebnis = ergebnis
        self.parameters = vol.Schema({vol.Optional(f, default=""): cv.string for f in felder})

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext):
        daten = {"werkzeug": self.name}
        for f in self.felder:
            roh = "".join(z if z.isprintable() else " " for z in str(tool_input.tool_args.get(f) or ""))
            daten[f] = " ".join(roh.split())[:LAENGE]
        merk = hass.data.setdefault(DOMAIN, {"letzte": {}, "zeiten": []})
        letzte, zeiten = merk["letzte"], merk["zeiten"]
        jetzt = dt_util.utcnow().timestamp()
        schluessel = tuple(daten.items())
        doppelt = jetzt - letzte.get(schluessel, 0) < SPERRE or jetzt - letzte.get(self.name, 0) < EINMAL
        letzte[schluessel] = jetzt
        if not doppelt:
            letzte[self.name] = jetzt
        for k in [k for k, t in letzte.items() if jetzt - t > 10 * SPERRE]:
            del letzte[k]
        zeiten[:] = [t for t in zeiten if jetzt - t < 60]
        zuviel = len(zeiten) >= JE_MINUTE
        if not doppelt and not zuviel:
            zeiten.append(jetzt)
            hass.bus.async_fire(EREIGNIS, daten)
        _stand(hass, plus=1, zuletzt=self.name, zuletzt_um=dt_util.now().isoformat(timespec="seconds"))
        _LOGGER.info("Werkzeug %s aufgerufen%s", self.name, " (kein Ereignis: doppelt)" if doppelt else " (kein Ereignis: mehr als %d je Minute)" % JE_MINUTE if zuviel else "")
        ergebnis = {"ergebnis": self.ergebnis + WEITER}
        # Ab Home Assistant 2026.10 erwartet der Kern ein ToolResult (ein bloßes dict geht nur noch bis 2027.11).
        return llm.ToolResult(data=ergebnis) if hasattr(llm, "ToolResult") else ergebnis


class TuerAPI(llm.API):
    """Die Werkzeugliste, wie sie ein Gesprächsagent wählen kann."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass=hass, id=DOMAIN, name="Tür-Assistent")

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        return llm.APIInstance(api=self, api_prompt="", llm_context=llm_context,
                               tools=[Werkzeug(*w) for w in WERKZEUGE])


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    llm.async_register_api(hass, TuerAPI(hass))
    _stand(hass)
    hass.data.setdefault(DOMAIN, {"letzte": {}, "zeiten": []})["agenten"] = dict((config.get(DOMAIN) or {}).get("agenten") or {KI_QUELLE: ZEIT})

    async def dienst(call: ServiceCall) -> None:
        """Ohne Gespräch geschieht nichts; nur wenn Auflegen gar nicht geht, ein Fehler (die Automation ruft mit continue_on_error)."""
        ergebnis = auflegen(hass)
        _stand(hass, auflegen=ergebnis)
        _LOGGER.log(logging.WARNING if ergebnis.startswith("nicht") else logging.INFO, "Auflegen: %s", ergebnis)
        if ergebnis.startswith("nicht"):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="auflegen_nicht_moeglich",
                                     translation_placeholders={"grund": ergebnis.removeprefix("nicht möglich: ")})

    hass.services.async_register(DOMAIN, "auflegen", dienst, schema=vol.Schema({}))

    if gv := (config.get(DOMAIN) or {}).get("grok_voice"):
        from .sprache import async_starten

        hass.data[DOMAIN]["grok_voice"] = True
        bruecke = await async_starten(hass, gv)
        hass.data[DOMAIN]["bruecke"] = bruecke
        _stand(hass, grok_voice="meldet sich an" if bruecke else "nicht gestartet (Log)")
        if bruecke is not None:
            async def anhalten(_event) -> None:
                await bruecke.stoppen()

            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, anhalten)
    else:
        _stand(hass, grok_voice="aus (kein Schlüssel in configuration.yaml)")

    async def pruefen(_event) -> None:
        """Nach dem Start: Sind die zwei Namen des VoIP Stack noch da? (wartung.py stand liest das Attribut.)"""
        bereit = hass.data[DOMAIN].get("bruecke") is not None or all(_voip())
        _stand(hass, auflegen="bereit" if bereit else "nicht möglich: VoIP Stack nicht geladen oder geändert")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, pruefen)
    async def eintrag() -> None:
        """Legt beim ersten Start den Eintrag an, über den Home Assistant die zwei Entitäten annimmt."""
        try:
            await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data={})
        except Exception:  # noqa: BLE001  ohne Eintrag bleiben Werkzeuge und Dienst trotzdem da
            _LOGGER.warning("Eintrag für die Entitäten des Empfangs nicht angelegt", exc_info=True)

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(eintrag())
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Die zwei Entitäten des Empfangs (Erkennung und Agent mit Auffangnetz)."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATTFORMEN)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATTFORMEN)
