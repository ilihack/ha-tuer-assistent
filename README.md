# Tür-Assistent („Empfang“) für Home Assistant

Ein Klingelknopf an einer Dahua-Türstation, hinter dem eine KI antwortet: Sie fängt Paketboten ab und schickt sie zur Paketbox. Sie sagt
Besuchern, wo sie klingeln müssen, gibt dem Bewohner Bescheid, nimmt Nachrichten an und legt nach der Verabschiedung auf. Im Haus kann sie
nichts schalten.

## Wofür

- **Zusteller:** in die Paketbox, an die richtige Klingel oder, ohne Unterschrift, vor die Haustür, ohne dass jemand im Haus gestört wird.
- **Besucher:** finden den richtigen Knopf; will jemand zum Bewohner, bekommt der eine Meldung aufs Handy.
- **Nachrichten:** Ein Besucher hinterlässt etwas für den Bewohner; es kommt als Meldung, dazu am Ende das ganze Gespräch als Text.
- **Abwesenheit:** Ist niemand da, sagt die KI das für den Bewohner (nicht für Mieter) und ruft ihn nur bei Dringendem.

## Unterstützte Geräte

- Getestet mit einer Dahua-Türstation (VTO mit vier Klingelknöpfen), die selbst SIP-Server ihrer Innenstationen ist. Jede Station, die
  eine Innenstation per SIP mit Digest anmelden lässt und G.711 (A-law oder µ-law, 8 kHz) anbietet, sollte gehen.
- Nicht unterstützt: Stationen, die nur über einen fremden SIP-Server oder nur mit anderen Codecs (Opus, G.722) sprechen; Video wird
  abgelehnt.
- Die KI ist Grok Voice von xAI (Echtzeit-Schnittstelle); ein xAI-Schlüssel mit Guthaben ist nötig.

## So funktioniert es

