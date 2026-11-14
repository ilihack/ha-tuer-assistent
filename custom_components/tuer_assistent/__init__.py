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
- bewohner_rufen(anliegen): ein Besucher möchte zum Bewohner (sein Name kommt aus den Einstellungen, Feld „Bewohner“, nicht aus dem Code).
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
Grok Voice (Sprache zu Sprache, `sprache.py`; seit 11.11.2026): Mit den Einstellungen am Eintrag (Einstellungen → Geräte & Dienste →
Tür-Assistent → Konfigurieren, `config_flow.py`) meldet sich die Integration selbst als Innenstation an der Türstation an und nimmt
deren Rufe an; einen Ersatzweg gibt es nicht (sein Wort vom 11.11.2026 abends: „wenn es kaputt geht, dann bleibt es halt kaputt“).
`tuer_assistent.auflegen` beendet auch dieses Gespräch.
Einstellungen (seit 2.6.0; sein Wort vom 14.11.2026: „die Integration braucht eine konfigurierbare Oberfläche, und dort können wir
unsere Instruction reinladen und auch die Klartextnamen, vielleicht weiter oben, damit man sie dann schnell editieren kann. Dann können
wir die Helper löschen“): oben der Bewohner mit Anrede und die Angaben (je Zeile `name: wert`, etwa die Namen der anderen Klingeln);
darunter die Begrüßung und die Anweisung als Text (Vorlagen; die Vorgaben stehen in `vorgabe.py` und gelten, solange dort kein
eigener Text steht), xAI (Schlüssel, Modell, Stimme, Stichwörter für die Erkennung) und die Türstation (Adresse, Nebenstelle,
Passwort, Ports); zuletzt „Mitschrift speichern“. Helfer braucht die Integration keine. Bewohner, Angaben, Begrüßung und Anweisung liest jeder Ruf frisch; ändert sich etwas an der Verbindung (VERBINDUNG),
lädt der Eintrag neu: Grok Voice hält an (ein laufender Ruf endet) und startet neu, ohne Neustart von Home Assistant. Der Block
`grok_voice:` unter `tuer_assistent:` in configuration.yaml (Schlüssel, Station, Passwort …) gilt nur, solange der Eintrag keine
Einstellungen hat: Dann übernimmt er die Werte einmal, danach wird der Block ignoriert; solange er dasteht, sagt ein Hinweis unter
Reparaturen, dass er weg kann. Ohne Schlüssel, Station und Passwort bleibt Grok Voice aus.
Nachsehen: `tuer_assistent.stand` (Anmeldung, xAI, letzter Ruf), der Sensor „Empfang Störung“, Einstellungen → Reparaturen (Schlüssel,
Anmeldung), das Tagebuch der letzten Rufe in `.storage/tuer_assistent.rufe` und die Diagnose am Eintrag (`diagnostics.py`, ohne
Mitschriften, Namen und Schlüssel). Was von der Qualitätsskala von Home Assistant hier gilt und was nicht: `quality_scale.yaml`.
Einbinden: Ordner nach /config/custom_components/tuer_assistent, Neustart, dann „Integration hinzufügen“ → Tür-Assistent (führt gleich
in die Einstellungen); die Zeile „tuer_assistent:“ in configuration.yaml legt den Eintrag ebenso an und trägt die Agentenliste der
Text-Strecke. Entfernen: erst im Sprachassistenten „Tür“ wieder die Erkennung und den Agenten von SuperGrok wählen und bei diesem die
Werkzeugliste abwählen, dann Eintrag und Zeile löschen, Neustart.
"""
from __future__ import annotations

from collections.abc import Mapping
import logging
import re
import sys

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir, llm
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
# Vorgaben der Einstellungen, für configuration.yaml und die Maske in config_flow.py (die Texte stehen in vorgabe.py)
VORGABEN = {"kennung": "9904", "port": 5062, "station_port": 5060, "stimme": "eve", "modell": "grok-voice-latest",
            "mitschrift_speichern": True, "anrede": "Herr"}
ANREDEN = ("Herr", "Frau", "Familie", "ohne")  # wie die Werkzeuge den Bewohner nennen: „Herrn Muster“, „Frau Muster“, „Familie Muster“, ohne: der ganze Name
PFLICHT = ("schluessel", "station", "passwort")  # ohne sie bleibt Grok Voice aus
# Ändert sich davon etwas, startet Grok Voice neu (der Eintrag lädt neu); alles andere liest jeder Ruf frisch aus den Einstellungen.
VERBINDUNG = ("schluessel", "station", "kennung", "passwort", "port", "station_port", "stimme", "modell", "mitschrift_speichern")
RESERVIERT = ("bewohner", "anrede", "begruessung", "grok_voice")  # Variablen der Anweisung, die nicht aus dem Feld „Angaben“ kommen
AUS = "aus (nicht eingerichtet)"
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.All(lambda v: v or {}, vol.Schema({
    vol.Optional("agenten"): vol.All(vol.Schema({cv.entity_domain("conversation"): vol.All(vol.Coerce(float), vol.Range(min=2, max=60))}),
                                     vol.Length(min=1)),
    vol.Optional("grok_voice"): vol.Schema({vol.Required("schluessel"): cv.string, vol.Required("station"): cv.string,
                                            vol.Required("passwort"): cv.string, vol.Optional("kennung", default=VORGABEN["kennung"]): cv.string,
                                            vol.Optional("port", default=VORGABEN["port"]): cv.port,
                                            vol.Optional("station_port", default=VORGABEN["station_port"]): cv.port,
                                            vol.Optional("stimme", default=VORGABEN["stimme"]): cv.string,
                                            vol.Optional("mitschrift_speichern", default=VORGABEN["mitschrift_speichern"]): cv.boolean}),
}))}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)

# Name, Beschreibung für das Modell, Textfelder, Ergebnis für das Modell. Der Bewohner steht nicht im Code (sein Wort vom 12.11.2026:
# „Namen sollen generell sowieso nicht fest drin stehen … wenn jemand Neues noch einzieht“): {dat}, {akk}, {nom} füllt werkzeuge() aus
# den Einstellungen (Felder „Bewohner“ und „Anrede“: „Herrn <Nachname>“), ohne Namen allgemein.
WEITER = " Rufe jetzt kein Werkzeug mehr auf, sondern antworte dem Besucher mit dem vorgesehenen Satz, in seiner Sprache."
WERKZEUGE = (
    ("bewohner_rufen",
     "Gibt {dat} Bescheid, dass jemand zu ihm möchte oder dass etwas für ihn wichtig ist. Nicht für Sendungen, die in die "
     "Paketbox kommen. anliegen: auf Deutsch, in wenigen Worten, wer da ist und was er möchte.",
     ("anliegen",), "{Nom} hat Bescheid bekommen."),
    ("nachricht_weitergeben",
     "Gibt eine Nachricht des Besuchers an {akk} weiter, auch die Meldung eines Zustellers, dass er eine Sendung für ihn "
     "abgegeben hat, selbst wenn er sich dabei verabschiedet. Nur für {akk}, nie für andere Bewohner. fuer: {nom}. "
     "nachricht: die Nachricht auf Deutsch, sinngetreu in den Worten des Besuchers.",
     ("fuer", "nachricht"), "Die Nachricht ist weitergegeben."),
    ("auflegen",
     "Beendet das Gespräch. Nur verwenden, wenn der Besucher sich verabschiedet hat (Tschüss, Auf Wiedersehen oder Ähnliches, in "
     "jeder Sprache) und nichts an {akk} weiterzugeben ist, und nie zusammen mit einem anderen Werkzeug.",
     (), "Das Gespräch wird gleich beendet."),
)


def einstellungen(hass: HomeAssistant) -> Mapping:
    """Die Einstellungen des Eintrags (seine Optionen, config_flow.py); leer, solange es keinen gibt."""
    eintraege = hass.config_entries.async_entries(DOMAIN)
    return eintraege[0].options if eintraege else {}


def sauber(wert: object, laenge: int = 200) -> str:
    """Text aus den Einstellungen für Anweisung und Werkzeuge: nur druckbare Zeichen, Leerraum zusammengezogen, begrenzt."""
    return " ".join("".join(z if z.isprintable() else " " for z in str(wert or "")).split())[:laenge]


def angaben_lesen(text: object) -> dict[str, str]:
    """Das Feld „Angaben“: je Zeile `name: wert` eine Variable der Anweisung (leere Zeilen und solche mit # zählen nicht). Wirft
    ValueError mit der Nummer der ersten Zeile, die nicht passt: kein Doppelpunkt, der Name kein einfacher Bezeichner, reserviert
    (RESERVIERT) oder doppelt."""
    aus: dict[str, str] = {}
    for nr, zeile in enumerate(str(text or "").splitlines(), 1):
        if not zeile.strip() or zeile.strip().startswith("#"):
            continue
        name, trenner, wert = zeile.partition(":")
        name = name.strip()
        if not trenner or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in RESERVIERT or name in aus:
            raise ValueError(str(nr))
        aus[name] = sauber(wert)
    return aus


def nachname(hass: HomeAssistant) -> str:
    """Nachname des Bewohners aus den Einstellungen (letztes Wort, nur Buchstaben, Ziffern und . , -); leer ohne Wert."""
    roh = re.sub(r"[^0-9A-Za-zÀ-ÿ .,-]", "", str(einstellungen(hass).get("bewohner") or ""))[:60].split()
    return roh[-1] if roh else ""


def werkzeuge(hass: HomeAssistant) -> list[tuple[str, str, tuple[str, ...], str]]:
    """Die drei Werkzeuge mit dem Bewohner aus den Einstellungen in der gewählten Anrede; ohne Namen „dem Bewohner“."""
    n = nachname(hass)
    anrede = einstellungen(hass).get("anrede") or VORGABEN["anrede"]
    if not n:
        f = {"dat": "dem Bewohner", "akk": "den Bewohner", "nom": "der Bewohner", "Nom": "Der Bewohner"}
    elif anrede == "Herr":
        f = {"dat": f"Herrn {n}", "akk": f"Herrn {n}", "nom": f"Herr {n}", "Nom": f"Herr {n}"}
    else:  # „Frau Muster“ und „Familie Muster“ bleiben in jedem Fall gleich; ohne Anrede der ganze Name
        voll = f"{anrede} {n}" if anrede in ("Frau", "Familie") else sauber(einstellungen(hass).get("bewohner"), 60)
        f = {"dat": voll, "akk": voll, "nom": voll, "Nom": voll}
    return [(name, text.format(**f), felder, ergebnis.format(**f)) for name, text, felder, ergebnis in WERKZEUGE]


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
        self.ohne = ""  # nach einem Aufruf: warum kein Ereignis gefeuert wurde (für den Ablauf im Tagebuch, sprache.py), sonst leer

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
        self.ohne = "doppelt" if doppelt else "mehr als %d je Minute" % JE_MINUTE if zuviel else ""
        _LOGGER.info("Werkzeug %s aufgerufen%s", self.name, " (kein Ereignis: %s)" % self.ohne if self.ohne else "")
        ergebnis = {"ergebnis": self.ergebnis + WEITER}
        # Ab Home Assistant 2026.10 erwartet der Kern ein ToolResult (ein bloßes dict geht nur noch bis 2027.11).
        return llm.ToolResult(data=ergebnis) if hasattr(llm, "ToolResult") else ergebnis


class TuerAPI(llm.API):
    """Die Werkzeugliste, wie sie ein Gesprächsagent wählen kann."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass=hass, id=DOMAIN, name="Tür-Assistent")

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        return llm.APIInstance(api=self, api_prompt="", llm_context=llm_context,
                               tools=[Werkzeug(*w) for w in werkzeuge(self.hass)])


async def _starten(hass: HomeAssistant, werte: Mapping | None, quelle: str) -> None:
    """Startet Grok Voice mit diesen Einstellungen neu (eine laufende Innenstation hält vorher sauber an); ohne Schlüssel, Station und
    Passwort bleibt es aus. `quelle` sagt der Diagnose, woher sie kommen."""
    await _stoppen(hass)
    if not werte or not all(werte.get(k) for k in PFLICHT):
        _stand(hass, grok_voice=AUS)
        return
    from .sprache import async_starten

    daten = hass.data[DOMAIN]
    daten["grok_voice"] = quelle
    try:
        bruecke = await async_starten(hass, dict(werte))
    except Exception:  # noqa: BLE001  ein Fehler beim Start legt nur Grok Voice still, nicht Werkzeuge, Dienst und Sensor „Empfang Störung“
        _LOGGER.warning("Grok Voice: Start gescheitert; ohne Grok Voice weiter", exc_info=True)
        bruecke = None
    daten["bruecke"] = bruecke
    if bruecke is None:
        _stand(hass, grok_voice="nicht gestartet (Log)")
    elif not bruecke.angemeldet:  # sonst steht schon „angemeldet als …“ da
        _stand(hass, grok_voice="meldet sich an")


async def _stoppen(hass: HomeAssistant, grund: str = "Einstellungen geändert oder Eintrag entladen") -> None:
    """Hält Grok Voice an, wenn es läuft oder laufen sollte; ein laufender Ruf endet mit diesem Grund."""
    daten = hass.data[DOMAIN]
    daten["grok_voice"] = ""
    if "bruecke" in daten:
        if (bruecke := daten.pop("bruecke")) is not None:
            await bruecke.stoppen(grund)
        _stand(hass, grok_voice="aus: " + grund)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    llm.async_register_api(hass, TuerAPI(hass))
    _stand(hass)
    daten = hass.data.setdefault(DOMAIN, {"letzte": {}, "zeiten": []})
    daten["agenten"] = dict((config.get(DOMAIN) or {}).get("agenten") or {KI_QUELLE: ZEIT})
    daten["yaml"] = (config.get(DOMAIN) or {}).get("grok_voice")  # gilt nur, solange der Eintrag keine Optionen hat (async_setup_entry)

    async def dienst(call: ServiceCall) -> None:
        """Ohne Gespräch geschieht nichts; nur wenn Auflegen gar nicht geht, ein Fehler (die Automation ruft mit continue_on_error)."""
        ergebnis = auflegen(hass)
        _stand(hass, auflegen=ergebnis)
        _LOGGER.log(logging.WARNING if ergebnis.startswith("nicht") else logging.INFO, "Auflegen: %s", ergebnis)
        if ergebnis.startswith("nicht"):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="auflegen_nicht_moeglich",
                                     translation_placeholders={"grund": ergebnis.removeprefix("nicht möglich: ")})

    hass.services.async_register(DOMAIN, "auflegen", dienst, schema=vol.Schema({}))

    async def anhalten(_event) -> None:
        await _stoppen(hass, "Home Assistant hält an")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, anhalten)

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

    if not hass.config_entries.async_entries(DOMAIN):  # ohne Eintrag (erster Start): Grok Voice aus configuration.yaml, bis er da ist
        await _starten(hass, daten["yaml"], "configuration.yaml")
        hass.async_create_task(eintrag())
    return True


