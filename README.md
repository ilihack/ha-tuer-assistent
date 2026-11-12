# Tür-Assistent („Empfang“) für Home Assistant

Ein Klingelknopf an einer Dahua-Türstation, hinter dem eine KI antwortet: Sie fängt Paketboten ab und schickt sie zur Paketbox. Sie sagt
Besuchern, wo sie klingeln müssen, gibt dem Bewohner Bescheid, nimmt Nachrichten an und legt nach der Verabschiedung auf. Im Haus kann sie
nichts schalten.

## So funktioniert es

```
Besucher drückt den Knopf
  → Türstation (Dahua, SIP-Server ihrer Innenstationen) ruft die Innenstation 9904
  → diese Integration ist als 9904 angemeldet (REGISTER mit Digest) und nimmt den Ruf an
      ├─ feuert sofort tuer_assistent_grok_voice {"ergebnis": "klingel"}
      ├─ verbindet sich mit der Echtzeit-Schnittstelle von xAI (Grok Voice: Erkennung, KI und Stimme in einem Schritt)
      │    Ton G.711 (A-law/µ-law, 8 kHz) unverändert in beide Richtungen, Paketlänge wie die Station (40 ms)
      │    drei Werkzeuge → Ereignis tuer_assistent_werkzeug → Automation: Handy klingeln lassen, Nachricht weitergeben, auflegen
      └─ am Ende: tuer_assistent_grok_voice {"ergebnis": "ende", "mitschrift", "grund", "sekunden", "angenommen"}
           → Automation: eine Meldung aufs Handy mit dem ganzen Gespräch, wenn es den Bewohner betrifft oder gestört war
```

- **Kein Ersatzweg:** Kommt xAI nicht binnen 5 s zustande, antwortet die Integration 503 und die Station beendet den Ruf. Der Grund
  steht in der Meldung am Ende.
- **Überwachung:** Den xAI-Schlüssel prüft die Integration beim Start und stündlich (`GET https://api.x.ai/v1/api-key`, kostet nichts).
  `binary_sensor.empfang_stoerung` geht an, wenn eines davon zutrifft:
  - seit 3 min nicht an der Station angemeldet
  - Schlüssel abgelehnt oder gesperrt
  - xAI seit 6 h nicht erreichbar
  - Grok Voice nicht gestartet
  
  Der Grund steht im Attribut `grund`. Beginn und Ende einer Störung melden sich je einmal. Eine Plakette auf dem Dashboard hängt man
  an diesen Sensor.
- **Vollduplex:** Wer dazwischenredet, bricht die Antwort ab. Die Begrüßung spielt xAI aber immer ganz.
- **Wächter:** Antwortet xAI 10 s nicht, wird aufgelegt und gemeldet. Bei 30 s Stille wird aufgelegt. Ein Ruf dauert höchstens 3 min,
  und es läuft immer nur ein Ruf.
- **Anmeldung:** Die Station gewährt 60 s; die Integration meldet sich nach 80 % davon erneut an. Nach einem Fehler versucht sie es nach
  5, 10, 20, 40 und dann alle 60 s wieder. Ist sie 3 min lang nicht angemeldet, kommt einmal eine Meldung und wieder eine, sobald es geht.
  Beim Anhalten meldet sie sich ab.
- **Nur die Station:** Den SIP-Port (UDP 5062) muss die Station erreichen, er ist im Hausnetz offen. Pakete von anderen Adressen
  verwirft die Integration deshalb ungelesen.

Daneben enthält die Integration die Bausteine für einen Text-Agenten hinter dem Assist-Weg des VoIP Stack. Das sind `stt.empfang`,
`conversation.empfang` (mit Ersatzantwort und Mitschrift), `tts.empfang` und `select.empfang_ki`. Für Grok Voice braucht man sie nicht.

## Werkzeuge der KI

| Werkzeug | Felder | Was passiert |
|---|---|---|
| `bewohner_rufen` | anliegen | Ereignis; die Automation lässt das Handy klingeln; danach legt die Integration auf (Station frei für die App) |
| `nachricht_weitergeben` | fuer, nachricht | Ereignis; die Automation schickt den Text aufs Handy (nur für den Bewohner, nie für Mieter) |
| `auflegen` | – | Ruf endet, sobald die Verabschiedung gespielt ist |

