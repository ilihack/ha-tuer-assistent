# Tür-Assistent („Empfang“) für Home Assistant

Ein Klingelknopf an einer Dahua-Türstation, hinter dem eine KI antwortet: Sie fängt Paketboten ab und schickt sie zur Paketbox. Sie sagt
Besuchern, wo sie klingeln müssen, gibt dem Bewohner Bescheid, nimmt Nachrichten an und legt nach der Verabschiedung auf. Im Haus kann sie
nichts schalten. Eingerichtet wird alles in der Oberfläche von Home Assistant: Namen, Begrüßung, Anweisung (Prompt), xAI-Schlüssel,
Türstation.

*In English:* a Home Assistant custom integration that registers as a SIP indoor station at a door station (tested with Dahua VTO) and
lets xAI Grok Voice talk to visitors, speech to speech: it sends couriers to the parcel box, tells visitors which bell to ring, notifies
the resident and takes messages. It cannot switch or open anything. Everything is configured in the UI (names, greeting, prompt, xAI key,
door station). The built-in prompt and the tool texts are German; the prompt can be replaced in the UI.

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
      └─ am Ende: tuer_assistent_grok_voice {"ergebnis": "ende", "mitschrift", "grund", "sekunden", "angenommen",
                                              "stoerung", "betrifft_bewohner"}
           → Automation: eine Meldung aufs Handy mit dem ganzen Gespräch, wenn es den Bewohner betrifft oder gestört war
```

- **Kein Ersatzweg:** Kommt xAI nicht binnen 5 s zustande, antwortet die Integration 503 und die Station beendet den Ruf. Der Grund
  steht in der Meldung am Ende.
- **Überwachung:** Den xAI-Schlüssel prüft die Integration beim Start, stündlich, sofort nach jedem an xAI gescheiterten Ruf und alle
  5 min, solange etwas nicht stimmt (`GET https://api.x.ai/v1/api-key`, kostet nichts; 402 und 429 gelten als abgelehnt, aufgebrauchtes
  Guthaben steht als eigener Grund da). `binary_sensor.empfang_stoerung` geht an, wenn eines davon zutrifft:
  - seit 3 min nicht an der Station angemeldet
  - Schlüssel abgelehnt oder gesperrt
  - xAI seit 6 h nicht erreichbar
  - Grok Voice nicht gestartet
  - der letzte Ruf wurde aus einem bleibenden Grund nicht angenommen (xAI lehnt mit 4xx oder einer Meldung ab, Begrüßung oder
    Anweisung lassen sich nicht rendern, kein passender Ton); bis ein Ruf angenommen wird
  
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
| Zustand | `tuer_assistent.stand` | Anmeldung, xAI, das Modell, das xAI zuletzt genommen hat, letztes Werkzeug, letzter Ruf mit Grund des Endes |
| Sensor „Empfang Störung“ (Diagnose) | `binary_sensor.empfang_stoerung` | an, wenn der Knopf nicht gehen würde; Attribut `grund` |
| Auswahl „Empfang KI“ (Einstellung) | `select.empfang_ki` | nur für den Weg über einen VoIP Stack: an welchen Text-Agenten der Empfang weiterreicht |
| Erkennung, Stimme, Agent | `stt.empfang`, `tts.empfang`, `conversation.empfang` | nur für den Weg über einen VoIP Stack; bei neuen Einrichtungen aus |
| Dienst | `tuer_assistent.auflegen` | beendet das laufende Gespräch |
| Ereignis | `tuer_assistent_grok_voice` | `klingel`, `angenommen`, `abgelehnt`, `ende` (mit Mitschrift, Grund, `stoerung` und `betrifft_bewohner`) |
| Ereignis | `tuer_assistent_werkzeug` | ein Werkzeug der KI wurde gerufen |
| Ereignis | `tuer_assistent_gespraech` | Beginn und Ende einer Störung (Feld `ersatz`) |
| Reparaturen | Einstellungen → Reparaturen | Schlüssel abgelehnt oder gesperrt; Anmeldung an der Station verloren; Warnung, dass Mitschriften gespeichert werden |
| Diagnose | am Eintrag der Integration | Zustand und Tagebuch der Rufe, ohne Schlüssel, Adresse, Namen, Anweisung und Mitschrift |

