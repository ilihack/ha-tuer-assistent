"""Tür-Assistent („Empfang“): Grok Voice von xAI spricht am obersten Knopf der Türstation mit Besuchern. Die Integration meldet sich
selbst als Innenstation an der Station an, nimmt deren Rufe an und verbindet sie mit der Echtzeit-Schnittstelle von xAI.

Aufbau (für jeden, der hier etwas ändert, Mensch oder KI; mehr in README.md):
- __init__.py      Einstellungen lesen, die drei Werkzeuge, die Dienste `auflegen` und `anruf_testen`, Start und Halt von Grok Voice.
- sprache.py       die Innenstation: Anmeldung (REGISTER), Rufe (INVITE, BYE), Ton (RTP), das Gespräch mit xAI, Wächter, Tagebuch.
- sip.py           reine Hilfen ohne Zustand: SIP-Nachrichten zerlegen und beantworten, SDP, RTP, Digest, Adressen im Hausnetz.
- weiterleitung.py die Weiterleitung aufs Telefon über einen eigenen SIP-Zugang (seit 2.8.0) und der Dienst `anruf_testen`.
- config_flow.py   die Maske (Einstellungen → Geräte & Dienste → Tür-Assistent → Konfigurieren).
- vorgabe.py       die mitgelieferte Begrüßung und Anweisung (Prompt, der ganze Kontext in einem Text, mit erfundenen Namen).
- binary_sensor.py der Sensor „Empfang Störung“; diagnostics.py die Diagnose zum Herunterladen.
- translations/, icons.json, services.yaml, quality_scale.yaml, brand/: Texte, Symbole, Dienst, Prüfliste, Symbol der Integration.
Regeln: Kein Name, keine Adresse und kein Schlüssel im Code; alles Persönliche steht in den Einstellungen des Eintrags, denn dieselben
Dateien liegen öffentlich auf GitHub. Was der Besucher sagt, steht nie im Log. Die Werkzeuge schalten nichts im Haus.

Wozu: Der Empfang spricht mit Fremden. Er darf im Haus nichts schalten und keinen Zustand lesen, soll aber dem Bewohner Bescheid geben,
eine Nachricht weitergeben und auflegen können (Wort des Betreibers vom 10.11.2026: „Mach die Integration, dass mein Handy da klingelt“).

Was ein Werkzeug tut: Es feuert das Ereignis `tuer_assistent_werkzeug` mit dem Namen des Werkzeugs und seinen Textfeldern. Mehr nicht.
Was daraus folgt (Handy, Auflegen), steht in einer Automation der Anlage; dort lässt es sich ändern. Einzige Ausnahme: Ist ein
SIP-Zugang eingetragen (weiterleitung.py) und ruft das Modell bewohner_rufen mit verbinden „ja“, ruft die Integration das Telefon
des Bewohners an; seine Tasten feuern `tuer_assistent_taste`, und was eine Taste bewirkt, steht wieder in einer Automation.
- bewohner_rufen(anliegen, verbinden): ein Besucher möchte zum Bewohner; verbinden „ja“, wenn er ihn selbst sprechen soll (wann, sagt
  die Anweisung; Wort des Betreibers vom 22.11.2026: „das mit dem Anruf darf grok selber entscheiden, auch auf weitere Satzarten, ich
  muss mit ihm reden, ich brauche deine Unterschrift“). Wer der Bewohner ist, steht nur in der Anweisung.
- nachricht_weitergeben(fuer, nachricht): ein Besucher hinterlässt eine Nachricht, oder ein Zusteller meldet ein abgegebenes Paket.
- auflegen(): der Besucher hat sich verabschiedet.

Gegen Missbrauch (Wort des Betreibers vom 10.11.2026: „Stelle sicher, dass man nicht Hacking betreiben kann“): Ein Besucher kann die KI
überreden, Werkzeuge zu rufen. Darum gibt es hier nichts, was im Haus etwas bewirkt, und harte Grenzen, die nicht vom Modell abhängen:
höchstens 6 Ereignisse je Minute, je Feld 300 druckbare Zeichen, derselbe Aufruf binnen 20 s und dasselbe Werkzeug binnen 3 s nur
einmal, immer dasselbe Ergebnis. Jedes Ergebnis sagt dem Modell, dass es jetzt antworten und kein Werkzeug mehr rufen soll (ein
schnelles Modell rief am 10.11.2026 zehnmal `auflegen` in einer Antwort).

Einstellungen (config_flow.py; Wort des Betreibers vom 14.11.2026: „die Integration braucht eine konfigurierbare Oberfläche, und dort
können wir unsere Instruction reinladen“; seit 2.9.0 ist die Anweisung der ganze Kontext in einem Text, sein Wort vom 22.11.2026:
„Man hat einmal diesen gigantischen Text, dann ist es auch universaler“): oben Begrüßung und Anweisung (Vorlagen; die Vorgaben in
vorgabe.py gelten, solange dort kein eigener Text steht), darunter xAI (Schlüssel, Modell, Stimme, Stichwörter), die Türstation
(Adresse, Nebenstelle, Passwort, Ports) und die Weiterleitung aufs Telefon (SIP-Zugang, Nummer); zuletzt „Mitschrift speichern“.
Begrüßung, Anweisung, Stichwörter und Weiterleitung liest jeder Ruf frisch; ändert sich etwas an der Verbindung (VERBINDUNG), lädt
der Eintrag neu: Grok Voice hält an (ein laufender Ruf endet) und startet neu, ohne Neustart von Home Assistant. Ohne Schlüssel,
Station und Passwort bleibt Grok Voice aus. Seit 2.7.0 ist das der einzige Weg (Wort des Betreibers vom 15.11.2026: „den alten Textweg
kannst du komplett entfernen“): keine Text-Agenten, keine Sprachkette, keine Zeile in configuration.yaml.

Nachsehen: `tuer_assistent.stand` (Anmeldung, xAI, Modell, letzter Ruf), der Sensor „Empfang Störung“, Einstellungen → Reparaturen
(Schlüssel, Anmeldung, Mitschriften), das Tagebuch der letzten Rufe in `.storage/tuer_assistent.rufe` und die Diagnose am Eintrag.
Einbinden: Ordner nach /config/custom_components/tuer_assistent, Neustart, „Integration hinzufügen“ → Tür-Assistent.
Entfernen: Eintrag löschen, Ordner und `.storage/tuer_assistent.rufe` löschen, Neustart.
"""
from __future__ import annotations

