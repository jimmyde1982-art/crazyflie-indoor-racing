# Crazyflie Indoor Racing

[![Tests](https://github.com/jimmyde1982-art/crazyflie-indoor-racing/actions/workflows/tests.yml/badge.svg)](https://github.com/jimmyde1982-art/crazyflie-indoor-racing/actions/workflows/tests.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-green)](LICENSE)
![Crazyflie 2.1](https://img.shields.io/badge/Crazyflie-2.1-orange)

Python-Skripte, mit denen man eine **Bitcraze Crazyflie 2.1** per **Xbox-Controller** in der Wohnung fliegt: schnell und wendig, aber mit eingebautem Schutz vor Wänden, Decke und Möbeln.

Das Projekt ist ein Hobby. Die Skripte sind echt geflogen, aber sie sind kein fertiges Produkt. Verbesserungen und Ideen sind willkommen (siehe unten).

**Inhalt:** [Hardware](#hardware) · [Installation](#installation) · [Die Skripte](#die-skripte) · [Starten](#starten) · [Schutzfunktionen](#schutzfunktionen-race_indoorpy-und-30_fliegenpy) · [Tests](#tests) · [Mitmachen](#mitmachen) · [Sicherheit](#sicherheit) · [Lizenz](#lizenz)

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
| `flow_ranger_recorder.py` | Fliegen, den Flug aufzeichnen und danach nachfliegen. Die Schutzfunktionen der anderen Skripte kommen ursprünglich von hier. |
| `flow_ranger_heimflug.py` | Hinfliegen, landen und danach allein zurück zum Startpunkt fliegen. Gespeicherte Strecken lassen sich wieder abfliegen. |
| `flug_auswerten.py` | Rechnet aufgezeichnete Heimflüge durch und erklärt in Klartext, wie der Flug lief und woran es lag, wenn sie das Ziel verfehlt hat. Es fliegt selbst nicht und läuft auch ohne Drohne. |
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

Die Tests brauchen keine Drohne, sie rechnen nur die Logik nach (Bremsen, Heimweg, Strecken, Auswertung …).

```bash
pip install -r requirements-dev.txt
pytest
```

Bei jedem Push und Pull Request laufen sie automatisch auf GitHub unter Linux und Windows (siehe Badge oben).

## Mitmachen

1. Oben rechts auf **Fork** klicken. Damit hast du deine eigene Kopie.
2. Deine Änderung machen und testen, am besten echt geflogen.
3. Einen **Pull Request** stellen und kurz beschreiben, was du geändert hast und warum.

Fehler oder Ideen kannst du auch einfach als **[Issue](../../issues/new/choose)** melden. Mehr Details stehen in der [CONTRIBUTING.md](CONTRIBUTING.md), was sich geändert hat in der [CHANGELOG.md](CHANGELOG.md).

## Sicherheit

Fliegen passiert auf eigene Gefahr. Fang mit Propellerschutz und niedriger Starthöhe an und halte Abstand zu Menschen, Tieren und empfindlichen Dingen. Die Schutzfunktionen helfen zwar, ersetzen aber keinen Piloten, der aufpasst.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Du darfst den Code frei benutzen, ändern und weitergeben.
