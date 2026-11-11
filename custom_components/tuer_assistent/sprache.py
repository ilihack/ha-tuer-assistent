"""Grok Voice: der Empfang am obersten Knopf der Station EG, Sprache zu Sprache (seit 11.11.2026; Wort des Betreibers: „probiert das Grok
Voice aus“; als eigene Innenstation seit 11.11.2026 abends, sein Wort: „bau die komplette Integration. Dadurch wird es robuster,
einfacher und wir können auch bei einem Fehlerfall dann einfach auflegen“).

Weg: Die Station EG ist der SIP-Server ihrer Innenstationen. Diese Integration meldet sich dort selbst als Innenstation 9904 an
(REGISTER mit Digest, die Station gibt 60 s und wird nach 80 % davon erneut gefragt). Drückt jemand den obersten Knopf, ruft die Station
9904 an; die Integration feuert sofort `tuer_assistent_grok_voice` mit „klingel“, verbindet sich mit der Echtzeit-Schnittstelle von xAI
(Erkennung, KI und Stimme in einem Schritt), gibt die Anweisung und nimmt den Ruf an. Am Ende jedes Rufs, auch eines gescheiterten,
feuert sie dasselbe Ereignis mit „ende“, der Mitschrift des Gesprächs und dem Grund des Endes; darauf hört die Automation „Klingel EG:
oberster Knopf“ und schickt genau eine Meldung aufs Handy (Wort des Betreibers vom 11.11.2026 spätabends: „bei diesem Knopf brauchen wir … nicht
überall innen drin … Nachrichten abzuspielen … Die Meldung aufs Handy ist dann das Transkript von dem, was abging“). Ton: G.711 (A-law vor µ-law, 8 kHz) wie von der Station angeboten; xAI nimmt und
liefert ihn genau so, ohne Umrechnen. Paketlänge wie angeboten (die Station: 40 ms). Andere Medien im Angebot (Video) lehnt die Antwort
mit Port 0 ab.

- Kein Ersatzweg (Wort des Betreibers vom 11.11.2026 abends: „Voice-over-Voice und wenn es kaputt geht, dann bleibt es halt kaputt“): Kommt xAI
  binnen VERBINDEN s nicht zustande, antwortet die Integration 503 und die Station beendet den Ruf; den Grund trägt die Meldung am Ende.
- Überwachung (Wort des Betreibers: „in der Überwachung haben, dass diese Integration funktioniert, unsere xAI-Keys nicht ausgelaufen sind und
  ansonsten im Notfall eine Plakette kommt“): Den Schlüssel prüft sie beim Start und stündlich bei xAI (GET /v1/api-key, kostet nichts;
  ein ungültiger Schlüssel gibt 400, ein gesperrter steht im Ergebnis), dazu bei jeder abgelehnten Verbindung. `stoerung()` nennt, was
  fehlt: nicht angemeldet seit MELDEN_NACH s, Schlüssel abgelehnt oder gesperrt, xAI seit XAI_STILL s nicht erreichbar. Daraus der
  Sensor `binary_sensor.empfang_stoerung` (binary_sensor.py) und die Plakette „Empfang“ auf den Hubs; Beginn und Ende einer Störung
  melden sich je einmal aufs Handy (Mitschrift mit „ersatz“, die Automation der Mitschrift meldet jedes „ersatz“).
- Nur die Station: Pakete von anderen Adressen verwirft die Integration ungelesen (der Port ist im Hausnetz offen, weil die Station
  ihn erreichen muss); Ton nur von der Station. Das Passwort für 9904 steht in secrets.yaml.
- Anmeldung verloren (Station aus, Netz, Passwort): neuer Versuch nach 5, 10, 20, 40, dann alle 60 s; dauert es MELDEN_NACH s, ist es
  eine Störung (wie oben). Beim Anhalten von Home Assistant meldet sie sich ab.
- Anweisung: dieselbe wie bei den Text-Agenten (aus dem gewählten Agenten), gerendert mit `grok_voice = true`; die Begrüßung ist der
  Satz „Hello, …“ daraus und kommt als fester Text (force_message), ohne das Modell zu fragen.
- Nachdenken „high“ (Vorgabe von xAI): Mit „none“ schickte es Zusteller nicht in die Paketbox und wusste die Bewohner nicht, bei
  gleicher Wartezeit bis zum ersten Ton (11.11.2026, r53/gv_proto.py).
- Werkzeuge: dieselben drei mit denselben Grenzen (`Werkzeug` aus __init__.py). „auflegen“ beendet den Ruf, sobald die Verabschiedung
  gespielt ist; `tuer_assistent.auflegen` beendet ihn ebenso. Nach „bewohner_rufen“ endet der Ruf ebenso nach der Antwort, damit die
  Sprechanlage frei ist und er sich über die App melden kann (Wort des Betreibers vom 11.11.2026 nachts: „solange der Grok damit redet, dann kann
  ich nicht telefonieren … direkt auflegen und sagen, ich hab Bescheid gesagt, der Muster könnte sich jeden Moment mit der Sprechanlage
  verbinden“).
- Vollduplex (Wort des Betreibers vom 11.11.2026 abends: „Die Komplexität mit Mikrofon aus brauchst du nicht. Grok … hat selbst eine gute
  Echo-Unterbindung und die Außensprechanlage auch“): Der Ton des Besuchers geht immer zu xAI. Fängt er an zu sprechen, bricht xAI die
  laufende Antwort ab (bei server_vad von selbst); die Gegenstelle verwirft den noch nicht gespielten Ton und alles, was von dieser
  Antwort noch kommt (11.11.2026 geprobt). Die Begrüßung spielt xAI trotzdem ganz zu Ende; was der Besucher währenddessen sagt, geht
  nicht verloren (ebenso geprobt).
- Mitschrift: je Antwort `tuer_assistent_gespraech` wie beim Text-Agenten (ki „grok_voice“, sekunden = vom Ende der Rede bis zum
  ersten Ton; aufs Handy nur, solange der Schalter „Tür Mitschrift“ an ist); das ganze Gespräch kommt mit „ende“ (oben).
- Ein Ruf zur Zeit (sonst 486), höchstens HOECHSTENS s (die Station beendet ohnehin nach 2 min).
- Robust: Jede Teilaufgabe des Rufs (Takt, Lesen, Schreiben, Wächter) beendet bei einem unerwarteten Fehler den Ruf sauber (BYE),
  mit dem Grund in der Meldung am Ende, statt still hängen zu bleiben; ein einzelnes unlesbares Ereignis von xAI wird übergangen; scheitert das Senden an xAI,
  legt sie auf und meldet es; ein Fehler in einem Werkzeug geht als Ergebnis an das Modell, der Ruf läuft weiter; nach Werkzeugen
  fordert sie die Antwort erst an, wenn xAI die Antwort mit den Aufrufen beendet hat (so verlangt es xAI bei mehreren Aufrufen).
- Wächter: Kommt nach dem Ende der Rede des Besuchers binnen KEINE_ANTWORT s keine Antwort von xAI (Verbindung steht, aber hängt),
  legt sie auf (Grund in der Meldung am Ende). Spricht STILLE_ENDE s niemand (weder der Besucher noch der Empfang), legt sie auf: Der
  Besucher ist gegangen, die Minuten kosten Geld.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import hashlib
import json
import logging
import re
import secrets
import socket
import time
from types import SimpleNamespace

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.template import Template

from . import LAENGE, MITSCHRIFT, WERKZEUGE, Werkzeug, _stand, agenten, gewaehlt

_LOGGER = logging.getLogger(__name__)
URL = "wss://api.x.ai/v1/realtime?model=grok-voice-latest"
EREIGNIS = "tuer_assistent_grok_voice"
VERBINDEN = 5.0  # s für Verbindung und Anweisung, bevor der Ruf angenommen wird
HOECHSTENS = 180  # s je Ruf
KEINE_ANTWORT = 10  # s nach dem Ende der Rede ohne Antwort von xAI: auflegen und melden
STILLE_ENDE = 30  # s, in denen niemand spricht: auflegen
ABLAUF = 300  # s, erbetene Gültigkeit der Anmeldung (die Station gibt 60 s)
WARTEN = (5, 10, 20, 40, 60)  # s bis zum nächsten Anmeldeversuch nach einem Fehler
MELDEN_NACH = 180  # s ohne Anmeldung, dann einmal aufs Handy
ERNEUERN_MIN = 5.0  # s, frühestens so bald wird eine Anmeldung erneuert
SCHLUESSEL_URL = "https://api.x.ai/v1/api-key"  # Auskunft über den Schlüssel, ohne Kosten
XAI_PRUEFEN = 3600  # s zwischen zwei Prüfungen des Schlüssels
XAI_STILL = 6 * 3600  # s ohne erfolgreiche Prüfung: Störung
MITSCHRIFT_HOECHSTENS = 1800  # Zeichen der Mitschrift in der Meldung am Ende
WIEDERHOLEN = (0.5, 1.0, 2.0)  # s, nach denen ein REGISTER ohne Antwort wiederholt wird (danach noch 1 s Warten)
KURZ = {"v": "via", "f": "from", "t": "to", "i": "call-id", "m": "contact", "l": "content-length", "c": "content-type"}
BEGRUESSUNG = "Hello! Hier ist der Empfang, wie kann ich helfen?"  # nur falls die Anweisung keinen Satz „Hello, …“ enthält


@dataclass(frozen=True)
class Codec:
    """G.711 auf der Leitung; xAI nimmt und liefert es genau so."""

    pt: int
    name: str

    @property
    def xai(self) -> dict:
        return {"type": "audio/pcma" if self.name == "PCMA" else "audio/pcmu", "rate": 8000}

    @property
    def stille(self) -> int:
        return 0xD5 if self.name == "PCMA" else 0xFF


def zerlege(daten: bytes) -> tuple[str, list[tuple[str, str]], str]:
    """SIP-Nachricht → erste Zeile, Kopfzeilen (Name klein, Kurzformen aufgelöst), Rumpf."""
    text = daten.decode("utf-8", "replace")
    kopf, _, rumpf = text.partition("\r\n\r\n")
    zeilen = kopf.split("\r\n")
    felder: list[tuple[str, str]] = []
    for z in zeilen[1:]:
        if not z:
            continue
        if z[0] in " \t" and felder:
            felder[-1] = (felder[-1][0], felder[-1][1] + " " + z.strip())
            continue
        name, _, wert = z.partition(":")
        name = name.strip().lower()
        felder.append((KURZ.get(name, name), wert.strip()))
    return zeilen[0].strip(), felder, rumpf


def feld(felder, name: str) -> str:
    return next((w for n, w in felder if n == name), "")


@dataclass
class Angebot:
    """Das SDP-Angebot der Station: Adresse und Port des Tons, angebotene G.711-Codecs, Paketlänge, alle Medienzeilen der Reihe nach."""

    host: str
    port: int
    codecs: list[Codec]
    ptime: int
    medien: list[list[str]]  # je Zeile: Medium, Port, Protokoll, Formate …
    ton: int  # Index der ersten Tonzeile in medien, -1 ohne


def sdp_lesen(rumpf: str) -> Angebot:
    host, medien, karte, ton, ptime, typen, port = "", [], {0: "PCMU", 8: "PCMA"}, -1, 20, [], 0
    in_ton = False
    for z in rumpf.replace("\r\n", "\n").split("\n"):
        z = z.strip()
        if z.startswith("m="):
            teile = z[2:].split()
            medien.append(teile)
            in_ton = ton == -1 and len(teile) >= 3 and teile[0] == "audio"
            if in_ton:
                ton = len(medien) - 1
                port = int(teile[1]) if teile[1].isdigit() else 0
                typen = [int(x) for x in teile[3:] if x.isdigit()]
        elif z.startswith("c=IN IP4 ") and (in_ton or not host):
            host = z[9:].split("/")[0].strip()
        elif z.startswith("a=rtpmap:") and in_ton:
            m = re.match(r"a=rtpmap:(\d+)\s+([^/\s]+)/(\d+)", z)
            if m and m.group(3) == "8000":
                karte[int(m.group(1))] = m.group(2).upper()
        elif z.startswith("a=ptime:") and in_ton and z[8:].strip().isdigit() and int(z[8:].strip()) in (10, 20, 30, 40):
            ptime = int(z[8:].strip())
    codecs = [Codec(t, karte[t]) for t in typen if karte.get(t) in ("PCMA", "PCMU")]
    return Angebot(host, port, codecs, ptime, medien, ton)


def waehlen(angebot: Angebot) -> Codec | None:
    """A-law vor µ-law."""
    return next((c for name in ("PCMA", "PCMU") for c in angebot.codecs if c.name == name), None)


def sdp_antwort(angebot: Angebot, codec: Codec, host: str, rtp_port: int) -> str:
    """Antwort mit derselben Zahl und Reihenfolge der Medienzeilen; Ton mit dem gewählten Codec, alles andere abgelehnt (Port 0)."""
    sitzung = secrets.randbelow(10**9)
    zeilen = [f"v=0\r\no=- {sitzung} {sitzung} IN IP4 {host}\r\ns=Empfang\r\nc=IN IP4 {host}\r\nt=0 0\r\n"]
    for i, m in enumerate(angebot.medien):
        if i == angebot.ton:
            zeilen.append(f"m=audio {rtp_port} RTP/AVP {codec.pt}\r\na=rtpmap:{codec.pt} {codec.name}/8000\r\n"
                          f"a=ptime:{angebot.ptime}\r\na=sendrecv\r\n")
        else:
            zeilen.append(f"m={m[0]} 0 {m[2] if len(m) > 2 else 'RTP/AVP'} {m[3] if len(m) > 3 else '0'}\r\n")
    return "".join(zeilen)


def antwort(felder, code: int, grund: str, *, to_tag: str = "", rumpf: str = "", kontakt: str = "") -> bytes:
    zeilen = [f"SIP/2.0 {code} {grund}"]
    zeilen += ["Via: " + w for n, w in felder if n == "via"]
    zeilen.append("From: " + feld(felder, "from"))
    an = feld(felder, "to")
    if to_tag and ";tag=" not in an:
        an += ";tag=" + to_tag
    zeilen += ["To: " + an, "Call-ID: " + feld(felder, "call-id"), "CSeq: " + feld(felder, "cseq")]
    if kontakt:
        zeilen.append("Contact: " + kontakt)
    zeilen.append("Server: tuer_assistent")
    if rumpf:
        zeilen.append("Content-Type: application/sdp")
    zeilen.append("Content-Length: %d" % len(rumpf.encode()))
    return ("\r\n".join(zeilen) + "\r\n\r\n" + rumpf).encode()


def rtp_nutzlast(d: bytes) -> tuple[int, bytes] | None:
    """RTP-Paket → (Nutzlast-Typ, Nutzlast) oder None."""
    if len(d) < 12 or d[0] >> 6 != 2:
        return None
    ab = 12 + 4 * (d[0] & 0x0F)
    if d[0] & 0x10:
        if len(d) < ab + 4:
            return None
        ab += 4 + 4 * int.from_bytes(d[ab + 2:ab + 4], "big")
    ende = len(d) - (d[-1] if d[0] & 0x20 and d[-1] else 0)
    return (d[1] & 0x7F, d[ab:ende]) if ab <= ende else None


def _md5(text: str) -> str:
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()


def digest(methode: str, uri: str, nutzer: str, passwort: str, herausforderung: str, nc: int = 1) -> str:
    """Kopfzeile Authorization für eine Digest-Herausforderung (MD5, mit oder ohne qop=auth)."""
    roh = herausforderung.split(" ", 1)[1] if herausforderung.lower().startswith("digest ") else herausforderung
    p = {k.lower(): (v[1:-1] if v.startswith('"') else v) for k, v in re.findall(r'(\w+)\s*=\s*("[^"]*"|[^,\s]+)', roh)}
    if p.get("algorithm", "MD5").upper() != "MD5":
        raise ValueError("Verfahren %s nicht unterstützt" % p.get("algorithm"))
    realm, nonce = p.get("realm", ""), p.get("nonce", "")
    ha1, ha2 = _md5(f"{nutzer}:{realm}:{passwort}"), _md5(f"{methode}:{uri}")
    teile = [f'username="{nutzer}"', f'realm="{realm}"', f'nonce="{nonce}"', f'uri="{uri}"']
    if "auth" in [q.strip() for q in p.get("qop", "").split(",")]:
        cnonce, ncs = secrets.token_hex(8), "%08x" % nc
        teile += [f'response="{_md5(f"{ha1}:{nonce}:{ncs}:{cnonce}:auth:{ha2}")}"', "qop=auth", f"nc={ncs}", f'cnonce="{cnonce}"']
    else:
        teile.append(f'response="{_md5(f"{ha1}:{nonce}:{ha2}")}"')
    teile.append("algorithm=MD5")
    if "opaque" in p:
        teile.append(f'opaque="{p["opaque"]}"')
    return "Digest " + ", ".join(teile)


def werkzeug_schemas() -> list[dict]:
    return [{"type": "function", "name": name, "description": beschreibung,
             "parameters": {"type": "object", "properties": {f: {"type": "string"} for f in felder}}}
            for name, beschreibung, felder, _ in WERKZEUGE]


def anweisung_vorlage(hass: HomeAssistant) -> str:
    """Die Anweisung des gewählten Tür-Agenten (alle Tür-Agenten haben dieselbe); leer, wenn keine zu finden ist."""
    reg = er.async_get(hass)
    for eid in [gewaehlt(hass)[0], *agenten(hass)]:
        e = reg.async_get(eid)
        eintrag = hass.config_entries.async_get_entry(e.config_entry_id) if e and e.config_entry_id else None
        sub = eintrag.subentries.get(e.config_subentry_id) if eintrag and getattr(e, "config_subentry_id", None) else None
        if sub is not None and sub.data.get("prompt"):
            return str(sub.data["prompt"])
    return ""


def namen(hass: HomeAssistant) -> list[str]:
    """Namen aus den Helfern als Hilfe für die Erkennung (keyterms)."""
    woerter: list[str] = []
    for e in ("input_text.tur_namen_dachgeschoss", "input_text.tur_namen_erdgeschoss", "input_text.tur_namen_untergeschoss"):
        st = hass.states.get(e)
        for w in re.split(r"[\s,]+", st.state if st else ""):
            w = re.sub(r"[^0-9A-Za-zÀ-ÿ-]", "", w)
            if len(w) > 2 and w not in ("und", "Herr", "Frau", "Familie", "unknown", "unavailable") and w not in woerter:
                woerter.append(w[:50])
    return woerter[:20] + ["Paketbox"]


def _text(err: BaseException) -> str:
    """Kurzer Text zu einem Fehler; manche Fehler von aiohttp lassen sich nicht in Text wandeln."""
    try:
        text = str(err)
    except Exception:  # noqa: BLE001
        text = ""
    if isinstance(err, aiohttp.WSServerHandshakeError):
        text = "xAI lehnt ab (HTTP %s)" % err.status
    return text[:120] or type(err).__name__


def _mitschrift_melden(hass: HomeAssistant, grund: str) -> None:
    """Ein Ausfall ohne Gespräch: Mitschrift mit Grund (die Automation der Mitschrift schickt jedes „ersatz“ aufs Handy)."""
    hass.bus.async_fire(MITSCHRIFT, {"besucher": "", "empfang": "", "sekunden": 0, "ersatz": ("Grok Voice: " + grund)[:LAENGE],
                                     "werkzeug": "", "ki": "grok_voice", "gespraech": ""})


class _Rtp(asyncio.DatagramProtocol):
    def __init__(self, ruf: "Ruf") -> None:
        self.ruf = ruf

    def datagram_received(self, daten: bytes, adresse) -> None:
        try:
            self.ruf.ton_rein(daten, adresse)
        except Exception:  # noqa: BLE001  ein kaputtes Paket darf den Ruf nicht stören
            _LOGGER.debug("Grok Voice: Paket verworfen", exc_info=True)


class Ruf:
    """Ein Gespräch: SIP-Dialog mit der Station, RTP und die Verbindung zu xAI."""

    def __init__(self, bruecke: "Bruecke", felder, adresse, rumpf: str) -> None:
        self.b, self.hass, self.felder, self.adresse = bruecke, bruecke.hass, felder, adresse
        self.call_id = feld(felder, "call-id")
        self.tag = secrets.token_hex(6)
        self.angebot = sdp_lesen(rumpf)
        self.codec = waehlen(self.angebot)
        self.ptime = self.angebot.ptime
        self.sdp = ""
        self.letzte_antwort: bytes | None = None
        self.antwort_200: bytes | None = None
        self.bestaetigt = False
        self.lebt = True
        self.angenommen = False
        self.ws = None
        self.rtp = None
        self.begruessung = BEGRUESSUNG
        self.aufgaben: list[asyncio.Task] = []
        self.raus: asyncio.Queue = asyncio.Queue()
        self.ausgang = bytearray()
        self.eingang = bytearray()
        self.zuletzt_ton = 0.0
        self.antwort_fertig = True
        self.auflegen_wunsch = False
        self.auflegen_grund = "aufgelegt nach Verabschiedung"
        self.offen = 0  # angeforderte Antworten nach einem Werkzeug, die noch nicht begonnen haben
        self.laeuft = False  # eine Antwort von xAI läuft (zwischen response.created und response.done)
        self.nach_werkzeug = False  # nach dem Ende dieser Antwort eine neue anfordern (die Ergebnisse der Werkzeuge sind gesendet)
        self.unterbrochen = False  # der Besucher hat dazwischengeredet: Ton der abgebrochenen Antwort verwerfen bis zur nächsten
        self.ende_rede: float | None = None
        self.warte_seit: float | None = None  # Ende der Rede, auf das noch keine Antwort begonnen hat
        self.besucher_spricht = False
        self.zuletzt_besucher = time.monotonic()
        self.wartezeit: float | None = None
        self.besucher = ""
        self.werkzeuge: list[str] = []
        self.beginn = time.monotonic()
        self.cseq = 100 + secrets.randbelow(1000)
        self.protokoll: list[str] = []  # das ganze Gespräch für die Meldung am Ende
        self.grund = ""  # warum der Ruf endete
        self.gemeldet = False

    # --- Aufbau -------------------------------------------------------------------------------------------------------------
    async def starten(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            async with asyncio.timeout(VERBINDEN):
                self.ws, self.begruessung = await self.b.verbinden_und_anweisen(self.codec.xai)
            if not self.lebt:  # während des Aufbaus abgebrochen (CANCEL)
                raise RuntimeError("abgebrochen")
            self.rtp, _ = await loop.create_datagram_endpoint(lambda: _Rtp(self), local_addr=("0.0.0.0", 0))
        except Exception as err:  # noqa: BLE001  jede Störung heißt: den Ruf nicht annehmen
            grund = "keine Antwort von xAI in %g s" % VERBINDEN if isinstance(err, TimeoutError) else _text(err)
            if isinstance(err, aiohttp.WSServerHandshakeError) and err.status in (400, 401, 403):
                self.b.xai_setzen("abgelehnt (HTTP %d)" % err.status)
            if self.lebt:
                _LOGGER.warning("Grok Voice: Ruf nicht angenommen (%s)", grund)
                self.b.senden(antwort(self.felder, 503, "Service Unavailable", to_tag=self.tag), self.adresse)
                self.hass.bus.async_fire(EREIGNIS, {"ergebnis": "abgelehnt", "grund": grund})
                self.grund = "nicht angenommen: " + grund
            await self.aufraeumen()
            return
        c = self.codec
        self.sdp = sdp_antwort(self.angebot, c, self.b.lokal, self.rtp.get_extra_info("sockname")[1])
        self.antwort_200 = antwort(self.felder, 200, "OK", to_tag=self.tag, rumpf=self.sdp, kontakt=self.b.kontakt())
        self.letzte_antwort = self.antwort_200
        self.b.senden(self.antwort_200, self.adresse)
        self.angenommen = True
        self.hass.bus.async_fire(EREIGNIS, {"ergebnis": "angenommen", "codec": f"{c.name}/8000"})
        _LOGGER.info("Grok Voice: Ruf angenommen nach %.1f s (%s, %d ms)", time.monotonic() - self.beginn, c.name, self.ptime)
        self.zuletzt_besucher = time.monotonic()
        for name, arbeit in (("200", self._wiederholen_200), ("Schreiben", self._schreiben), ("Lesen", self._lesen),
                             ("Takt", self._takt), ("Frist", self._frist), ("Wächter", self._waechter)):
            self.aufgaben.append(asyncio.create_task(self._sicher(name, arbeit)))
        await self.raus.put({"type": "conversation.item.create", "item": {
            "type": "force_message", "role": "assistant", "interruptible": True,
            "content": [{"type": "output_text", "text": self.begruessung}]}})

    async def _sicher(self, name: str, arbeit) -> None:
        """Eine Teilaufgabe, die bei einem unerwarteten Fehler den Ruf beendet und meldet, statt still hängen zu bleiben."""
        try:
            await arbeit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Grok Voice: Fehler in der Teilaufgabe %s", name)
            if self.lebt:
                await self.beenden("interner Fehler (%s)" % name)

    async def _wiederholen_200(self) -> None:
        for warte in (0.5, 1, 2, 4, 4, 4, 4):
            await asyncio.sleep(warte)
            if self.bestaetigt or not self.lebt:
                return
            self.b.senden(self.antwort_200, self.adresse)

    async def _frist(self) -> None:
        await asyncio.sleep(HOECHSTENS)
        await self.beenden("Höchstdauer erreicht")

    async def _waechter(self) -> None:
        while self.lebt:
            await asyncio.sleep(0.5)
            jetzt = time.monotonic()
            if self.warte_seit is not None and jetzt - self.warte_seit > KEINE_ANTWORT:
                await self.beenden("xAI antwortet nicht (%d s)" % KEINE_ANTWORT)
                return
            ruhig = not self.ausgang and self.antwort_fertig and not self.besucher_spricht and self.warte_seit is None
            if ruhig and jetzt - max(self.zuletzt_ton, self.zuletzt_besucher) > STILLE_ENDE:
                await self.beenden("%d s Stille" % STILLE_ENDE)
                return

    # --- Ton ----------------------------------------------------------------------------------------------------------------
    def ton_rein(self, daten: bytes, adresse) -> None:
        if not self.lebt or adresse[0] not in (self.angebot.host, self.b.station):
            return
        paket = rtp_nutzlast(daten)
        if paket is None or paket[0] != self.codec.pt:
            return
        self.eingang.extend(paket[1])
        if len(self.eingang) >= 640:  # 80 ms je Nachricht an xAI
            self.raus.put_nowait({"type": "input_audio_buffer.append", "audio": base64.b64encode(bytes(self.eingang)).decode()})
            self.eingang.clear()

    async def _takt(self) -> None:
        """Je Paketlänge (ptime) ein RTP-Paket: eigener Ton, sonst Stille; nach einem Hänger bis 0,2 s wird nachgeholt, sonst neu angesetzt."""
        loop = asyncio.get_running_loop()
        c = self.codec
        groesse, takt = 8 * self.ptime, self.ptime / 1000
        stille = bytes([c.stille]) * groesse
        seq, ts, ssrc = secrets.randbelow(65536), secrets.randbelow(2**32), secrets.randbelow(2**32)
        sprach, naechst = False, loop.time()
        ziel = (self.angebot.host, self.angebot.port)
        while self.lebt:
            warte = naechst - loop.time()
            if warte > 0:
                await asyncio.sleep(warte)
            jetzt = loop.time()
            if jetzt - naechst > 0.2:
                naechst = jetzt
            while naechst <= jetzt + 0.001 and self.lebt:
                if len(self.ausgang) >= groesse or (self.ausgang and self.antwort_fertig):
                    nutz = bytes(self.ausgang[:groesse]).ljust(groesse, stille[:1])
                    del self.ausgang[:groesse]
                    marke, sprach = not sprach, True
                    self.zuletzt_ton = time.monotonic()
                else:
                    nutz, marke, sprach = stille, False, False
                kopf = bytes([0x80, (0x80 if marke else 0) | c.pt]) + seq.to_bytes(2, "big") + ts.to_bytes(4, "big") + ssrc.to_bytes(4, "big")
                if self.rtp is not None:
                    self.rtp.sendto(kopf + nutz, ziel)
                seq, ts, naechst = (seq + 1) & 0xFFFF, (ts + groesse) & 0xFFFFFFFF, naechst + takt
            if self.auflegen_wunsch and self.antwort_fertig and not self.ausgang and time.monotonic() - self.zuletzt_ton > 0.8:
                self.hass.async_create_task(self.beenden(self.auflegen_grund))
                return

    # --- xAI ----------------------------------------------------------------------------------------------------------------
    async def _schreiben(self) -> None:
        while self.lebt:
            nachricht = await self.raus.get()
            try:
                await self.ws.send_json(nachricht)
            except Exception as err:  # noqa: BLE001  ohne Senden hört xAI nichts mehr: auflegen und melden
                if self.lebt:
                    await self.beenden("Senden an xAI fehlgeschlagen (%s)" % type(err).__name__)
                return

    async def _lesen(self) -> None:
        grund = "Verbindung zu xAI beendet"
        try:
            async for roh in self.ws:
                if roh.type != aiohttp.WSMsgType.TEXT:
                    if roh.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                try:
                    e = json.loads(roh.data)
                except (TypeError, ValueError):
                    continue
                if not isinstance(e, dict):
                    continue
                try:
                    await self._ereignis(e)
                except Exception:  # noqa: BLE001  ein einzelnes kaputtes Ereignis beendet das Gespräch nicht (hängt es, wacht der Wächter)
                    _LOGGER.warning("Grok Voice: Ereignis %s nicht verarbeitet", str(e.get("type"))[:40], exc_info=True)
                if not self.lebt:
                    return
        except Exception as err:  # noqa: BLE001
            grund = "Verbindung zu xAI abgebrochen (%s)" % type(err).__name__
        if self.lebt:
            await self.beenden(grund)

    async def _ereignis(self, e: dict) -> None:
        art = e.get("type", "")
        if art in ("response.output_audio.delta", "response.audio.delta"):
            if self.unterbrochen:  # Rest der abgebrochenen Antwort
                return
            if self.wartezeit is None and self.ende_rede is not None:
                self.wartezeit = time.monotonic() - self.ende_rede
            self.ausgang.extend(base64.b64decode(e.get("delta") or ""))
        elif art == "response.created":
            self.offen = max(0, self.offen - 1)
            self.antwort_fertig, self.warte_seit, self.laeuft, self.unterbrochen = False, None, True, False
        elif art == "response.done":  # nach Werkzeug-Aufrufen erst jetzt die Folgeantwort anfordern; fertig erst, wenn auch sie durch ist
            self.laeuft = False
            if self.nach_werkzeug:
                self.nach_werkzeug = False
                await self._folgeantwort()
            self.antwort_fertig = self.offen == 0
        elif art == "input_audio_buffer.speech_started":  # Dazwischenreden: xAI bricht die Antwort selbst ab, hier nicht mehr spielen
            self.ausgang.clear()
            self.unterbrochen = self.laeuft or self.unterbrochen
            self.besucher_spricht, self.zuletzt_besucher = True, time.monotonic()
        elif art == "input_audio_buffer.speech_stopped":
            self.ende_rede, self.wartezeit = time.monotonic(), None
            self.besucher_spricht, self.zuletzt_besucher, self.warte_seit = False, self.ende_rede, self.ende_rede
        elif art == "conversation.item.input_audio_transcription.completed":
            self.besucher = " ".join(str(e.get("transcript") or "").split())
            if self.besucher:
                self.protokoll.append("Besucher: " + self.besucher[:LAENGE])
        elif art == "response.output_audio_transcript.done":
            gesagt = " ".join(str(e.get("transcript") or "").split())
            if gesagt and gesagt != self.begruessung:
                self.protokoll.append("Empfang: " + gesagt[:LAENGE])
            self._mitschrift(gesagt, "")
        elif art == "response.function_call_arguments.done":
            await self._werkzeug(e)
        elif art == "error":
            fehler = e.get("error") or {}
            _LOGGER.warning("Grok Voice: Meldung von xAI: %s %s", fehler.get("type"), str(fehler.get("message"))[:160])

    async def _werkzeug(self, e: dict) -> None:
        name = str(e.get("name") or "")
        try:
            argumente = json.loads(e.get("arguments") or "{}")
        except ValueError:
            argumente = {}
        eintrag = next((w for w in WERKZEUGE if w[0] == name), None)
        if eintrag is None:
            ausgabe: object = {"ergebnis": "Dieses Werkzeug gibt es nicht."}
        else:
            try:
                ergebnis = await Werkzeug(*eintrag).async_call(self.hass, SimpleNamespace(tool_name=name, tool_args=argumente if isinstance(argumente, dict) else {}), None)
                ausgabe = getattr(ergebnis, "data", ergebnis)
            except Exception:  # noqa: BLE001  ein Fehler im Werkzeug beendet nicht das Gespräch
                _LOGGER.exception("Grok Voice: Werkzeug %s fehlgeschlagen", name)
                ausgabe = {"ergebnis": "Das hat gerade nicht geklappt. Bitte den Besucher, selbst an der Wohnung zu klingeln."}
            self.werkzeuge.append(name)
            self.protokoll.append({"bewohner_rufen": "(dir Bescheid gegeben)", "nachricht_weitergeben": "(Nachricht an dich weitergegeben)",
                                   "auflegen": "(aufgelegt)"}.get(name, "(%s)" % name))
            if name == "auflegen":
                self.auflegen_wunsch = True
            elif name == "bewohner_rufen":  # die Sprechanlage für ihn freimachen: nach dieser Antwort auflegen
                self.auflegen_wunsch, self.auflegen_grund = True, "aufgelegt nach dem Bescheid an dich (Sprechanlage frei)"
        await self.raus.put({"type": "conversation.item.create", "item": {
            "type": "function_call_output", "call_id": e.get("call_id"), "output": json.dumps(ausgabe, ensure_ascii=False)}})
        self.antwort_fertig = False  # die Antwort nach dem Werkzeug kommt noch (sonst legte auflegen vor der Verabschiedung auf)
        if self.laeuft:
            self.nach_werkzeug = True  # erst nach response.done anfordern, dann sind alle Ergebnisse dieser Antwort da
        else:
            await self._folgeantwort()

    async def _folgeantwort(self) -> None:
        self.offen += 1
        self.antwort_fertig, self.warte_seit = False, time.monotonic()  # auch hier wacht der Wächter
        await self.raus.put({"type": "response.create"})

    def _mitschrift(self, gesagt: str, grund: str) -> None:
        try:
            self.hass.bus.async_fire(MITSCHRIFT, {
                "besucher": self.besucher[:LAENGE], "empfang": " ".join(gesagt.split())[:LAENGE],
                "sekunden": round(self.wartezeit, 1) if self.wartezeit is not None else 0, "ersatz": grund,
                "werkzeug": ", ".join(self.werkzeuge), "ki": "grok_voice", "gespraech": self.call_id[-6:]})
        except Exception:  # noqa: BLE001  die Mitschrift darf das Gespräch nie stören
            _LOGGER.debug("Mitschrift nicht gefeuert", exc_info=True)
        self.besucher, self.werkzeuge = "", []

    # --- Ende ---------------------------------------------------------------------------------------------------------------
    def auflegen(self) -> None:
        """Von außen (Dienst tuer_assistent.auflegen): nach dem Ton, der gerade läuft, spätestens nach 6 s."""
        self.auflegen_wunsch = True
        if self.antwort_fertig and not self.ausgang:
            self.hass.async_create_task(self.beenden("aufgelegt (Dienst)"))
        else:
            self.hass.loop.call_later(6, lambda: self.hass.async_create_task(self.beenden("aufgelegt (Dienst, nach 6 s)")))

    async def beenden(self, grund: str, *, bye: bool = True) -> None:
        if not self.lebt:
            return
        self.lebt = False
        self.grund = self.grund or grund
        if bye and self.angenommen:
            self.b.bye(self)
        _LOGGER.info("Grok Voice: Ruf beendet nach %.0f s (%s)", time.monotonic() - self.beginn, grund)
        await self.aufraeumen()

    async def aufraeumen(self) -> None:
        self.lebt = False
        aktuell = asyncio.current_task()
        for a in self.aufgaben:
            if a is not aktuell:
                a.cancel()
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:  # noqa: BLE001
                pass
        if self.rtp is not None:
            self.rtp.close()
        if self.b.ruf is self:
            self.b.ruf = None
        self._ende_melden()

    def _ende_melden(self) -> None:
        """Einmal je Ruf: das ganze Gespräch und der Grund des Endes (die Automation der Klingel schickt es aufs Handy)."""
        if self.gemeldet:
            return
        self.gemeldet = True
        text = "\n".join(self.protokoll)
        if len(text) > MITSCHRIFT_HOECHSTENS:
            text = text[:MITSCHRIFT_HOECHSTENS - 2].rsplit(" ", 1)[0] + " …"
        try:
            self.hass.bus.async_fire(EREIGNIS, {"ergebnis": "ende", "angenommen": self.angenommen, "sekunden": round(time.monotonic() - self.beginn),
                                                "grund": self.grund, "mitschrift": text})
        except Exception:  # noqa: BLE001  die Meldung darf das Aufräumen nie stören
            _LOGGER.debug("Ende nicht gefeuert", exc_info=True)


async def _warte_auf_update(ws) -> None:
    while True:
        nachricht = await ws.receive_json()
        art = nachricht.get("type")
        if art == "session.updated":
            return
        if art == "error":
            raise RuntimeError("xAI: %s" % str((nachricht.get("error") or {}).get("message"))[:120])


def lokale_adresse(station: str) -> str:
    """Die eigene Adresse im Hausnetz, von der aus die Station erreicht wird (UDP-connect sendet nichts)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((station, 5060))
        return s.getsockname()[0]
    finally:
        s.close()