from collections.abc import Mapping
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

DOMAIN = "tuer_assistent"
EREIGNIS = "tuer_assistent_werkzeug"
MITSCHRIFT = "tuer_assistent_gespraech"
PLATTFORMEN = ["binary_sensor"]
STAND = f"{DOMAIN}.stand"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
# Ein Gerät (Dienst) für den Sensor: eine Seite mit Zustand und dem Knopf „Diagnose herunterladen“.
GERAET = DeviceInfo(identifiers={(DOMAIN, "empfang")}, name="Empfang", manufacturer="ilihack", model="Tür-Assistent (Grok Voice)",
                    entry_type=DeviceEntryType.SERVICE)
LAENGE = 300
SPERRE = 20  # s, in denen derselbe Aufruf kein zweites Ereignis feuert
EINMAL = 3  # s, in denen dasselbe Werkzeug auch mit anderen Feldern kein zweites Ereignis feuert (ein Aufruf je Antwort)
JE_MINUTE = 6  # Ereignisse aller Werkzeuge zusammen
# Vorgaben der Einstellungen für die Maske in config_flow.py (die Texte stehen in vorgabe.py)
VORGABEN = {"kennung": "9904", "port": 5062, "station_port": 5060, "stimme": "eve", "modell": "grok-voice-latest",
            "mitschrift_speichern": True}
PFLICHT = ("schluessel", "station", "passwort")  # ohne sie bleibt Grok Voice aus
# Ändert sich davon etwas, startet Grok Voice neu (der Eintrag lädt neu); alles andere liest jeder Ruf frisch aus den Einstellungen.
VERBINDUNG = ("schluessel", "station", "kennung", "passwort", "port", "station_port", "stimme", "modell", "mitschrift_speichern")
AUS = "aus (nicht eingerichtet)"
_LOGGER = logging.getLogger(__name__)