Alle Entitäten hängen an einem Gerät „Empfang“; Namen und Symbole kommen aus `translations/` und `icons.json` (deutsch und englisch).

## Woher die Daten kommen

- Rufe schiebt die Station selbst herein (SIP über UDP im Hausnetz); die Integration fragt dafür nichts ab.
- Die Anmeldung an der Station erneuert sie nach 80 % der gewährten Zeit.
- Den xAI-Schlüssel prüft sie beim Start, stündlich und nach jedem an xAI gescheiterten Ruf.
- Bewohner, Angaben, Begrüßung und Anweisung liest sie bei jedem Ruf frisch aus ihren Einstellungen; eine Änderung dort gilt ab dem
  nächsten Ruf. Im Code steht kein Name, und Helfer braucht sie keine.
- Ob ein Gespräch den Bewohner betrifft (er wurde gerufen, bekam eine Nachricht, oder ein Wort seines Namens fällt) und ob das Ende
  eine Störung war, entscheidet die Integration und gibt es im Ereignis „ende“ mit.
- Der Sensor „Empfang Störung“ liest alle 30 s nur den eigenen Zustand.

## Einrichten

1. Den Ordner `custom_components/tuer_assistent` nach `/config/custom_components/` kopieren oder dieses Projekt in HACS als
   benutzerdefiniertes Repository (Typ Integration) eintragen. Home Assistant neu starten.
2. An der Türstation eine Innenstation (hier 9904) mit eigenem Passwort anlegen und sie dem Knopf zuordnen.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → „Tür-Assistent“. Die Maske, von oben:

   | Abschnitt | Feld | Vorgabe | Bedeutung |
   |---|---|---|---|
   | Bewohner und Namen | Bewohner | – | Vor- und Nachname dessen, für den der Empfang arbeitet; Variable `bewohner` |
   | | Anrede | Herr | wie die Werkzeuge ihn nennen: Herr, Frau, Familie oder ohne (der ganze Name) |
   | | Angaben | vier leere Zeilen | je Zeile `name: wert`; jede wird eine Variable der Anweisung (etwa `dachgeschoss: Familie Beispiel`) |
   | Begrüßung und Anweisung | Begrüßung | „Hello, guten Tag! Hier ist der Empfang …“ | der erste Satz, wörtlich gesprochen; Vorlage; Variable `begruessung` |
   | | Anweisung | `vorgabe.py` | der Prompt; Vorlage, bei jedem Ruf neu gerendert |
   | xAI (Grok Voice) | xAI-Schlüssel | – | wird vor dem Speichern bei xAI geprüft (kostet nichts) |
   | | Modell | grok-voice-latest | der Alias folgt den Aktualisierungen von xAI; ein Name mit Version legt es fest |
   | | Stimme | eve | Name der Stimme bei xAI |
   | | Stichwörter | – | Wörter für die Erkennung; die Namen aus Bewohner und Angaben kommen von selbst dazu |
   | Türstation | Türstation | – | Name oder Adresse der Station im Hausnetz |
   | | Nebenstelle | 9904 | Nummer der Innenstation |
   | | Passwort der Nebenstelle | – | Passwort dieser Innenstation an der Station |
   | | Eigener SIP-Port | 5062 | UDP-Port, den die Station erreichen muss |
   | | SIP-Port der Türstation | 5060 | |
   | | Mitschrift speichern | an | Mitschriften im Tagebuch; aus hält sie heraus, auch aus den schon gespeicherten Rufen |

   Vor dem Speichern prüft die Maske die Zeilen der Angaben, rendert Begrüßung und Anweisung streng (eine Variable, die es nicht gibt,
   ist ein Fehler) und fragt xAI nach dem Schlüssel. Schlüssel und Passwort zeigt sie nie wieder an; leer gelassen bleiben sie.
