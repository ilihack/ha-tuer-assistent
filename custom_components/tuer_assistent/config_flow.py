"""Einrichtung über die Oberfläche: der eine Eintrag „Tür-Assistent (Empfang)“ und alle seine Einstellungen.

Der Eintrag entsteht über „Integration hinzufügen“ (gleich mit der Maske); danach stehen die Einstellungen am Eintrag unter
„Konfigurieren“. Eine Zeile in configuration.yaml gibt es seit 2.7.0 nicht mehr.

Die Maske, von oben (sein Wort vom 14.11.2026: „dort können wir unsere Instruction reinladen und auch die Klartextnamen, vielleicht
weiter oben, damit man sie dann schnell editieren kann“):
- „Bewohner und Namen“ (immer offen): der Bewohner, für den der Empfang arbeitet, seine Anrede und die Angaben (je Zeile `name: wert`,
  jede wird eine Variable der Anweisung).
- „Begrüßung und Anweisung“: beides Vorlagen, vorbelegt mit der Vorgabe aus vorgabe.py. Gespeichert wird nur eigener Text: Bleibt ein
  Feld bei der Vorgabe (oder leer), gilt die Vorgabe der Integration, auch die einer späteren Version.
- „xAI“: Schlüssel, Modell, Stimme, Stichwörter für die Erkennung.
- „Türstation“: Adresse, Nebenstelle, Passwort, Ports.
- „Mitschrift speichern“.
Ist Grok Voice eingerichtet, stehen alle Abschnitte außer dem ersten zugeklappt: Geändert werden meist nur die Namen.

Vor dem Speichern prüft sie, was sonst erst der nächste Ruf zeigte: Pflichtfelder, die Zeilen der Angaben, ob Begrüßung und Anweisung
sich rendern lassen (streng: auch eine Variable, die es nicht gibt, ist ein Fehler; die Meldung von Jinja steht nur in der Maske, nie
im Log, denn sie zitiert die Zeile), und ob xAI den Schlüssel annimmt (eine Abfrage ohne Kosten; antwortet xAI nicht, wird gespeichert).
Schlüssel und Passwort sind Passwortfelder und nie vorbelegt (sonst ginge der gespeicherte Wert an jeden Browser, der die Maske öffnet);
leer gelassen bleibt der gespeicherte. Eine Vorlage mit falscher Schreibweise lehnt schon das Feld ab (Home Assistant antwortet mit
dem Fehler von Jinja). Was sich nach dem Speichern tut, entscheidet __init__._geaendert: Nur eine geänderte Verbindung startet Grok
Voice neu.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import ANREDEN, DOMAIN, PFLICHT, STAND, VORGABEN, angaben_lesen, vorgabe

TITEL = "Tür-Assistent (Empfang)"
GEHEIM = ("schluessel", "passwort")
_VERDECKT = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_MEHRZEILIG = TextSelector(TextSelectorConfig(multiline=True))
# Abschnitt → Felder in der Reihenfolge der Maske: (Name, Prüfer, Pflicht)
ABSCHNITTE: dict[str, tuple[tuple[str, object, bool], ...]] = {
    "namen": (("bewohner", cv.string, False),
              ("anrede", SelectSelector(SelectSelectorConfig(options=list(ANREDEN), mode=SelectSelectorMode.DROPDOWN)), True),
              ("angaben", _MEHRZEILIG, False)),
    "texte": (("begruessung", TemplateSelector(), False),
              ("anweisung", TemplateSelector(), False)),
    "xai": (("schluessel", _VERDECKT, False),  # ohne Pflicht, weil leer „unverändert“ heißt; ob einer da ist, prüft pruefen()
            ("modell", cv.string, True),
            ("stimme", cv.string, True),
            ("stichwoerter", cv.string, False)),
    "station": (("station", cv.string, True),
                ("kennung", cv.string, True),
                ("passwort", _VERDECKT, False),
                ("port", cv.port, True),
                ("station_port", cv.port, True)),
}
TEXT = ("station", "kennung", "stimme", "modell")  # dürfen nicht leer sein
TEXTE = {"begruessung": vorgabe.BEGRUESSUNG, "anweisung": vorgabe.ANWEISUNG}  # vorbelegt; gespeichert wird nur, was davon abweicht
VORSCHLAG = {**VORGABEN, "angaben": vorgabe.ANGABEN, **TEXTE}


def maske(vorschlag: Mapping, eingerichtet: bool) -> vol.Schema:
    """Die Maske mit ihren Abschnitten, vorbelegt mit `vorschlag`. Solange Schlüssel, Station oder Passwort fehlen, stehen alle
    Abschnitte offen, danach nur noch der erste: Geändert werden meist nur die Namen."""
    felder: dict = {}
    for abschnitt, liste in ABSCHNITTE.items():
        innen: dict = {}
        for name, pruefer, pflicht in liste:
            wert = vorschlag.get(name)
            art = vol.Required if pflicht else vol.Optional
            innen[art(name, description={"suggested_value": wert}) if wert not in (None, "") else art(name)] = pruefer
        felder[vol.Required(abschnitt)] = section(vol.Schema(innen), {"collapsed": eingerichtet and abschnitt != "namen"})
    felder[vol.Required("mitschrift_speichern", default=bool(vorschlag.get("mitschrift_speichern", True)))] = cv.boolean
    return vol.Schema(felder)


def flach(eingabe: Mapping) -> dict:
    """Die Eingabe ohne die Abschnitte, Text ohne Leerzeichen am Rand (die Vorlagen behalten ihre Zeilen)."""
    werte: dict = {}
    for name, wert in eingabe.items():
        werte.update(wert if name in ABSCHNITTE and isinstance(wert, Mapping) else {name: wert})
    return {k: v.strip() if isinstance(v, str) else v for k, v in werte.items()}


async def pruefen(hass: HomeAssistant, werte: dict) -> tuple[str, dict[str, str]]:
    """Der erste Fehler der Eingabe als (Kennung, Platzhalter) oder ("", {}): was sonst erst der nächste Ruf zeigte."""
    from .sprache import schluessel_abfragen, texte  # erst hier: sprache.py gehört zum Betrieb, nicht zum Laden der Maske

    fehlt = [k for k in (*PFLICHT, *TEXT) if not werte.get(k)]
    if fehlt:  # Schlüssel und Passwort haben eigene Sätze (leer gelassen heißt sonst „unverändert“); die übrigen verlangt schon die Maske
        return (fehlt[0] + "_fehlt" if fehlt[0] in GEHEIM else "leer"), {"feld": fehlt[0]}
    try:
        angaben_lesen(werte.get("angaben"))
    except ValueError as err:
        return "angaben", {"zeile": str(err)}
    try:
        texte(hass, werte)
    except TemplateError as err:  # der Text von Jinja nennt die Zeile; er steht nur hier in der Maske
        return "vorlage", {"grund": str(err)[:300]}
    try:
        async with asyncio.timeout(6):  # die Maske soll nicht lange hängen
            zustand = await schluessel_abfragen(hass, werte["schluessel"])
    except Exception:  # noqa: BLE001  xAI antwortet nicht: speichern, die laufende Prüfung meldet sich
        zustand = "ok"
    return ("schluessel", {"grund": zustand}) if zustand != "ok" else ("", {})


def _zeilen(text: object) -> str:
    """Text zum Vergleichen mit der Vorgabe: Zeilenenden einheitlich, ohne Leerraum am Rand."""
    return str(text or "").replace("\r\n", "\n").strip()


async def _schritt(flow, schritt: str, eingabe: dict | None, alt: Mapping, fertig: Callable[[dict], ConfigFlowResult]) -> ConfigFlowResult:
    """Ohne Eingabe oder mit einem Fehler die Maske, sonst fertig(Einstellungen)."""
    fehler, platz = "", {}
    werte: dict = {}
    if eingabe is not None:
        werte = flach(eingabe)
        werte.update({k: werte.get(k) or alt.get(k, "") for k in GEHEIM})  # leer gelassen: der gespeicherte Wert bleibt
        fehler, platz = await pruefen(flow.hass, werte)
        if not fehler:  # leere Felder und Texte, die der Vorgabe gleichen, werden nicht gespeichert: Dann gilt die Vorgabe
            return fertig({k: v for k, v in werte.items() if v not in (None, "") and not (k in TEXTE and _zeilen(v) == _zeilen(TEXTE[k]))})
    # vorbelegt mit Vorgaben und Gespeichertem, ohne Schlüssel und Passwort; nach einem Fehler mit der Eingabe (sie kam aus diesem Browser)
    vorschlag = {**VORSCHLAG, **{k: v for k, v in alt.items() if k not in GEHEIM}, **flach(eingabe or {})}
    stand = flow.hass.states.get(STAND)
    platz = {"feld": "", "zeile": "", "grund": "", **platz,
             "stand": ", ".join(str(stand.attributes.get(k)) for k in ("grok_voice", "xai", "modell") if stand and stand.attributes.get(k)) or "–"}
    return flow.async_show_form(step_id=schritt, data_schema=maske(vorschlag, all(alt.get(k) for k in PFLICHT)),
                                errors={"base": fehler} if fehler else {}, description_placeholders=platz)


class TuerAssistentFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Optionen:
        return Optionen()

    async def async_step_user(self, user_input=None):
        """„Integration hinzufügen“: derselbe Eintrag, gleich mit der Maske (den zweiten verhindert single_config_entry)."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await _schritt(self, "user", user_input, {}, lambda werte: self.async_create_entry(title=TITEL, data={}, options=werte))


class Optionen(OptionsFlow):
    """„Konfigurieren“ am Eintrag: dieselbe Maske."""

    async def async_step_init(self, user_input=None):
        return await _schritt(self, "init", user_input, self.config_entry.options, lambda werte: self.async_create_entry(data=werte))
