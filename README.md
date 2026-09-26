# Crazyflie Indoor Racing

Python-Skripte, mit denen man eine **Bitcraze Crazyflie 2.1** per **Xbox-Controller** in der Wohnung fliegt: schnell und wendig, aber mit eingebautem Schutz vor Wänden, Decke und Möbeln.

Das Projekt ist ein Hobby. Die Skripte sind echt geflogen, aber sie sind kein fertiges Produkt. Verbesserungen und Ideen sind willkommen (siehe unten).

## Hardware

- Crazyflie 2.1 mit **Flow Deck v2** (Höhe und Position) und **Multi-Ranger Deck** (Abstände in alle Richtungen)
- Crazyradio (USB-Funkstick)
- Xbox-Controller, per USB oder Bluetooth

## Installation

Du brauchst Python 3.12.

```bash
pip install -r requirements.txt
```

Schließ vor dem Start den cfclient, sonst ist der Funkstick belegt.

## Die Skripte

| Datei | Was es macht |
|---|---|
| `race_indoor.py` | Das Hauptskript für schnelles Fliegen. Taste **Y** macht eine Wende um 180°. Vor Wänden bremst sie selbst (Bremslicht über die LEDs). Jeder Flug wird als `.txt` und `.csv` mitgeschrieben. |
| `30_fliegen.py` | Ein Allround-Flugskript mit zwei Flugmodi: **SCHWEBEN** (der Stick gibt das Tempo vor) und **SPORTLICH** (der Stick gibt die Neigung vor). Es hat vier Stick-Einstellungen, Flugfiguren auf dem Steuerkreuz (Kreis, Acht, Spirale, Auf-und-Ab), Trimmung und eine optionale Aufzeichnung. |
| `strecken.py` | Verwaltet aufgezeichnete Flugstrecken und vergibt Namen dafür (zum Beispiel „kueche“). Es fliegt selbst nicht, sondern liest und schreibt nur Dateien. |
| `xbox_fly3.py` | Ein einfaches Grundgerüst mit direktem Schub und **ohne Höhenhaltung**. Es ist nur für Leute gedacht, die wissen, was sie tun. |

### Starten

```bash
python race_indoor.py
python 30_fliegen.py              # normal
python 30_fliegen.py 3 h40 d10    # Einstellung 3, Start auf 40 cm, 10 cm Abstand zur Decke
python 30_fliegen.py sport rec    # im sportlichen Modus starten und den Flug aufzeichnen
```

Alle Tasten und Optionen stehen ausführlich am Anfang der jeweiligen Datei.

### Funkadresse

In `race_indoor.py` und `30_fliegen.py` ist die Standardadresse `radio://0/80/2M/E7E7E7E7E7`. Wenn deine Drohne eine andere hat, gibst du sie so an:

```bash
# Windows (PowerShell)
$env:CFLIB_URI = "radio://0/80/2M/E7E7E7E7E7"
# Linux / macOS
export CFLIB_URI=radio://0/80/2M/E7E7E7E7E7
```

## Schutzfunktionen (race_indoor.py und 30_fliegen.py)

- **Wände und Möbel:** Die Drohne bremst ab einem Mindestabstand und bleibt dann stehen. Wegfliegen geht immer.
- **Decke:** Der Sensor oben hält einen Mindestabstand ein.
- **Möbelkanten:** Springt der Bodensensor plötzlich, zum Beispiel über einem Tisch, wird das herausgerechnet, damit sie nicht hochschießt.
- **Akku:** Bei niedriger Spannung unter Last kommt eine Warnung, danach landet sie automatisch.
- **Funkabriss, Controller weg, Strg+C:** Sie landet, beziehungsweise es greift der Not-Aus.

Alle Grenzwerte stehen oben in den Dateien unter KONFIGURATION und sind kommentiert, oft mit den Messwerten, aus denen sie entstanden sind.

## Tests

```bash
pip install pytest
pytest
```

## Mitmachen

1. Oben rechts auf **Fork** klicken. Damit hast du deine eigene Kopie.
2. Deine Änderung machen und testen, am besten echt geflogen.
3. Einen **Pull Request** stellen und kurz beschreiben, was du geändert hast und warum.

Fehler oder Ideen kannst du auch einfach als **Issue** melden.

## Sicherheit

Fliegen passiert auf eigene Gefahr. Fang mit Propellerschutz und niedriger Starthöhe an und halte Abstand zu Menschen, Tieren und empfindlichen Dingen. Die Schutzfunktionen helfen zwar, ersetzen aber keinen Piloten, der aufpasst.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Du darfst den Code frei benutzen, ändern und weitergeben.
