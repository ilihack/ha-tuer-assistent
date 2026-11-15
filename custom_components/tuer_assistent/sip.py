"""Reine Hilfen für die Innenstation, ohne Zustand und ohne Home Assistant: SIP-Nachrichten zerlegen und beantworten, das SDP-Angebot
der Station lesen und beantworten, RTP-Pakete auspacken, Digest für die Anmeldung, die Adressen im Hausnetz. sprache.py nutzt sie
(und gibt sie unter demselben Namen weiter); geprüft in pruefung/tests/test_grok_voice.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import secrets
import socket

KURZ = {"v": "via", "f": "from", "t": "to", "i": "call-id", "m": "contact", "l": "content-length", "c": "content-type"}


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


def adressen(station: str) -> tuple[str, str]:
    """Adresse der Station und die eigene im Hausnetz, von der aus sie erreicht wird (UDP-connect sendet nichts). Ein Name wird bei
    jeder Anmeldung neu aufgelöst: Nach einem Stromausfall ist Home Assistant oft vor dem Router wieder da."""
    try:
        adresse = socket.gethostbyname(station)
    except OSError as err:
        raise OSError("Station nicht auflösbar") from err
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((adresse, 5060))
        return adresse, s.getsockname()[0]
    finally:
        s.close()