```
Besucher drückt den Knopf
  → Türstation (Dahua, SIP-Server ihrer Innenstationen) ruft die Innenstation 9904
  → diese Integration ist als 9904 angemeldet (REGISTER mit Digest) und nimmt den Ruf an
      ├─ feuert sofort tuer_assistent_grok_voice {"ergebnis": "klingel"}
      ├─ verbindet sich mit der Echtzeit-Schnittstelle von xAI (Grok Voice: Erkennung, KI und Stimme in einem Schritt)
      │    Ton G.711 (A-law/µ-law, 8 kHz) unverändert in beide Richtungen, Paketlänge wie von der Station angeboten
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
- **Wächter:** Jeder Zustand eines Rufs hat eine Frist, nach der aufgelegt wird:
  - 8 s kein Ton-Paket der Station (sie hat aufgelegt, ohne es zu sagen); nur, wenn die Station in den ersten 3 s ohne Pause
    gesendet hat, sonst endete bei einer Station mit Stille-Unterdrückung jedes Gespräch, sobald der Besucher schweigt
  - 10 s weder Ereignis noch Ton von xAI, obwohl xAI dran ist (wird gemeldet)
  - 60 s „Rede“ des Besuchers ohne erkanntes Ende (Lärm)
  - 20 s Stille; nach einer weitergegebenen Nachricht 8 s
  - 3 min Höchstdauer
- **Ein Ruf zur Zeit:** Ruft die Station neu an, ist der alte Ruf für sie vorbei; er wird beendet und der neue angenommen. Ein „besetzt“
  gibt es nicht.
- **Tagebuch:** Die letzten 30 Rufe stehen in `.storage/tuer_assistent.rufe`: Beginn, Dauer, Grund des Endes, Ton-Pakete, Wartezeiten,
  Werkzeuge, der Ablauf mit Zeiten und die Mitschrift. Im Log von Home Assistant steht je Ruf eine Zeile mit den Zahlen, nie mit dem,
  was der Besucher sagt.
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
| `nachricht_weitergeben` | fuer, nachricht | Ereignis; die Automation schickt den Text aufs Handy (nur für den Bewohner, nie für Mieter); nach 8 s Stille legt die Integration auf |
| `auflegen` | – | Ruf endet, sobald die Verabschiedung gespielt ist |

Die Werkzeuge rufen keinen Dienst und lesen keinen Zustand. Grenzen, die nicht vom Modell abhängen:
- höchstens 6 Ereignisse je Minute
- je Feld 300 druckbare Zeichen
- derselbe Aufruf mit denselben Feldern feuert binnen 20 s nur einmal ein Ereignis

xAI bekommt nur diese drei Funktionen, keine eigenen Werkzeuge von xAI (Websuche, MCP).

## Was die Integration bereitstellt

| Was | Name | Wozu |
|---|---|---|
| Zustand | `tuer_assistent.stand` | Anmeldung, xAI, letztes Werkzeug, letzter Ruf mit Grund des Endes |
| Sensor „Empfang Störung“ (Diagnose) | `binary_sensor.empfang_stoerung` | an, wenn der Knopf nicht gehen würde; Attribut `grund` |
| Auswahl „Empfang KI“ (Einstellung) | `select.empfang_ki` | von welchem Agenten Grok Voice die Anweisung nimmt |
| Erkennung, Stimme, Agent | `stt.empfang`, `tts.empfang`, `conversation.empfang` | nur für den Weg über einen VoIP Stack; bei neuen Einrichtungen aus |
| Dienst | `tuer_assistent.auflegen` | beendet das laufende Gespräch |
| Ereignis | `tuer_assistent_grok_voice` | `klingel`, `angenommen`, `abgelehnt`, `ende` (mit Mitschrift und Grund) |
| Ereignis | `tuer_assistent_werkzeug` | ein Werkzeug der KI wurde gerufen |
| Ereignis | `tuer_assistent_gespraech` | Beginn und Ende einer Störung (Feld `ersatz`) |
| Reparaturen | Einstellungen → Reparaturen | Schlüssel abgelehnt oder gesperrt; Anmeldung an der Station verloren; Warnung, dass Mitschriften gespeichert werden |
| Diagnose | am Eintrag der Integration | Zustand und Tagebuch der Rufe, ohne Schlüssel, Adresse, Namen und Mitschrift |

Alle Entitäten hängen an einem Gerät „Empfang“; Namen und Symbole kommen aus `translations/` und `icons.json` (deutsch und englisch).

## Woher die Daten kommen

- Rufe schiebt die Station selbst herein (SIP über UDP im Hausnetz); die Integration fragt dafür nichts ab.
- Die Anmeldung an der Station erneuert sie nach 80 % der gewährten Zeit.
- Den xAI-Schlüssel prüft sie beim Start und stündlich.
- Der Sensor „Empfang Störung“ liest alle 30 s nur den eigenen Zustand.

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

Einstellungen unter `grok_voice` in `configuration.yaml`:

| Name | Vorgabe | Bedeutung |
|---|---|---|
| `schluessel` | – | xAI-Schlüssel |
| `station` | – | Adresse der Türstation |
| `passwort` | – | Passwort der Innenstation an der Station |
| `kennung` | 9904 | Nummer der Innenstation |
| `port` | 5062 | eigener SIP-Port (UDP), den die Station erreichen muss |
| `station_port` | 5060 | SIP-Port der Station |
| `stimme` | eve | Stimme von Grok Voice |
| `mitschrift_speichern` | true | Mitschriften im Tagebuch; `false` hält sie heraus, auch aus den schon gespeicherten Rufen |

## Fehlersuche

1. `tuer_assistent.stand` ansehen: `grok_voice` („angemeldet als …“), `xai` („ok“), `letzter_ruf` (Zeit, Dauer, Grund des Endes).
2. Einstellungen → Reparaturen: Dort steht, wenn der Schlüssel abgelehnt ist oder die Anmeldung scheitert, und was zu tun ist.
3. Das Tagebuch `.storage/tuer_assistent.rufe` oder die Diagnose am Eintrag: je Ruf der Ablauf mit Zeiten. Typische Gründe des Endes:

| Grund | Bedeutung |
|---|---|
| aufgelegt nach Verabschiedung / nach dem Bescheid | normales Ende |
| Station hat aufgelegt | die Station hat das Gespräch beendet (bei Dahua nach 2 min) |
| Station sendet keinen Ton mehr | die Station hat beendet, ohne es zu sagen, oder das Netz ist weg |
| vom nächsten Klingeln abgelöst | die Station rief neu an, während der alte Ruf hier noch offen war |
| xAI antwortet nicht | xAI hängt; die Meldung am Ende nennt es als Störung |
| nicht angenommen: … | keine Verbindung zu xAI in 5 s, Schlüssel abgelehnt, oder kein G.711 im Angebot |
| 20 s Stille / 8 s Stille nach der Nachricht | niemand spricht mehr |

4. Bleibt der Knopf stumm und im Log steht nichts von „Grok Voice“: Der Abschnitt `grok_voice` fehlt oder ist unvollständig, oder der
   Port ist belegt (Warnung beim Start).

## Bekannte Grenzen

- Kein Ersatzweg: Ohne Internet oder ohne xAI bleibt der Knopf stumm (die Meldung am Ende und der Sensor sagen es).
- Ein Gespräch zur Zeit, höchstens 3 min; die Dahua-Station beendet von sich aus nach 2 min.
- Die KI kann sich verhören, besonders bei Namen; die Anweisung lässt sie nachfragen. Was sie sagt, regelt die Anweisung, nicht der Code.
- Einrichtung nur über `configuration.yaml`, keine Maske; eine Änderung braucht einen Neustart.
- Die Werkzeug-Beschreibungen in `__init__.py` nennen den Bewohner („Herrn Muster“); für eine andere Wohnung dort anpassen.
- Die Anweisung und die Beispiele sind deutsch und auf ein Haus mit drei Wohnungen zugeschnitten.

## Entfernen

1. Die Automationen aus `beispiele/` löschen.
2. In `configuration.yaml` den Abschnitt `tuer_assistent:` entfernen und neu starten.
3. Den Eintrag „Tür-Assistent“ unter Geräte & Dienste löschen, den Ordner `custom_components/tuer_assistent` und die Datei
   `.storage/tuer_assistent.rufe` entfernen.
4. An der Türstation die Innenstation 9904 löschen oder dem Knopf wieder eine andere Nummer geben.

## Kosten und Schutz

- xAI rechnet laut eigener Preisliste 5 Cent je Minute Gespräch ab. Ein Klingeln kostet damit höchstens rund 15 Cent. Im xAI-Konto ein
  Ausgabenlimit setzen.
- Schlüssel, Adresse der Station und Passwort gehören nur in `secrets.yaml`.
- Mitschriften: Das Tagebuch hält die letzten 30 Gespräche mit Text fest, unverschlüsselt in `.storage` und damit in jeder Sicherung.
  Dieselben Texte stehen in den Ereignissen der Integration, die der Recorder aufhebt (standardmäßig 10 Tage). Die Integration sagt
  das unter Reparaturen. Abschalten: `mitschrift_speichern: false`; aus dem Recorder heraus mit
  ```yaml
  recorder:
    exclude:
      event_types: [tuer_assistent_grok_voice, tuer_assistent_gespraech, tuer_assistent_werkzeug]
  ```
  Die Automationen bekommen die Ereignisse trotzdem.
- Die KI öffnet nichts. Ob der Bewohner da ist, sagt sie nur, wenn er weg ist: Dann bietet sie an, eine Nachricht weiterzugeben oder,
  wenn es dringend ist, sein Handy klingeln zu lassen. Für die Mieter nimmt sie nichts an und gibt nichts weiter. Das regelt die
  Anweisung; die harten Grenzen setzen die Werkzeuge.

## Stand

Version 2.4.0 (12.11.2026):

- Jede Sprache wie Deutsch: Das Ergebnis jedes Werkzeugs sagt dem Modell, in der Sprache des Besuchers zu antworten (vorher sprach es
  nach einem Werkzeug oft Deutsch); in einer Matrix aus zehn Fällen in sieben Sprachen 139 von 140 richtig (vorher 101).
- Kein doppelter Gruß: Hat das Modell sich schon verabschiedet und legt in derselben Antwort auf, fordert die Integration keine zweite
  Antwort an.
- Werkzeuge: `bewohner_rufen` nicht für Sendungen, die in die Paketbox kommen; die Meldung einer abgegebenen Sendung geht auch mit
  Abschied als Nachricht weiter.
- Anweisung (`beispiele/anweisung.jinja`): auch Sendungen für den Bewohner kommen in die Paketbox, ohne ihn zu rufen; die Sendungen stehen
  vor seinen Anliegen; siezen; Regeln nicht aussprechen.

Version 2.3.0:

- Nach dem ersten echten Klingeln: Ein neuer Ruf löst einen alten ab, der hier noch offen war (vorher „besetzt“); Wächter mit einer
  Frist je Zustand; Tagebuch der Rufe, Diagnose, Hinweise unter Reparaturen; nach einer Nachricht Auflegen nach 8 s Stille; Hinweis
  „Deutsch“ an die Erkennung; die Anweisung nennt, welcher Briefkasten wem gehört.
- Warnung unter Reparaturen, dass Mitschriften gespeichert werden, und der Schalter `mitschrift_speichern`.
- Qualitätsskala als Prüfliste (`custom_components/tuer_assistent/quality_scale.yaml`; eigene Integrationen bekommen keine Stufe):
  39 von 54 Regeln erfüllt, darunter 16 von 21 der Gold-Stufe. Offen ist, was an einer Einrichtung über die Oberfläche hängt (statt
  `configuration.yaml`); der Rest gilt hier nicht (Erkennung im Netz, wechselnde Geräte).
- Eigenes Symbol in `brand/` (Home Assistant ab 2026.3).
- Anweisung: Der Bewohner ist auch über Vornamen und „Familie <Nachname>“ zu finden (Helfer fürs Erdgeschoss mit Vor- und Nachnamen); ob etwas dringend ist, entscheidet das Modell; ausrichten geht immer; „Nachbarn“ sind die anderen Klingeln im Haus.

Geprüft mit gestellter Station und gestelltem xAI, mit dem echten Grok Voice über Proben mit aufgenommenen Sätzen und mit simulierten
Gesprächen. Die Tests liegen im Projektordner der Anlage, weil sie deren Prüfstand brauchen.