4. Die Automationen aus `beispiele/` einspielen:
   - `klingel_unten.json`: am Ende eines Rufs eine Meldung mit der Mitschrift, wenn das Gespräch den Bewohner betrifft oder der
     Empfang gestört war (beides steht im Ereignis)
   - `tuer_assistent_werkzeuge.json`: Handy, Nachricht, Auflegen
   - `tuer_assistent_mitschrift.json`: Beginn und Ende von Störungen aufs Handy (beim Text-Agenten auf Wunsch jeder Wortwechsel)
   
   Sie nutzen das Skript `script.meldung` der eigenen Anlage (Push aufs Handy) und die zwei Helfer aus `beispiele/helfer.json`.
5. `tuer_assistent.stand` zeigt im Attribut `grok_voice` den Wert „angemeldet als 9904“ und im Attribut `xai` den Wert „ok“;
   `binary_sensor.empfang_stoerung` steht auf aus. Dasselbe steht oben in der Maske („Stand“).

Ändern: am Eintrag „Konfigurieren“. Die Maske zeigt dann nur den Abschnitt mit den Namen offen. Namen, Angaben, Begrüßung und
Anweisung gelten ab dem nächsten Ruf, ohne dass etwas neu startet. Ändert sich etwas an xAI, der Türstation oder „Mitschrift
speichern“, startet Grok Voice neu (ein laufender Ruf endet), Home Assistant nicht.

### Begrüßung und Anweisung

Beides sind Vorlagen (Jinja) wie überall in Home Assistant. Die mitgelieferte Anweisung (`custom_components/tuer_assistent/vorgabe.py`)
ist ein Beispiel für ein Haus mit drei Parteien und Briefkästen, die zugleich Paketboxen sind; sie nutzt die Angaben `dachgeschoss`,
`untergeschoss`, `adresse` und `paketbox` und liest `sensor.anwesend` (Zustand `niemand` heißt: keiner zu Hause). Für ein anderes Haus
den Text in der Maske anpassen oder ersetzen.

- Variablen: `bewohner`, `anrede`, `begruessung` (nur in der Anweisung) und je Zeile der Angaben eine. Die Werte der Angaben sind Text
  und werden nie ausgeführt.
- Gespeichert wird nur eigener Text. Bleibt ein Feld bei der Vorgabe oder leer, gilt die Vorgabe der Integration, auch die einer
  späteren Version.
- Welches Modell xAI wirklich nimmt, steht in `tuer_assistent.stand` (Attribut `modell`) und je Ruf im Tagebuch. Ein Wechsel steht
  einmal als Warnung im Log. Für einen Namen, den es nicht gibt, nimmt xAI still sein Standardmodell.

### Von 2.5.0 kommend

Der Block `grok_voice:` in `configuration.yaml` wird beim ersten Start einmal in die Einstellungen übernommen und danach ignoriert
(ein Hinweis unter Reparaturen sagt, dass er weg kann). Die Anweisung kommt nicht mehr vom Gesprächsagenten, sondern aus den
Einstellungen; die Helfer für Namen, Adresse und Paketbox braucht es nicht mehr: Ihre Werte gehören in „Bewohner“ und „Angaben“.

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
| nicht angenommen: … | keine Verbindung zu xAI in 5 s, Schlüssel abgelehnt, Begrüßung oder Anweisung nicht lesbar, oder kein G.711 im Angebot |
| 20 s Stille / 8 s Stille nach der Nachricht | niemand spricht mehr |

4. Bleibt der Knopf stumm und im Log steht nichts von „Grok Voice“: Schlüssel, Türstation oder Passwort fehlen in den Einstellungen
   (`grok_voice`: „aus (nicht eingerichtet)“), oder der Port ist belegt (Warnung beim Start).

## Bekannte Grenzen

- Kein Ersatzweg: Ohne Internet oder ohne xAI bleibt der Knopf stumm (die Meldung am Ende und der Sensor sagen es).
- Ein Gespräch zur Zeit, höchstens 3 min; die Dahua-Station beendet von sich aus nach 2 min.
- Die KI kann sich verhören, besonders bei Namen; die Anweisung lässt sie nachfragen. Was sie sagt, regelt die Anweisung, nicht der Code.
- Die Texte der drei Werkzeuge stehen im Code und sind deutsch (mit „Paketbox“); die Anrede des Bewohners darin kommt aus den
  Einstellungen.