class Bruecke(asyncio.DatagramProtocol):
    """Die Innenstation 9904: Anmeldung an der Station, Rufe von ihr, Gespräch mit xAI."""

    def __init__(self, hass: HomeAssistant, *, schluessel: str, station: str, kennung: str, passwort: str, port: int = 5062,
                 station_port: int = 5060, stimme: str = "eve") -> None:
        self.hass, self.schluessel, self.station, self.kennung, self.passwort = hass, schluessel, station, kennung, passwort
        self.port, self.station_port, self.stimme = port, station_port, stimme
        self.lokal = "0.0.0.0"
        self.transport = None
        self.ruf: Ruf | None = None
        self.byes: dict[str, asyncio.Task] = {}
        self.angemeldet = False
        self.anmeldung: asyncio.Task | None = None
        self._antworten: dict[tuple[str, int], asyncio.Future] = {}
        self._reg_call_id = secrets.token_hex(10)
        self._reg_tag = secrets.token_hex(6)
        self._reg_cseq = secrets.randbelow(1000)
        self._nc = 0
        self.anmelde_fehler_seit: float | None = None
        self.xai = "noch nicht geprüft"
        self.xai_ok_seit = time.monotonic()  # bis zur ersten Prüfung als gut angenommen
        self.pruefung: asyncio.Task | None = None

    # --- xAI ----------------------------------------------------------------------------------------------------------------
    async def verbinden(self):
        sitzung = async_get_clientsession(self.hass)
        return await sitzung.ws_connect(URL, headers={"Authorization": "Bearer " + self.schluessel}, heartbeat=20, max_msg_size=0)

    async def verbinden_und_anweisen(self, format_: dict):
        """Verbindung zu xAI mit Anweisung, Stimme, Werkzeugen und Tonformat; → (Verbindung, Begrüßung)."""
        vorlage = anweisung_vorlage(self.hass)
        if not vorlage:
            raise RuntimeError("keine Anweisung gefunden")
        anweisung = Template(vorlage, self.hass).async_render({"grok_voice": True}, parse_result=False)
        treffer = re.search(r"„(Hello,[^“]*)“", anweisung)
        ws = await self.verbinden()
        try:
            await ws.send_json({"type": "session.update", "session": {
                "instructions": anweisung, "voice": self.stimme, "reasoning": {"effort": "high"},
                "turn_detection": {"type": "server_vad"}, "tools": werkzeug_schemas(),
                "audio": {"input": {"format": format_, "transcription": {"keyterms": namen(self.hass)}}, "output": {"format": format_}}}})
            await _warte_auf_update(ws)
        except BaseException:
            await ws.close()
            raise
        return ws, treffer.group(1) if treffer else BEGRUESSUNG

    # --- Überwachung -------------------------------------------------------------------------------------------------------
    def stoerung(self) -> str:
        """Leer, wenn alles geht; sonst, was fehlt (für den Sensor „Empfang Störung“ und die Plakette)."""
        gruende, jetzt = [], time.monotonic()
        if not self.angemeldet and self.anmelde_fehler_seit is not None and jetzt - self.anmelde_fehler_seit >= MELDEN_NACH:
            gruende.append("an der Station nicht angemeldet")
        if self.xai.startswith(("abgelehnt", "gesperrt")):
            gruende.append("xAI-Schlüssel " + self.xai)
        elif jetzt - self.xai_ok_seit > XAI_STILL:
            gruende.append("xAI seit über %d h nicht erreichbar" % (XAI_STILL // 3600))
        return "; ".join(gruende)

    def xai_setzen(self, zustand: str) -> None:
        """Ergebnis einer Prüfung des Schlüssels; Beginn und Ende eines Problems je einmal aufs Handy."""
        vorher = self.xai.startswith(("abgelehnt", "gesperrt"))
        jetzt = zustand.startswith(("abgelehnt", "gesperrt"))
        self.xai = zustand
        if zustand == "ok":
            self.xai_ok_seit = time.monotonic()
        if jetzt and not vorher:
            _LOGGER.warning("Grok Voice: xAI-Schlüssel %s", zustand)
            _mitschrift_melden(self.hass, "xAI-Schlüssel %s; der oberste Knopf geht nicht" % zustand)
        elif vorher and zustand == "ok":
            _mitschrift_melden(self.hass, "xAI-Schlüssel wieder in Ordnung")
        _stand(self.hass, xai=zustand)

    async def schluessel_pruefen(self) -> None:
        sitzung = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(15):
                async with sitzung.get(SCHLUESSEL_URL, headers={"Authorization": "Bearer " + self.schluessel}) as r:
                    if r.status in (400, 401, 403):
                        self.xai_setzen("abgelehnt (HTTP %d)" % r.status)
                        return
                    r.raise_for_status()
                    d = await r.json()
        except Exception as err:  # noqa: BLE001  nicht erreichbar zählt erst nach XAI_STILL als Störung
            self.xai = "nicht erreichbar (%s)" % type(err).__name__
            _stand(self.hass, xai=self.xai)
            return
        gesperrt = [k for k in ("api_key_blocked", "api_key_disabled", "team_blocked") if d.get(k)]
        self.xai_setzen("gesperrt (%s)" % ", ".join(gesperrt) if gesperrt else "ok")

    async def schluessel_dauernd(self) -> None:
        while True:
            await self.schluessel_pruefen()
            await asyncio.sleep(XAI_PRUEFEN)

    # --- Anmeldung an der Station -------------------------------------------------------------------------------------------
    def kontakt(self) -> str:
        return f"<sip:{self.kennung}@{self.lokal}:{self.port}>"

    async def anmelden(self, gueltig: int) -> int:
        """Ein REGISTER (mit Digest, wenn die Station fragt); → gewährte Sekunden. Wirft bei Ablehnung oder ohne Antwort."""
        self.lokal = await self.hass.async_add_executor_job(lokale_adresse, self.station)
        uri, aor = f"sip:{self.station}", f"<sip:{self.kennung}@{self.station}>"
        kopf_auth: tuple[str, str] | None = None
        for _ in range(2):
            self._reg_cseq += 1
            zeilen = [f"REGISTER {uri} SIP/2.0", f"Via: SIP/2.0/UDP {self.lokal}:{self.port};branch=z9hG4bK{secrets.token_hex(8)};rport",
                      "Max-Forwards: 70", f"From: {aor};tag={self._reg_tag}", f"To: {aor}", f"Call-ID: {self._reg_call_id}",
                      f"CSeq: {self._reg_cseq} REGISTER", f"Contact: {self.kontakt()}", f"Expires: {gueltig}",
                      "Allow: INVITE, ACK, BYE, CANCEL, OPTIONS, INFO", "User-Agent: tuer_assistent"]
            if kopf_auth:
                zeilen.append("%s: %s" % kopf_auth)
            erste, felder = await self._transaktion(("\r\n".join(zeilen + ["Content-Length: 0", "", ""])).encode(), self._reg_cseq)
            code = int(erste.split()[1]) if len(erste.split()) > 1 and erste.split()[1].isdigit() else 0
            if code in (401, 407) and kopf_auth is None:
                herausforderung = feld(felder, "www-authenticate" if code == 401 else "proxy-authenticate")
                self._nc += 1
                kopf_auth = ("Authorization" if code == 401 else "Proxy-Authorization",
                             digest("REGISTER", uri, self.kennung, self.passwort, herausforderung, self._nc))
                continue
            if 200 <= code < 300:
                if gueltig == 0:
                    return 0
                eigen = f"{self.lokal}:{self.port}"
                for w in [x for n, x in felder if n == "contact"]:
                    for teil in w.split(","):
                        m = re.search(r";\s*expires=(\d+)", teil)
                        if eigen in teil and m:
                            return int(m.group(1))
                wert = feld(felder, "expires")
                return int(wert) if wert.isdigit() else gueltig
            raise RuntimeError("Station antwortet %s" % (erste[8:60] or "nichts Lesbares"))
        raise RuntimeError("Anmeldung abgelehnt (Kennung oder Passwort)")

    async def _transaktion(self, nachricht: bytes, cseq: int) -> tuple[str, list]:
        """Schickt ein REGISTER und wartet auf die endgültige Antwort; wiederholt nach WIEDERHOLEN s."""
        schluessel = (self._reg_call_id, cseq)
        fertig = self.hass.loop.create_future()
        self._antworten[schluessel] = fertig
        try:
            for warte in (*WIEDERHOLEN, 1.0):
                self.senden(nachricht, (self.station, self.station_port))
                try:
                    return await asyncio.wait_for(asyncio.shield(fertig), warte)
                except TimeoutError:
                    continue
            raise TimeoutError("keine Antwort der Station")
        finally:
            self._antworten.pop(schluessel, None)

    async def anmelden_dauernd(self) -> None:
        """Hält die Anmeldung: erneuert nach 80 % der Gültigkeit, nach Fehlern mit wachsendem Abstand; meldet einen langen Ausfall."""
        gemeldet, versuch = False, 0
        while True:
            try:
                gewaehrt = await self.anmelden(ABLAUF)
                if not self.angemeldet:
                    _LOGGER.info("Grok Voice: an der Station als %s angemeldet (%d s)", self.kennung, gewaehrt)
                self.angemeldet = True
                _stand(self.hass, grok_voice="angemeldet als %s" % self.kennung)
                if gemeldet:
                    _mitschrift_melden(self.hass, "wieder an der Station angemeldet")
                self.anmelde_fehler_seit, gemeldet, versuch = None, False, 0
                await asyncio.sleep(max(ERNEUERN_MIN, min(gewaehrt * 0.8, gewaehrt - 10.0)))
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001  jeder Fehler: später neu versuchen
                grund = _text(err)[:100]
                if self.angemeldet or self.anmelde_fehler_seit is None:
                    _LOGGER.warning("Grok Voice: Anmeldung an der Station fehlgeschlagen (%s)", grund)
                self.angemeldet = False
                _stand(self.hass, grok_voice="nicht angemeldet: " + grund)
                self.anmelde_fehler_seit = self.anmelde_fehler_seit or time.monotonic()
                if not gemeldet and time.monotonic() - self.anmelde_fehler_seit >= MELDEN_NACH:
                    gemeldet = True
                    _mitschrift_melden(self.hass, "an der Station nicht angemeldet (%s); der oberste Knopf geht nicht" % grund)
                await asyncio.sleep(WARTEN[min(versuch, len(WARTEN) - 1)])
                versuch += 1

    # --- SIP ----------------------------------------------------------------------------------------------------------------
    def connection_made(self, transport) -> None:
        self.transport = transport

    def senden(self, daten: bytes, adresse) -> None:
        if self.transport is not None:
            self.transport.sendto(daten, adresse)

    def datagram_received(self, daten: bytes, adresse) -> None:
        if adresse[0] != self.station:  # nur die Station; alles andere ungelesen verwerfen
            return
        try:
            erste, felder, rumpf = zerlege(daten)
        except Exception:  # noqa: BLE001
            return
        if erste.startswith("SIP/2.0"):
            cseq = feld(felder, "cseq").split()
            if len(cseq) == 2 and cseq[1] == "REGISTER" and cseq[0].isdigit():
                code = erste.split()[1] if len(erste.split()) > 1 else ""
                warten = self._antworten.get((feld(felder, "call-id"), int(cseq[0])))
                if warten is not None and not warten.done() and not code.startswith("1"):
                    warten.set_result((erste, felder))
            elif len(cseq) == 2 and cseq[1] == "BYE" and (aufgabe := self.byes.pop(feld(felder, "call-id"), None)):
                aufgabe.cancel()
            return
        methode = erste.split(" ", 1)[0]
        ruf = self.ruf if self.ruf is not None and self.ruf.call_id == feld(felder, "call-id") else None
        if methode == "INVITE":
            self._invite(felder, rumpf, adresse, ruf)
        elif methode == "ACK":
            if ruf is not None:
                ruf.bestaetigt = True
        elif methode == "BYE":
            self.senden(antwort(felder, 200, "OK"), adresse)
            if ruf is not None:
                self.hass.async_create_task(ruf.beenden("Station hat aufgelegt", bye=False))
        elif methode == "CANCEL":
            self.senden(antwort(felder, 200, "OK"), adresse)
            if ruf is not None and not ruf.angenommen:
                self.senden(antwort(ruf.felder, 487, "Request Terminated", to_tag=ruf.tag), adresse)
                self.hass.async_create_task(ruf.beenden("abgebrochen", bye=False))
        elif methode in ("OPTIONS", "INFO", "NOTIFY", "MESSAGE"):
            self.senden(antwort(felder, 200, "OK"), adresse)
        else:
            self.senden(antwort(felder, 501, "Not Implemented"), adresse)

    def _invite(self, felder, rumpf: str, adresse, ruf: Ruf | None) -> None:
        if ruf is not None:
            if ruf.angenommen and feld(felder, "cseq") != feld(ruf.felder, "cseq"):  # neues INVITE im Gespräch: alles bleibt, wie es ist
                self.senden(antwort(felder, 200, "OK", to_tag=ruf.tag, rumpf=ruf.sdp, kontakt=self.kontakt()), adresse)
            elif ruf.letzte_antwort is not None:  # Wiederholung desselben INVITE
                self.senden(ruf.letzte_antwort, adresse)
            return
        if self.ruf is not None:
            self.senden(antwort(felder, 486, "Busy Here", to_tag=secrets.token_hex(6)), adresse)
            return
        neu = Ruf(self, felder, adresse, rumpf)
        self.hass.bus.async_fire(EREIGNIS, {"ergebnis": "klingel"})
        if neu.codec is None or not neu.angebot.host or not neu.angebot.port:
            angebot = ", ".join(" ".join(m[:1] + m[3:]) for m in neu.angebot.medien) or "keins"
            _LOGGER.warning("Grok Voice: kein G.711 im Angebot der Station (%s)", angebot)
            self.senden(antwort(felder, 488, "Not Acceptable Here", to_tag=neu.tag), adresse)
            self.hass.bus.async_fire(EREIGNIS, {"ergebnis": "abgelehnt", "grund": "kein passender Codec: " + angebot})
            neu.grund = "nicht angenommen: kein passender Ton im Angebot der Station (%s)" % angebot
            neu._ende_melden()
            return
        self.ruf = neu
        self.senden(antwort(felder, 100, "Trying"), adresse)
        neu.letzte_antwort = antwort(felder, 180, "Ringing", to_tag=neu.tag)
        self.senden(neu.letzte_antwort, adresse)
        self.hass.async_create_task(neu.starten())

    def bye(self, ruf: Ruf) -> None:
        ruf.cseq += 1
        von = feld(ruf.felder, "to")
        if ";tag=" not in von:
            von += ";tag=" + ruf.tag
        kontakt = re.search(r"<([^>]+)>", feld(ruf.felder, "contact") or "")
        ziel = kontakt.group(1) if kontakt else (re.search(r"<([^>]+)>", feld(ruf.felder, "from")) or [None, "sip:" + self.station])[1]
        nachricht = "\r\n".join([
            f"BYE {ziel} SIP/2.0", f"Via: SIP/2.0/UDP {self.lokal}:{self.port};branch=z9hG4bK{secrets.token_hex(8)};rport",
            "Max-Forwards: 70", "From: " + von, "To: " + feld(ruf.felder, "from"), "Call-ID: " + ruf.call_id,
            f"CSeq: {ruf.cseq} BYE", "Content-Length: 0", "", ""]).encode()

        async def wiederholen() -> None:
            for warte in (0, 0.5, 1, 2):
                await asyncio.sleep(warte)
                self.senden(nachricht, ruf.adresse)
            self.byes.pop(ruf.call_id, None)

        self.byes[ruf.call_id] = self.hass.async_create_task(wiederholen())

    def auflegen(self) -> bool:
        if self.ruf is None or not self.ruf.lebt:
            return False
        self.ruf.auflegen()
        return True

    async def stoppen(self) -> None:
        if self.ruf is not None:
            await self.ruf.beenden("Home Assistant hält an")
        for aufgabe in (self.anmeldung, self.pruefung):
            if aufgabe is not None:
                aufgabe.cancel()
        if self.angemeldet:
            try:
                async with asyncio.timeout(2):
                    await self.anmelden(0)
            except Exception:  # noqa: BLE001  abmelden ist Höflichkeit; die Station vergisst die Anmeldung nach 60 s ohnehin
                pass
            self.angemeldet = False
        for aufgabe in list(self.byes.values()):
            aufgabe.cancel()
        if self.transport is not None:
            self.transport.close()


async def async_starten(hass: HomeAssistant, einstellungen: dict) -> Bruecke | None:
    """Startet die Innenstation; ohne Schlüssel, Station oder Passwort oder bei belegtem Port nicht (dann bleibt der Knopf stumm)."""
    werte = {k: str(einstellungen.get(k) or "").strip() for k in ("schluessel", "station", "kennung", "passwort", "stimme")}
    fehlt = [k for k in ("schluessel", "station", "passwort") if not werte[k]]
    if fehlt:
        _LOGGER.warning("Grok Voice: es fehlt %s in configuration.yaml; ohne Grok Voice weiter", ", ".join(fehlt))
        return None
    try:
        station = await hass.async_add_executor_job(socket.gethostbyname, werte["station"])
    except OSError as err:
        _LOGGER.warning("Grok Voice: Station nicht auflösbar (%s); ohne Grok Voice weiter", err)
        return None
    bruecke = Bruecke(hass, schluessel=werte["schluessel"], station=station, kennung=werte["kennung"] or "9904",
                      passwort=werte["passwort"], port=int(einstellungen.get("port") or 5062),
                      station_port=int(einstellungen.get("station_port") or 5060), stimme=werte["stimme"] or "eve")
    try:
        await asyncio.get_running_loop().create_datagram_endpoint(lambda: bruecke, local_addr=("0.0.0.0", bruecke.port))
    except OSError as err:
        _LOGGER.warning("Grok Voice: Port %s nicht frei (%s); ohne Grok Voice weiter", bruecke.port, err)
        return None
    bruecke.anmeldung = hass.async_create_background_task(bruecke.anmelden_dauernd(), "tuer_assistent Anmeldung")
    bruecke.pruefung = hass.async_create_background_task(bruecke.schluessel_dauernd(), "tuer_assistent Schlüssel")
    _LOGGER.info("Grok Voice: Innenstation %s auf Port %s", bruecke.kennung, bruecke.port)
    return bruecke
