"""Weiterleitung aufs Telefon über einen eigenen SIP-Zugang (Wort des Betreibers vom 21.11.2026: „trage es ein als Möglichkeit so das
nun der Tür Assistent wenn jemand sagt es wäre wichtig weiterleitet. und schau das ich mit 1 die Tür öffnen kann“).

Ablauf (sprache.py ruft es): Ruft der Empfang bewohner_rufen, ist ein Zugang eingetragen und gilt „Weiterleiten, wenn“, ruft die
Integration über den Zugang die eingetragene Nummer an. Der Besucher hört nach dem Satz des Empfangs den Freiton; nimmt der Bewohner
ab, geht der Ton zwischen Station und Telefon hin und her (ohne xAI, ohne Umrechnen: angeboten wird nur der Codec der Station). Drückt
er eine Taste, feuert das Ereignis `tuer_assistent_taste` mit `taste` (und `probe`), mehr nicht: Was eine Taste bewirkt (1 = Haustür
auf), steht in einer Automation der Anlage. Tasten gibt es nur in Anrufen, die die Integration selbst gewählt hat; ein Anruf auf den
Zugang wird abgewiesen. Nimmt niemand ab (KLINGELN s, besetzt, abgelehnt, Störung), spricht der Empfang weiter.
Der Dienst `tuer_assistent.anruf_testen` wählt ohne Besucher: Signaltöne, jede erkannte Taste quittiert ein hoher Ton.

SIP über UDP: REGISTER mit Digest vor dem Anruf, abgemeldet danach; INVITE mit Digest, ACK, CANCEL, BYE in beide Richtungen; re-INVITE,
INFO und OPTIONS im Gespräch werden beantwortet. Tasten nach RFC 4733 (telephone-event) oder per SIP INFO. Hinter dem Router (NAT):
Via mit rport, Ton geht sofort nach der Annahme raus (der Anbieter lernt daran den Rückweg), alle 15 s ein Lebenszeichen an den Server.
Zugangsdaten und Nummer stehen nur in den Einstellungen des Eintrags, nie im Log; der Log nennt nur Ergebnisse.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
import math
import re
import secrets
import socket
import time

from .sip import Codec, antwort, digest, feld, rtp_nutzlast, sdp_lesen, zerlege

_LOGGER = logging.getLogger(__name__)
TASTE = "tuer_assistent_taste"
KLINGELN = 25  # s, bis der Bewohner abnimmt; die Mailbox des Handys nimmt oft nach 15 bis 30 s ab
ANMELDEN = 180  # s Gültigkeit der Anmeldung beim Anbieter (länger dauert kein Ruf der Station)
WIEDERHOLEN = (0.5, 1.0, 2.0, 4.0)  # s bis zur nächsten Wiederholung einer Anfrage ohne Antwort; danach aufgeben
STILL = 10  # s ohne Ton vom Anbieter im Gespräch: Verbindung verloren
LEBENSZEICHEN = 15  # s
PROBE = 30  # s Signaltöne im Probeanruf
TEL = 101  # Nutzlast-Typ für Tasten (telephone-event) im eigenen Angebot
TASTEN = "0123456789*#ABCD"
ALLE = (Codec(8, "PCMA"), Codec(0, "PCMU"))


@dataclass(frozen=True)
class Zugang:
    """Der SIP-Zugang aus den Einstellungen: Server (Name, optional mit :Port), Benutzer, Passwort und die Nummer, die gewählt wird."""

    server: str
    nutzer: str
    passwort: str
    ziel: str

    @property
    def host(self) -> str:
        return re.sub(r":\d+$", "", self.server)

    @property
    def port(self) -> int:
        m = re.search(r":(\d+)$", self.server)
        return int(m.group(1)) if m else 5060


def nummer(text: object) -> str:
    """Telefonnummer zum Wählen: ohne Leerzeichen und Striche, „+“ als „00“; leer, wenn es keine ist."""
    t = re.sub(r"[\s\-/().]", "", str(text or ""))
    if t.startswith("+"):
        t = "00" + t[1:]
    return t if re.fullmatch(r"\d{3,20}", t) else ""


FELDER = ("sip_server", "sip_nutzer", "sip_passwort", "ziel")  # erst alle vier zusammen leiten weiter


def stand(werte: Mapping) -> str:
    """Für Maske und Diagnose: eingerichtet, aus, oder was fehlt (nie die Werte)."""
    namen = {"sip_server": "SIP-Server", "sip_nutzer": "Benutzer", "sip_passwort": "Passwort", "ziel": "Nummer"}
    fehlt = [namen[k] for k in FELDER if not werte.get(k)]
    if len(fehlt) == len(FELDER):
        return "aus"
    if werte.get("ziel") and not nummer(werte.get("ziel")):
        fehlt.append("gültige Nummer")
    return "unvollständig, es fehlt: " + ", ".join(fehlt) if fehlt else "eingerichtet"


def zugang(werte: Mapping) -> Zugang | None:
    """Der Zugang aus den Einstellungen, wenn Server, Benutzer, Passwort und eine gültige Nummer da sind, sonst None."""
    z = Zugang(str(werte.get("sip_server") or "").strip(), str(werte.get("sip_nutzer") or "").strip(),
               str(werte.get("sip_passwort") or ""), nummer(werte.get("ziel")))
    return z if z.server and z.nutzer and z.passwort and z.ziel else None


# --- Töne ---------------------------------------------------------------------------------------------------------------------
_A_ENDE = (0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF)
_U_ENDE = (0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF)


def _alaw(pcm: int) -> int:
    """16 bit linear → A-law (G.711)."""
    pcm >>= 3
    if pcm >= 0:
        maske = 0xD5
    else:
        maske, pcm = 0x55, -pcm - 1
    seg = next(i for i, e in enumerate(_A_ENDE) if pcm <= e)  # 16 bit: höchstens 0xFFF, also Segment 7
    return ((seg << 4) | ((pcm >> 1) & 0x0F if seg < 2 else (pcm >> seg) & 0x0F)) ^ maske


def _ulaw(pcm: int) -> int:
    """16 bit linear → µ-law (G.711)."""
    pcm >>= 2
    if pcm < 0:
        maske, pcm = 0x7F, -pcm
    else:
        maske = 0xFF
    pcm = min(pcm, 8159) + 33
    seg = next((i for i, e in enumerate(_U_ENDE) if pcm <= e), 8)
    if seg >= 8:
        return 0x7F ^ maske
    return ((seg << 4) | ((pcm >> (seg + 1)) & 0x0F)) ^ maske


def klang(codec: Codec, hz: tuple[float, ...], an: float, aus: float, pegel: float = 0.2) -> bytes:
    """Ein Ton in G.711: an s die Frequenzen gemischt, danach aus s Stille."""
    kodieren = _alaw if codec.name == "PCMA" else _ulaw
    werte = bytearray(kodieren(int(pegel * 32767 * sum(math.sin(2 * math.pi * f * i / 8000) for f in hz) / len(hz)))
                      for i in range(int(8000 * an)))
    return bytes(werte) + bytes([codec.stille]) * int(8000 * aus)


def freiton(codec: Codec) -> bytes:
    """Der deutsche Freiton: 425 Hz, 1 s an, 4 s aus."""
    return klang(codec, (425,), 1.0, 4.0)


# --- SDP ----------------------------------------------------------------------------------------------------------------------
def sdp_angebot(codecs: tuple[Codec, ...], host: str, port: int) -> str:
    sitzung = secrets.randbelow(10**9)
    typen = " ".join(str(c.pt) for c in codecs)
    return (f"v=0\r\no=- {sitzung} {sitzung} IN IP4 {host}\r\ns=Tuer\r\nc=IN IP4 {host}\r\nt=0 0\r\n"
            f"m=audio {port} RTP/AVP {typen} {TEL}\r\n" + "".join(f"a=rtpmap:{c.pt} {c.name}/8000\r\n" for c in codecs)
            + f"a=rtpmap:{TEL} telephone-event/8000\r\na=fmtp:{TEL} 0-15\r\na=ptime:20\r\na=sendrecv\r\n")


def tasten_typ(rumpf: str) -> int | None:
    """Nutzlast-Typ von telephone-event in einer SDP-Antwort, sonst None."""
    m = re.search(r"a=rtpmap:(\d+)\s+telephone-event/8000", rumpf, re.IGNORECASE)
    return int(m.group(1)) if m else None


def info_taste(felder, rumpf: str) -> str:
    """Taste aus einem SIP INFO (application/dtmf-relay „Signal=1“ oder application/dtmf „1“), sonst leer."""
    art = feld(felder, "content-type").lower()
    m = re.search(r"signal\s*=\s*([0-9*#A-Da-d])", rumpf, re.IGNORECASE) if "dtmf-relay" in art else (
        re.fullmatch(r"\s*([0-9*#A-Da-d])\s*", rumpf) if "dtmf" in art else None)
    return m.group(1).upper() if m else ""


# --- Anruf --------------------------------------------------------------------------------------------------------------------
class _Udp(asyncio.DatagramProtocol):
    def __init__(self, ziel: Callable[[bytes, tuple], None]) -> None:
        self.ziel = ziel

    def datagram_received(self, daten: bytes, adresse) -> None:
        try:
            self.ziel(daten, adresse)
        except Exception:  # noqa: BLE001  ein kaputtes Paket darf den Anruf nicht stören
            _LOGGER.debug("Weiterleitung: Paket verworfen", exc_info=True)


class Anruf:
    """Ein Anruf über den Zugang: anmelden, wählen, Ton in beide Richtungen, Tasten, auflegen. Jeder Anruf hat eigene Sockel."""

    def __init__(self, hass, z: Zugang, codecs: tuple[Codec, ...], *, vom_telefon: Callable[[bytes], None] | None = None,
                 probe: bool = False, schritt: Callable[[str], None] | None = None) -> None:
        self.hass, self.z, self.codecs, self.probe = hass, z, codecs, probe
        self.vom_telefon = vom_telefon  # bekommt jedes Ton-Paket vom Telefon (Nutzlast im Codec der Station)
        self.schritt = schritt or (lambda _text: None)
        self.codec: Codec | None = None
        self.server = ""  # Adresse des Servers, bei jedem Anruf neu aufgelöst
        self.lokal = "0.0.0.0"
        self.sip = self.rtp = None
        self.sip_port = self.rtp_port = 0
        self.call_id, self.tag = secrets.token_hex(10), secrets.token_hex(6)
        self.reg_call_id, self.reg_tag = secrets.token_hex(10), secrets.token_hex(6)
        self.cseq = 1 + secrets.randbelow(1000)
        self.warten: dict[tuple[str, int, str], asyncio.Queue] = {}
        self.angemeldet = False
        self.zustand = "neu"  # neu, waehlt, klingelt, verbunden, ende
        self.invite_cseq = 0
        self.invite_branch = ""
        self.ack_200: bytes | None = None
        self.gegen_tag = ""
        self.gegen_ziel = ""
        self.route: list[str] = []
        self.ziel_rtp: tuple[str, int] | None = None
        self.tel: int | None = None
        self.puffer = bytearray()  # Ton zum Telefon
        self.puffern = True
        self.quittung = b""
        self.tasten: list[str] = []
        self.letzte_taste: tuple[str, float] = ("", 0.0)
        self.rtp_zeit: int | None = None
        self.zuletzt_rtp = 0.0
        self.pakete_rein = self.pakete_raus = 0
        self.ende_grund = ""
        self.zu_ende = asyncio.Event()
        self.aufgaben: list[asyncio.Task] = []
        self.signal = b""
        self.signal_pos = 0

    # --- Sockel und Senden --------------------------------------------------------------------------------------------------------
    async def _oeffnen(self) -> None:
        self.server, self.lokal = await self.hass.async_add_executor_job(_adressen, self.z.host, self.z.port)
        loop = asyncio.get_running_loop()
        self.sip, _ = await loop.create_datagram_endpoint(lambda: _Udp(self._sip_rein), local_addr=("0.0.0.0", 0))
        self.rtp, _ = await loop.create_datagram_endpoint(lambda: _Udp(self._ton_rein), local_addr=("0.0.0.0", 0))
        self.sip_port = self.sip.get_extra_info("sockname")[1]
        self.rtp_port = self.rtp.get_extra_info("sockname")[1]

    def _senden(self, daten: bytes) -> None:
        if self.sip is not None:
            self.sip.sendto(daten, (self.server, self.z.port))

    def _aor(self) -> str:
        return f"<sip:{self.z.nutzer}@{self.z.host}>"

    def _kontakt(self) -> str:
        return f"<sip:{self.z.nutzer}@{self.lokal}:{self.sip_port}>"

    def _anfrage(self, methode: str, uri: str, *, call_id: str, cseq: int, von_tag: str, an: str, branch: str,
                 kopf: tuple[str, ...] = (), rumpf: str = "", cseq_methode: str = "") -> bytes:
        zeilen = [f"{methode} {uri} SIP/2.0", f"Via: SIP/2.0/UDP {self.lokal}:{self.sip_port};branch={branch};rport",
                  "Max-Forwards: 70", f"From: {self._aor()};tag={von_tag}", "To: " + an, f"Call-ID: {call_id}",
                  f"CSeq: {cseq} {cseq_methode or methode}", *kopf, "User-Agent: tuer_assistent"]
        if rumpf:
            zeilen.append("Content-Type: application/sdp")
        zeilen.append("Content-Length: %d" % len(rumpf.encode()))
        return ("\r\n".join(zeilen) + "\r\n\r\n" + rumpf).encode()

    async def _antwort_abwarten(self, schluessel: tuple[str, int, str], nachricht: bytes, frist: float,
                                vorlaeufig: Callable[[int, list, str], None] | None = None) -> tuple[int, list, str] | None:
        """Sendet die Anfrage (wiederholt, bis eine Antwort kommt) und wartet auf die endgültige; None nach `frist` s, wenn schon
        eine vorläufige kam (INVITE klingelt noch). Ohne jede Antwort: TimeoutError."""
        q = self.warten.setdefault(schluessel, asyncio.Queue())
        loop = asyncio.get_running_loop()
        ende, wiederholt, naechst, gehoert = loop.time() + frist, 0, loop.time(), False
        while True:
            jetzt = loop.time()
            if not gehoert and jetzt >= naechst:
                if wiederholt > len(WIEDERHOLEN):
                    raise TimeoutError("keine Antwort vom SIP-Server")
                self._senden(nachricht)
                naechst = jetzt + (WIEDERHOLEN[wiederholt] if wiederholt < len(WIEDERHOLEN) else 4.0)
                wiederholt += 1
            if gehoert and jetzt >= ende:
                return None
            bis = (ende if gehoert else min(naechst, ende + 30)) - loop.time()
            try:
                code, felder, rumpf = await asyncio.wait_for(q.get(), max(0.01, bis))
            except TimeoutError:
                continue
            if code < 200:
                gehoert = True
                if vorlaeufig is not None:
                    vorlaeufig(code, felder, rumpf)
                continue
            return code, felder, rumpf

    def _auth(self, code: int, felder, methode: str, uri: str) -> str:
        herausforderung = feld(felder, "www-authenticate" if code == 401 else "proxy-authenticate")
        return ("Authorization: " if code == 401 else "Proxy-Authorization: ") + digest(methode, uri, self.z.nutzer, self.z.passwort,
                                                                                         herausforderung, 1)

    # --- Anmeldung ----------------------------------------------------------------------------------------------------------------
    async def _registrieren(self, gueltig: int) -> int:
        """REGISTER (mit Digest); → SIP-Code der endgültigen Antwort."""
        uri, auth = f"sip:{self.z.host}", ""
        for _ in range(2):
            self.cseq += 1
            schluessel = (self.reg_call_id, self.cseq, "REGISTER")
            nachricht = self._anfrage("REGISTER", uri, call_id=self.reg_call_id, cseq=self.cseq, von_tag=self.reg_tag, an=self._aor(),
                                      branch="z9hG4bK" + secrets.token_hex(8),
                                      kopf=(f"Contact: {self._kontakt()}", f"Expires: {gueltig}", *([auth] if auth else [])))
            try:
                code, felder, _ = await self._antwort_abwarten(schluessel, nachricht, 10)
            finally:
                self.warten.pop(schluessel, None)
            if code in (401, 407) and not auth:
                auth = self._auth(code, felder, "REGISTER", uri)
                continue
            return code
        return 403

    # --- Wählen ---------------------------------------------------------------------------------------------------------------
    async def anrufen(self, klingeln: float = KLINGELN) -> str:
        """Anmelden und die Nummer wählen; → „angenommen“ oder warum nicht. Wirft nie."""
        try:
            await self._oeffnen()
            code = await self._registrieren(ANMELDEN)
            if not 200 <= code < 300:
                return "Anmeldung beim SIP-Server abgelehnt (%d)" % code if code not in (401, 403, 407) else (
                    "Anmeldung beim SIP-Server abgelehnt (Benutzer oder Passwort)")
            self.angemeldet = True
            self.schritt("beim SIP-Server angemeldet")
            return await self._waehlen(klingeln)
        except TimeoutError:
            return "keine Antwort vom SIP-Server"
        except OSError as err:
            return "SIP-Server nicht erreichbar (%s)" % type(err).__name__
        except Exception as err:  # noqa: BLE001  ein Fehler hier heißt nur: nicht weitergeleitet
            _LOGGER.warning("Weiterleitung: Fehler beim Wählen", exc_info=True)
            return "Fehler beim Wählen (%s)" % type(err).__name__

    async def _waehlen(self, klingeln: float) -> str:
        uri = f"sip:{self.z.ziel}@{self.z.host}"
        sdp = sdp_angebot(self.codecs, self.lokal, self.rtp_port)
        auth = ""
        self.zustand = "waehlt"
        for _ in range(2):
            self.cseq += 1
            self.invite_cseq, self.invite_branch = self.cseq, "z9hG4bK" + secrets.token_hex(8)
            schluessel = (self.call_id, self.cseq, "INVITE")
            an = f"<{uri}>"
            nachricht = self._anfrage("INVITE", uri, call_id=self.call_id, cseq=self.cseq, von_tag=self.tag, an=an, branch=self.invite_branch,
                                      kopf=(f"Contact: {self._kontakt()}", "Allow: INVITE, ACK, BYE, CANCEL, OPTIONS, INFO",
                                            *([auth] if auth else [])), rumpf=sdp)

            def vorlaeufig(code: int, felder, _rumpf: str) -> None:
                if code in (180, 183) and self.zustand == "waehlt":
                    self.zustand = "klingelt"
                    self.schritt("Telefon klingelt")

            try:
                ergebnis = await self._antwort_abwarten(schluessel, nachricht, klingeln, vorlaeufig)
                if ergebnis is None:  # klingelt, niemand nimmt ab
                    return await self._abbrechen(schluessel, an)
                code, felder, rumpf = ergebnis
            finally:  # Wiederholungen des 200 OK beantwortet _sip_rein mit dem ACK
                self.warten.pop(schluessel, None)
            if 200 <= code < 300:
                return self._angenommen(felder, rumpf, an)
            self._ack_fehler(felder)
            if code in (401, 407) and not auth:
                auth = self._auth(code, felder, "INVITE", uri)
                continue
            return {486: "besetzt", 600: "besetzt", 603: "abgelehnt", 480: "nicht erreichbar", 404: "Nummer unbekannt", 487: "abgebrochen",
                    403: "vom SIP-Server abgelehnt", 488: "kein gemeinsamer Ton"}.get(code, "nicht angenommen (%d)" % code)
        return "vom SIP-Server abgelehnt (Benutzer oder Passwort)"

    def _ack_fehler(self, felder) -> None:
        """ACK auf eine endgültige Antwort außer 2xx: gleicher Zweig, To mit dem Tag der Antwort."""
        self._senden(self._anfrage("ACK", f"sip:{self.z.ziel}@{self.z.host}", call_id=self.call_id, cseq=self.invite_cseq, von_tag=self.tag,
                                   an=feld(felder, "to"), branch=self.invite_branch))

    async def _abbrechen(self, schluessel: tuple[str, int, str], an: str) -> str:
        """CANCEL nach KLINGELN s; die 487 auf das INVITE wird bestätigt. Nimmt er genau jetzt ab, wird aufgelegt (BYE)."""
        uri = f"sip:{self.z.ziel}@{self.z.host}"
        c_schluessel = (self.call_id, self.invite_cseq, "CANCEL")
        cancel = self._anfrage("CANCEL", uri, call_id=self.call_id, cseq=self.invite_cseq, von_tag=self.tag, an=an, branch=self.invite_branch)
        try:
            await self._antwort_abwarten(c_schluessel, cancel, 4)
        except TimeoutError:
            pass
        finally:
            self.warten.pop(c_schluessel, None)
        q = self.warten.get(schluessel)
        try:
            while q is not None:
                code, felder, rumpf = await asyncio.wait_for(q.get(), 4)
                if code >= 200:
                    if 200 <= code < 300:  # doch noch abgenommen: bestätigen und gleich wieder auflegen
                        self._angenommen(felder, rumpf, an)
                        await self.auflegen("zu spät abgenommen")
                    else:
                        self._ack_fehler(felder)
                    break
        except TimeoutError:
            pass
        return "nicht abgenommen (%d s)" % KLINGELN

    def _angenommen(self, felder, rumpf: str, an: str) -> str:
        to = feld(felder, "to")
        m = re.search(r";\s*tag=([^;>\s]+)", to)
        self.gegen_tag = m.group(1) if m else ""
        kontakt = re.search(r"<([^>]+)>", feld(felder, "contact"))
        self.gegen_ziel = kontakt.group(1) if kontakt else f"sip:{self.z.ziel}@{self.z.host}"
        self.route = [r.strip() for n, w in reversed(felder) if n == "record-route" for r in reversed(w.split(","))]
        self.ack_200 = self._anfrage("ACK", self.gegen_ziel, call_id=self.call_id, cseq=self.invite_cseq, von_tag=self.tag, an=to,
                                     branch="z9hG4bK" + secrets.token_hex(8), kopf=tuple("Route: " + r for r in self.route))
        self._senden(self.ack_200)
        try:
            antwort_sdp = sdp_lesen(rumpf)
        except Exception:  # noqa: BLE001
            antwort_sdp = None
        gemeinsam = [c for c in (antwort_sdp.codecs if antwort_sdp else []) if c in self.codecs]
        if not gemeinsam or not antwort_sdp.host or not 0 < antwort_sdp.port < 65536:
            self.zustand = "verbunden"  # das auflegen() des Aufrufers schickt dann ein BYE
            return "kein gemeinsamer Ton"
        self.codec, self.ziel_rtp, self.tel = gemeinsam[0], (antwort_sdp.host, antwort_sdp.port), tasten_typ(rumpf)
        self.zustand, self.zuletzt_rtp = "verbunden", time.monotonic()
        if self.probe:
            self.signal = klang(self.codec, (660, 880), 0.15, 1.35)
        for name, arbeit in (("Takt", self._takt), ("Lebenszeichen", self._lebenszeichen)):
            self.aufgaben.append(asyncio.create_task(self._sicher(name, arbeit)))
        self.schritt("Telefon hat abgenommen (%s%s)" % (self.codec.name, ", Tasten per RTP" if self.tel is not None else ""))
        return "angenommen"

    async def _sicher(self, name: str, arbeit) -> None:
        try:
            await arbeit()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Weiterleitung: Fehler in %s", name)
            self.hass.async_create_task(self.auflegen("interner Fehler (%s)" % name))

    # --- Ton ----------------------------------------------------------------------------------------------------------------------
    def ton(self, nutzlast: bytes) -> None:
        """Ton vom Besucher (Codec der Station) zum Telefon; höchstens 0,4 s Vorrat."""
        self.puffer.extend(nutzlast)
        if len(self.puffer) > 3200:
            del self.puffer[:len(self.puffer) - 1600]

    async def _takt(self) -> None:
        """Alle 20 ms ein Paket zum Telefon: Quittung einer Taste, im Probeanruf die Signaltöne, sonst der Besucher oder Stille."""
        loop = asyncio.get_running_loop()
        seq, ts, ssrc = secrets.randbelow(65536), secrets.randbelow(2**32), secrets.randbelow(2**32)
        stille, naechst, erstes = bytes([self.codec.stille]) * 160, loop.time(), True
        while self.zustand == "verbunden":
            warte = naechst - loop.time()
            if warte > 0:
                await asyncio.sleep(warte)
            if loop.time() - naechst > 0.2:
                naechst = loop.time()
            if self.quittung:
                nutz, self.quittung = self.quittung[:160].ljust(160, stille[:1]), self.quittung[160:]
            elif self.probe:
                nutz = (self.signal[self.signal_pos:] + self.signal)[:160]
                self.signal_pos = (self.signal_pos + 160) % len(self.signal)
            elif len(self.puffer) >= 160 and not (self.puffern and len(self.puffer) < 480):
                nutz, self.puffern = bytes(self.puffer[:160]), False
                del self.puffer[:160]
            else:
                nutz, self.puffern = stille, True
            kopf = bytes([0x80, (0x80 if erstes else 0) | self.codec.pt]) + seq.to_bytes(2, "big") + ts.to_bytes(4, "big") + ssrc.to_bytes(4, "big")
            if self.rtp is not None and self.ziel_rtp is not None:
                self.rtp.sendto(kopf + nutz, self.ziel_rtp)
                self.pakete_raus += 1
            seq, ts, naechst, erstes = (seq + 1) & 0xFFFF, (ts + 160) & 0xFFFFFFFF, naechst + 0.02, False

    async def _lebenszeichen(self) -> None:
        """Hält die Zuordnung im Router für SIP offen (sonst erreicht ein BYE des Anbieters die Integration nach einer Weile nicht)."""
        while self.zustand == "verbunden":
            await asyncio.sleep(LEBENSZEICHEN)
            self._senden(b"\r\n\r\n")

    def _ton_rein(self, daten: bytes, adresse) -> None:
        if self.zustand != "verbunden" or self.ziel_rtp is None or adresse[0] != self.ziel_rtp[0]:
            return
        paket = rtp_nutzlast(daten)
        if paket is None:
            return
        self.zuletzt_rtp, self.pakete_rein = time.monotonic(), self.pakete_rein + 1
        typ, nutz = paket
        if self.codec is not None and typ == self.codec.pt:
            if self.vom_telefon is not None:
                self.vom_telefon(nutz)
        elif self.tel is not None and typ == self.tel and len(nutz) >= 4 and nutz[0] < len(TASTEN):
            zeit = int.from_bytes(daten[4:8], "big")
            if zeit != self.rtp_zeit:  # ein Druck: mehrere Pakete mit demselben Zeitstempel
                self.rtp_zeit = zeit
                self._taste(TASTEN[nutz[0]])

    def _taste(self, taste: str) -> None:
        jetzt = time.monotonic()
        if self.letzte_taste[0] == taste and jetzt - self.letzte_taste[1] < 0.6:  # derselbe Druck per RTP und per INFO
            return
        self.letzte_taste = (taste, jetzt)
        if len(self.tasten) >= 20:
            return
        self.tasten.append(taste)
        self.schritt("Taste %s" % taste)
        if self.codec is not None:
            self.quittung = klang(self.codec, (1400,), 0.25, 0.0, 0.15)
        self.hass.bus.async_fire(TASTE, {"taste": taste, "probe": self.probe})

    # --- SIP vom Server -----------------------------------------------------------------------------------------------------------
    def _sip_rein(self, daten: bytes, adresse) -> None:
        if adresse[0] != self.server or not daten.strip():
            return
        erste, felder, rumpf = zerlege(daten)
        if erste.startswith("SIP/2.0"):
            teile, cseq = erste.split(), feld(felder, "cseq").split()
            if len(teile) < 2 or not teile[1].isdigit() or len(cseq) != 2 or not cseq[0].isdigit():
                return
            code = int(teile[1])
            q = self.warten.get((feld(felder, "call-id"), int(cseq[0]), cseq[1]))
            if q is not None:
                q.put_nowait((code, felder, rumpf))
            elif cseq[1] == "INVITE" and 200 <= code < 300 and self.ack_200 is not None and feld(felder, "call-id") == self.call_id:
                self._senden(self.ack_200)  # Wiederholung des 200 OK: das ACK ging verloren
            return
        methode = erste.split(" ", 1)[0]
        unser = feld(felder, "call-id") == self.call_id and self.zustand in ("verbunden", "klingelt", "waehlt")
        if methode == "BYE" and unser:
            self._senden(antwort(felder, 200, "OK"))
            self.schritt("Telefon hat aufgelegt")
            self._beendet("aufgelegt")
        elif methode == "INFO" and unser:
            self._senden(antwort(felder, 200, "OK"))
            if (taste := info_taste(felder, rumpf)) and self.zustand == "verbunden":
                self._taste(taste)
        elif methode == "INVITE" and unser and self.zustand == "verbunden":  # re-INVITE (Sitzung auffrischen): alles bleibt
            sdp = sdp_angebot((self.codec,), self.lokal, self.rtp_port) if self.codec else ""
            self._senden(antwort(felder, 200, "OK", rumpf=sdp, kontakt=self._kontakt()))
        elif methode == "INVITE":  # ein Anruf auf den Zugang: nicht hier
            self._senden(antwort(felder, 486, "Busy Here", to_tag=secrets.token_hex(4)))
        elif methode in ("OPTIONS", "NOTIFY", "UPDATE") or (methode == "INFO"):
            self._senden(antwort(felder, 200, "OK"))
        elif methode == "CANCEL":
            self._senden(antwort(felder, 481, "Call/Transaction Does Not Exist"))
        elif methode != "ACK":
            self._senden(antwort(felder, 501, "Not Implemented"))

    def _beendet(self, grund: str) -> None:
        if not self.ende_grund:
            self.ende_grund = grund
        self.zustand = "ende"
        self.zu_ende.set()

    # --- Ende ---------------------------------------------------------------------------------------------------------------------
    async def ende(self, hoechstens: float) -> str:
        """Wartet im Gespräch, bis einer auflegt, kein Ton mehr kommt oder `hoechstens` s um sind; → Grund."""
        loop = asyncio.get_running_loop()
        bis = loop.time() + hoechstens
        while self.zustand == "verbunden":
            try:
                await asyncio.wait_for(self.zu_ende.wait(), max(0.01, min(1.0, bis - loop.time())))
            except TimeoutError:
                pass
            if self.zustand != "verbunden":
                break
            if time.monotonic() - self.zuletzt_rtp > STILL:
                return "kein Ton mehr vom Telefon (%d s)" % STILL
            if loop.time() >= bis:
                return "Höchstdauer"
        return self.ende_grund or "aufgelegt"

    async def auflegen(self, grund: str = "") -> None:
        """BYE (im Gespräch), Abmelden beim Server, Sockel zu. Mehrfach aufrufbar; wirft nie."""
        war = self.zustand
        self._beendet(grund or "aufgelegt")
        for a in self.aufgaben:
            if a is not asyncio.current_task():
                a.cancel()
        try:
            if war == "verbunden":
                self.cseq += 1
                schluessel = (self.call_id, self.cseq, "BYE")
                an = f"<sip:{self.z.ziel}@{self.z.host}>" + (f";tag={self.gegen_tag}" if self.gegen_tag else "")
                bye = self._anfrage("BYE", self.gegen_ziel, call_id=self.call_id, cseq=self.cseq, von_tag=self.tag, an=an,
                                    branch="z9hG4bK" + secrets.token_hex(8), kopf=tuple("Route: " + r for r in self.route))
                try:
                    await self._antwort_abwarten(schluessel, bye, 3)
                except TimeoutError:
                    pass
                finally:
                    self.warten.pop(schluessel, None)
            if self.angemeldet:
                self.angemeldet = False
                try:
                    async with asyncio.timeout(3):
                        await self._registrieren(0)
                except Exception:  # noqa: BLE001  der Server vergisst die Anmeldung nach ANMELDEN s ohnehin
                    pass
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Weiterleitung: Auflegen unvollständig", exc_info=True)
        finally:
            for s in (self.sip, self.rtp):
                if s is not None:
                    s.close()
            self.sip = self.rtp = None


def _adressen(host: str, port: int) -> tuple[str, str]:
    """Adresse des Servers und die eigene, von der aus er erreicht wird (UDP-connect sendet nichts)."""
    try:
        adresse = socket.gethostbyname(host)
    except OSError as err:
        raise OSError("SIP-Server nicht auflösbar") from err
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((adresse, port))
        return adresse, s.getsockname()[0]
    finally:
        s.close()


async def probe(hass, z: Zugang, *, klingeln: float = KLINGELN, dauer: float = PROBE) -> dict:
    """Probeanruf ohne Besucher: wählt, spielt Signaltöne, quittiert Tasten (Ereignis mit probe: true); → Ergebnis für den Dienst."""
    beginn = time.monotonic()
    ablauf: list[str] = []
    a = Anruf(hass, z, ALLE, probe=True, schritt=lambda t: ablauf.append("%.1f s %s" % (time.monotonic() - beginn, t)))
    ergebnis = await a.anrufen(klingeln)
    ende = ""
    try:
        if ergebnis == "angenommen":
            ende = await a.ende(dauer)
    finally:
        await a.auflegen(ende or ergebnis)
    return {"ergebnis": ergebnis, "ende": ende, "tasten": "".join(a.tasten), "sekunden": round(time.monotonic() - beginn),
            "ton": a.codec.name if a.codec else "", "pakete_rein": a.pakete_rein, "pakete_raus": a.pakete_raus, "ablauf": ablauf}