- Die mitgelieferte Anweisung ist deutsch, auf ein Haus mit drei Wohnungen zugeschnitten und nennt den Bewohner „Herr“ mit Nachnamen;
  für ein anderes Haus oder eine andere Anrede den Text in der Maske anpassen.
- Nur xAI Grok Voice als KI; erprobt nur an einer Dahua-Türstation.
- Die Anmeldung an der Türstation prüft die Maske nicht vor dem Speichern; ob sie gilt, zeigt der Stand gleich danach.

## Entfernen

1. Die Automationen aus `beispiele/` löschen.
2. Den Eintrag „Tür-Assistent“ unter Geräte & Dienste löschen (Grok Voice meldet sich an der Station ab).
3. Den Ordner `custom_components/tuer_assistent` und die Datei `.storage/tuer_assistent.rufe` entfernen, neu starten; eine Zeile
   `tuer_assistent:` in `configuration.yaml` vorher entfernen.
4. An der Türstation die Innenstation 9904 löschen oder dem Knopf wieder eine andere Nummer geben.

## Kosten und Schutz

- xAI rechnet laut eigener Preisliste 5 Cent je Minute Gespräch ab. Ein Klingeln kostet damit höchstens rund 15 Cent. Im xAI-Konto ein
  Ausgabenlimit setzen.
- Schlüssel, Adresse der Station und Passwort stehen in den Einstellungen des Eintrags (`.storage/core.config_entries`, wie bei jeder
  Integration unverschlüsselt und in jeder Sicherung). Die Maske zeigt Schlüssel und Passwort nie an; Log und Diagnose enthalten sie
  nicht, auch keine Namen und keinen Text der Anweisung.
- Mitschriften: Das Tagebuch hält die letzten 30 Gespräche mit Text fest, unverschlüsselt in `.storage` und damit in jeder Sicherung.
  Dieselben Texte stehen in den Ereignissen der Integration, die der Recorder aufhebt (standardmäßig 10 Tage). Die Integration sagt
  das unter Reparaturen. Abschalten: „Mitschrift speichern“ in den Einstellungen; aus dem Recorder heraus mit
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

Version 2.6.0 (14.11.2026):

- Alle Einstellungen in der Oberfläche: Bewohner mit Anrede, Angaben (je Zeile eine Variable), Begrüßung, Anweisung, xAI, Türstation.
  Keine Helfer mehr, kein Block in `configuration.yaml`, kein Gesprächsagent als Quelle der Anweisung. Namen und Texte gelten ab dem
  nächsten Ruf; nur eine geänderte Verbindung startet Grok Voice neu.
- Die Anweisung liegt als Vorgabe bei (`vorgabe.py`) und steht vorbelegt in der Maske.
- Modell aus den Einstellungen, Vorgabe „grok-voice-latest“; das wirklich genutzte Modell wird festgehalten, ein Wechsel im Log gemeldet.
- Vor dem Speichern: Zeilen der Angaben, strenges Rendern von Begrüßung und Anweisung, Abfrage des Schlüssels bei xAI.
- Das Ereignis „ende“ trägt `stoerung` und `betrifft_bewohner`; die Automation der Klingel braucht keinen Helfer und keine eigene Regel mehr.
- 80 Tests der Integration selbst (gestellte Station, gestelltes xAI), Abdeckung 96 %; die Maske zusätzlich im echten Frontend von
  Home Assistant bedient (einrichten, Fehler, ändern, zurück zur Vorgabe).

Version 2.5.0 (14.11.2026):

- Namen aus dem Helfer statt aus dem Code (siehe oben).
- Modell fest `grok-voice-3.0` statt des Alias „latest“. Achtung: xAI nimmt auch Namen an, die es nicht gibt, und nimmt dann still das
  Standardmodell; was gilt, steht in `session.created`.
- Begrüßung 0,5 s nach der Annahme, damit die Station ihre Ansage zu Ende spricht.
- Robuster: Ein Fehler beim Start legt nur Grok Voice still; der Name der Station wird bei jeder Anmeldung neu aufgelöst (nach einem
  Stromausfall ist der Router oft später da); hängt xAI beim Aufbau, kommt die 503 nach 5 s; eine stockende Antwort endet nach 10 s
  statt nach der Höchstdauer; ein „auflegen“ für den vorigen Ruf trifft keinen neuen; Anhalten während des Aufbaus gibt 503.