def _verbindung(optionen: Mapping) -> dict:
    """Die Werte, mit denen Grok Voice läuft (fehlt einer, die Vorgabe): Daran erkennt _geaendert, ob ein Neustart nötig ist."""
    return {k: optionen.get(k, VORGABEN.get(k)) for k in VERBINDUNG}


async def _geaendert(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach geänderten Einstellungen: Nur wenn sich an der Verbindung etwas geändert hat, lädt der Eintrag neu (Grok Voice startet neu,
    ein laufender Ruf endet). Bewohner, Angaben, Begrüßung und Anweisung liest ohnehin jeder Ruf frisch."""
    if _verbindung(entry.options) != hass.data[DOMAIN].get("verbindung"):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Die Entitäten des Empfangs und Grok Voice mit den Optionen des Eintrags. Hat er noch keine, übernimmt er einmal den Block
    grok_voice aus configuration.yaml; danach gelten nur die Optionen (geändert in der Oberfläche, config_flow.py)."""
    yaml = hass.data[DOMAIN].get("yaml")
    if yaml and not entry.options:
        hass.config_entries.async_update_entry(entry, options=dict(yaml))
    hass.data[DOMAIN]["verbindung"] = _verbindung(entry.options)
    entry.async_on_unload(entry.add_update_listener(_geaendert))
    if yaml:  # übernommen oder ignoriert: Der Block kann weg (der Hinweis verschwindet beim ersten Start ohne ihn)
        ir.async_create_issue(hass, DOMAIN, "grok_voice_yaml", is_fixable=False, severity=ir.IssueSeverity.WARNING,
                              translation_key="grok_voice_yaml")
    else:
        ir.async_delete_issue(hass, DOMAIN, "grok_voice_yaml")
    await _starten(hass, entry.options, "Oberfläche")
    await hass.config_entries.async_forward_entry_setups(entry, PLATTFORMEN)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Auch beim Neuladen nach geänderten Optionen: Entitäten entladen, Grok Voice anhalten (ein laufender Ruf endet)."""
    if ok := await hass.config_entries.async_unload_platforms(entry, PLATTFORMEN):
        await _stoppen(hass)
    return ok