Die Werkzeuge rufen keinen Dienst und lesen keinen Zustand. Grenzen, die nicht vom Modell abhängen:
- höchstens 6 Ereignisse je Minute
- je Feld 300 druckbare Zeichen
- derselbe Aufruf mit denselben Feldern feuert binnen 20 s nur einmal ein Ereignis

xAI bekommt nur diese drei Funktionen, keine eigenen Werkzeuge von xAI (Websuche, MCP).

## Einrichten

1. Den Ordner `custom_components/tuer_assistent` nach `/config/custom_components/` kopieren. Alternativ geht HACS mit diesem Projekt als
   benutzerdefiniertem Repository; ein privates Projekt braucht dafür einen GitHub-Token.
2. An der Türstation eine Innenstation 9904 mit eigenem Passwort anlegen und sie dem Knopf zuordnen. In `__init__.py` steht in den
   Werkzeug-Beschreibungen der Name des Bewohners (hier „Muster“); anpassen.
3. `configuration.yaml`, Beispiel in `beispiele/configuration.yaml`:
   ```yaml
   tuer_assistent:
     agenten:                       # nur für den Text-Agenten-Weg; jeder Agent nur mit der Werkzeugliste „Tür-Assistent“
       conversation.tur_gemini_lite: 8
     grok_voice:
       schluessel: !secret xai_api_key
       station: !secret vto_eg_adresse
       passwort: !secret vto_9904_passwort
       # kennung: "9904"   port: 5062   station_port: 5060   stimme: eve
   ```
4. Die Anweisung (`beispiele/anweisung.jinja`, eine Jinja-Vorlage) beim Gesprächsagenten eintragen. Grok Voice nimmt sie von dem
   Agenten, der in `select.empfang_ki` gewählt ist, und rendert sie mit `grok_voice = true`. Namen, Adresse und Lage der Paketbox kommen
   aus Helfern (`beispiele/helfer.json`).
5. Die Automationen aus `beispiele/` einspielen:
   - `klingel_unten.json`: am Ende eines Rufs eine Meldung mit der Mitschrift, wenn sein Name fällt, ein Werkzeug für ihn lief oder
     der Empfang gestört war
   - `tuer_assistent_werkzeuge.json`: Handy, Nachricht, Auflegen
   - `tuer_assistent_mitschrift.json`: Beginn und Ende von Störungen aufs Handy (beim Text-Agenten auf Wunsch jeder Wortwechsel)
   
   Sie nutzen das Skript `script.meldung` der eigenen Anlage (Push aufs Handy).
6. Neu starten. `tuer_assistent.stand` zeigt im Attribut `grok_voice` den Wert „angemeldet als 9904“ und im Attribut `xai` den Wert
   „ok“; `binary_sensor.empfang_stoerung` steht auf aus.

## Kosten und Schutz

- xAI rechnet laut eigener Preisliste 5 Cent je Minute Gespräch ab. Ein Klingeln kostet damit höchstens rund 15 Cent. Im xAI-Konto ein
  Ausgabenlimit setzen.
- Schlüssel, Adresse der Station und Passwort gehören nur in `secrets.yaml`.
- Die KI öffnet nichts. Ob der Bewohner da ist, sagt sie nur, wenn er weg ist: Dann bietet sie an, eine Nachricht weiterzugeben oder,
  wenn es dringend ist, sein Handy klingeln zu lassen. Für die Mieter nimmt sie nichts an und gibt nichts weiter. Das regelt die
  Anweisung; die harten Grenzen setzen die Werkzeuge.

## Stand

Version 2.1.2 (11.11.2026): die Integration ist eigene Innenstation, kein VoIP Stack nötig. Nach einem Ruf kommt eine Meldung mit der
Mitschrift, wenn er den Bewohner betrifft; Schlüssel und Anmeldung werden überwacht. Die Anweisung folgt dem Leitfaden von xAI für
Grok Voice (Abschnitte, kurz); am 12.11. mit 157 simulierten Gesprächen nachgeschärft (ein Modell spielt drängende,
fremdsprachige und listige Besucher, ein zweites prüft): Sätze für Besucher beschrieben statt zitiert, damit sie in deren Sprache
kommen; eigene Regel für Hartnäckigkeit; „vor die Haustür“ nur für große Pakete ohne Unterschrift. Mit gestellter Station und gestelltem xAI
geprüft; mit dem echten Grok Voice über SIP-Proben geprüft. Am echten Klingeln ist die eigene Anmeldung noch nicht geprüft. Die Tests
liegen im Projektordner der Anlage, weil sie deren Prüfstand brauchen.