- Sichtbarer: gescheiterte Rufe lösen sofort die Prüfung des Schlüssels aus, ein bleibender Grund zeigt sich am Sensor; gleiche Fehler
  von xAI nur einmal je Ruf im Log; Fehler der Anweisung ohne Textzeile.
- 196 Tests, Abdeckung 93 %.

Version 2.4.1 (12.11.2026):

- Was an den Bewohner geht (Anliegen, Nachricht), schreibt dasselbe Modell auf Deutsch, auch wenn der Besucher eine andere Sprache
  spricht; mit dem Besucher spricht es weiter in dessen Sprache. Ohne zweites Modell; die Mitschrift am Ende bleibt im Original.
- Qualitätsskala: Testabdeckung gemessen, 91 % (Silber verlangt über 95 % in jedem Modul), darum jetzt „todo“.

Version 2.4.0:

- Jede Sprache wie Deutsch: Das Ergebnis jedes Werkzeugs sagt dem Modell, in der Sprache des Besuchers zu antworten (vorher sprach es
  nach einem Werkzeug oft Deutsch); in einer Matrix aus zehn Fällen in sieben Sprachen 139 von 140 richtig (vorher 101).
- Kein doppelter Gruß: Hat das Modell sich schon verabschiedet und legt in derselben Antwort auf, fordert die Integration keine zweite
  Antwort an.
- Werkzeuge: `bewohner_rufen` nicht für Sendungen, die in die Paketbox kommen; die Meldung einer abgegebenen Sendung geht auch mit
  Abschied als Nachricht weiter.
- Anweisung: auch Sendungen für den Bewohner kommen in die Paketbox, ohne ihn zu rufen; die Sendungen stehen
  vor seinen Anliegen; in anderen Sprachen die dortige Anrede (Mr., Bey, Pan); siezen; Regeln nicht aussprechen.

Version 2.3.0:

- Nach dem ersten echten Klingeln: Ein neuer Ruf löst einen alten ab, der hier noch offen war (vorher „besetzt“); Wächter mit einer
  Frist je Zustand; Tagebuch der Rufe, Diagnose, Hinweise unter Reparaturen; nach einer Nachricht Auflegen nach 8 s Stille; Hinweis
  „Deutsch“ an die Erkennung; die Anweisung nennt, welcher Briefkasten wem gehört.
- Warnung unter Reparaturen, dass Mitschriften gespeichert werden, und der Schalter `mitschrift_speichern`.
- Qualitätsskala als Prüfliste (`custom_components/tuer_assistent/quality_scale.yaml`; eigene Integrationen bekommen keine Stufe):
  38 von 54 Regeln erfüllt (Stand 2.4.1), darunter 16 von 21 der Gold-Stufe. Offen sind die Testabdeckung und, was an einer
  Einrichtung über die Oberfläche hängt (statt `configuration.yaml`); der Rest gilt hier nicht (Erkennung im Netz, wechselnde Geräte).
  Eine Stufe vergibt Home Assistant nur Integrationen im Kern; streng gelesen läge diese unter Bronze, weil Bronze die Einrichtung über
  die Oberfläche verlangt.
- Eigenes Symbol in `brand/` (Home Assistant ab 2026.3).
- Anweisung: Der Bewohner ist auch über Vornamen und „Familie <Nachname>“ zu finden (Helfer fürs Erdgeschoss mit Vor- und Nachnamen); ob etwas dringend ist, entscheidet das Modell; ausrichten geht immer; „Nachbarn“ sind die anderen Klingeln im Haus.

Geprüft mit gestellter Station und gestelltem xAI, mit dem echten Grok Voice über Proben mit aufgenommenen Sätzen und mit simulierten
Gesprächen. Die Tests liegen im Projektordner der Anlage, weil sie deren Prüfstand brauchen.

## Lizenz

MIT, siehe `LICENSE`.