# Name, Beschreibung für das Modell, Textfelder, Ergebnis für das Modell. Der Bewohner steht nicht im Code und nicht in den Werkzeugen:
# wer er ist, sagt die Anweisung.
WEITER = " Rufe jetzt kein Werkzeug mehr auf, sondern antworte dem Besucher mit dem vorgesehenen Satz, in seiner Sprache."
WERKZEUGE = (
    ("bewohner_rufen",
     "Gibt dem Bewohner (für wen du arbeitest, steht in deiner Anweisung) Bescheid, dass jemand zu ihm möchte oder dass etwas für "
     "ihn wichtig ist. Nicht für Sendungen, die in die Paketbox kommen. anliegen: auf Deutsch, in wenigen Worten, wer da ist und was "
     "er möchte. verbinden: „ja“, wenn der Besucher ihn jetzt selbst am Telefon sprechen soll (wann, sagt deine Anweisung), sonst „nein“.",
     ("anliegen", "verbinden"), "Der Bewohner hat Bescheid bekommen."),
    ("nachricht_weitergeben",
     "Gibt eine Nachricht des Besuchers an den Bewohner weiter (für wen du arbeitest, steht in deiner Anweisung), auch die Meldung "
     "eines Zustellers, dass er eine Sendung für ihn abgegeben hat, selbst wenn er sich dabei verabschiedet. Nur für ihn, nie für "
     "andere Bewohner im Haus. fuer: sein Name. "
     "nachricht: die Nachricht auf Deutsch, sinngetreu in den Worten des Besuchers.",
     ("fuer", "nachricht"), "Die Nachricht ist weitergegeben."),
    ("auflegen",
     "Beendet das Gespräch. Nur verwenden, wenn der Besucher sich verabschiedet hat (Tschüss, Auf Wiedersehen oder Ähnliches, in "
     "jeder Sprache) und nichts an den Bewohner weiterzugeben ist, und nie zusammen mit einem anderen Werkzeug.",
     (), "Das Gespräch wird gleich beendet."),
)
# Mit eingetragenem SIP-Zugang (weiterleitung.py) und verbinden „ja“ ersetzt dieses Ergebnis das von bewohner_rufen; nimmt er nicht ab,
# sagt der Empfang NICHT_ERREICHT wörtlich (ohne Namen, er steht nur in der Anweisung) und das Gespräch geht weiter.
ERGEBNIS_WEITER = ("Der Bewohner wird jetzt angerufen. Sag dem Besucher in einem kurzen Satz, dass du ihn verbindest und er bitte "
                   "kurz warten soll.")
NICHT_ERREICHT = "Leider erreiche ich gerade niemanden. Sie können gern eine Nachricht hinterlassen."


def einstellungen(hass: HomeAssistant) -> Mapping:
    """Die Einstellungen des Eintrags (seine Optionen, config_flow.py); leer, solange es keinen gibt."""
    eintraege = hass.config_entries.async_entries(DOMAIN)
    return eintraege[0].options if eintraege else {}


def sauber(wert: object, laenge: int = 200) -> str:
    """Text aus den Einstellungen für Anweisung und Werkzeuge: nur druckbare Zeichen, Leerraum zusammengezogen, begrenzt."""
    return " ".join("".join(z if z.isprintable() else " " for z in str(wert or "")).split())[:laenge]


def werkzeuge(hass: HomeAssistant) -> list[tuple[str, str, tuple[str, ...], str]]:
    """Die drei Werkzeuge (fest; wer der Bewohner ist, steht in der Anweisung)."""
    return list(WERKZEUGE)


def auflegen(hass: HomeAssistant) -> str:
    """Beendet das laufende Gespräch von Grok Voice; sagt, was geschah. Wirft nie."""
    bruecke = (hass.data.get(DOMAIN) or {}).get("bruecke")
    if bruecke is None:
        return "nicht möglich: Grok Voice läuft nicht"
    try:
        return "aufgelegt" if bruecke.auflegen() else "kein Gespräch"
    except Exception as err:  # noqa: BLE001
        return "nicht möglich: %s" % type(err).__name__


def _stand(hass: HomeAssistant, plus: int = 0, **neu) -> None:
    """Schreibt tuer_assistent.stand fort; `plus` zählt die Aufrufe hoch."""
    alt = hass.states.get(STAND)
    attr = {"friendly_name": "Tür-Assistent Werkzeuge", "werkzeuge": [w[0] for w in WERKZEUGE], "zuletzt": "", "zuletzt_um": "",
            "aufrufe": 0, "auflegen": "", **(dict(alt.attributes) if alt else {}), **neu}
    attr["aufrufe"] = int(attr["aufrufe"] or 0) + plus
    hass.states.async_set(STAND, "aktiv", attr)


class Werkzeug:
    """Ein Werkzeug, das nur ein Ereignis feuert; sprache.py ruft es, wenn xAI es aufruft."""

    def __init__(self, name: str, beschreibung: str, felder: tuple[str, ...], ergebnis: str) -> None:
        self.name = name
        self.description = beschreibung
        self.felder = felder
        self.ergebnis = ergebnis
        self.ohne = ""  # nach einem Aufruf: warum kein Ereignis gefeuert wurde (für den Ablauf im Tagebuch, sprache.py), sonst leer

    async def rufen(self, hass: HomeAssistant, argumente: Mapping) -> dict:
        """Feuert das Ereignis, wenn die Grenzen es zulassen, und gibt das Ergebnis für das Modell zurück."""
        daten = {"werkzeug": self.name}
        for f in self.felder:
            roh = "".join(z if z.isprintable() else " " for z in str(argumente.get(f) or ""))
            daten[f] = " ".join(roh.split())[:LAENGE]
        merk = hass.data.setdefault(DOMAIN, {})
        letzte, zeiten = merk.setdefault("letzte", {}), merk.setdefault("zeiten", [])
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
        return {"ergebnis": self.ergebnis + WEITER}


async def _starten(hass: HomeAssistant, werte: Mapping | None) -> None:
    """Startet Grok Voice mit diesen Einstellungen neu (eine laufende Innenstation hält vorher sauber an); ohne Schlüssel, Station und
    Passwort bleibt es aus."""
    await _stoppen(hass)
    if not werte or not all(werte.get(k) for k in PFLICHT):
        _stand(hass, grok_voice=AUS)
        return
    from .sprache import async_starten

    daten = hass.data[DOMAIN]
    daten["grok_voice"] = "Oberfläche"
    try:
        bruecke = await async_starten(hass, dict(werte))
    except Exception:  # noqa: BLE001  ein Fehler beim Start legt nur Grok Voice still, nicht Dienst und Sensor „Empfang Störung“
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
    """Der Dienst tuer_assistent.auflegen, der Stand und das Anhalten mit Home Assistant; Grok Voice startet mit dem Eintrag."""
    _stand(hass)
    hass.data.setdefault(DOMAIN, {})

    async def dienst(call: ServiceCall) -> None:
        """Ohne Gespräch geschieht nichts; nur wenn Auflegen gar nicht geht, ein Fehler (die Automation ruft mit continue_on_error)."""
        ergebnis = auflegen(hass)
        _stand(hass, auflegen=ergebnis)
        _LOGGER.log(logging.WARNING if ergebnis.startswith("nicht") else logging.INFO, "Auflegen: %s", ergebnis)
        if ergebnis.startswith("nicht"):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="auflegen_nicht_moeglich",
                                     translation_placeholders={"grund": ergebnis.removeprefix("nicht möglich: ")})

    hass.services.async_register(DOMAIN, "auflegen", dienst, schema=vol.Schema({}))

    async def anruf_testen(call: ServiceCall) -> ServiceResponse:
        """Probeanruf über den SIP-Zugang (weiterleitung.py): Ergebnis als Antwort und in tuer_assistent.stand."""
        from .weiterleitung import probe, zugang

        z = zugang(einstellungen(hass))
        if z is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="kein_zugang")
        ergebnis = await probe(hass, z)
        _stand(hass, weiterleitung="%s: Probe %s%s" % (dt_util.now().strftime("%Y-%m-%d %H:%M"), ergebnis["ergebnis"],
                                                       ", Tasten " + ergebnis["tasten"] if ergebnis["tasten"] else ""))
        _LOGGER.info("Probeanruf: %s (%s)", ergebnis["ergebnis"], ergebnis["ende"] or "–")
        return ergebnis

    hass.services.async_register(DOMAIN, "anruf_testen", anruf_testen, schema=vol.Schema({}), supports_response=SupportsResponse.OPTIONAL)

    async def anhalten(_event) -> None:
        await _stoppen(hass, "Home Assistant hält an")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, anhalten)
    return True


def _verbindung(optionen: Mapping) -> dict:
    """Die Werte, mit denen Grok Voice läuft (fehlt einer, die Vorgabe): Daran erkennt _geaendert, ob ein Neustart nötig ist."""
    return {k: optionen.get(k, VORGABEN.get(k)) for k in VERBINDUNG}


async def _geaendert(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach geänderten Einstellungen: Nur wenn sich an der Verbindung etwas geändert hat, lädt der Eintrag neu (Grok Voice startet neu,
    ein laufender Ruf endet). Begrüßung, Anweisung, Stichwörter und Weiterleitung liest ohnehin jeder Ruf frisch."""
    if _verbindung(entry.options) != hass.data[DOMAIN].get("verbindung"):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Der Sensor „Empfang Störung“ und Grok Voice mit den Optionen des Eintrags (geändert in der Oberfläche, config_flow.py)."""
    hass.data[DOMAIN]["verbindung"] = _verbindung(entry.options)
    entry.async_on_unload(entry.add_update_listener(_geaendert))
    ir.async_delete_issue(hass, DOMAIN, "grok_voice_yaml")  # Hinweis aus 2.6.0 (alter YAML-Block); seit 2.7.0 gibt es ihn nicht mehr
    await _starten(hass, entry.options)
    await hass.config_entries.async_forward_entry_setups(entry, PLATTFORMEN)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Auch beim Neuladen nach geänderten Optionen: Sensor entladen, Grok Voice anhalten (ein laufender Ruf endet)."""
    if ok := await hass.config_entries.async_unload_platforms(entry, PLATTFORMEN):
        await _stoppen(hass)
    return ok
