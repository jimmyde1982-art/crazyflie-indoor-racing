#!/usr/bin/env python3
"""
strecken.py  --  Aufgezeichnete Flugstrecken benennen und verwalten
===================================================================
Version 1.0 vom 20.09.2026.

Eine Strecke ist ein aufgezeichneter Hinflug, den du behalten willst.
Statt heim_hin_2026-09-20_154141.csv heißt sie dann "kueche" und lässt
sich jederzeit wieder abfliegen.

Je Strecke liegen zwei Dateien im Ordner strecken/:

    kueche.csv    Kopie der Aufnahme, Zeile für Zeile wie im Original
    kueche.json   Name, Datum, Herkunft und die Kennzahlen des Fluges

Warum eine Kopie und kein Verweis: Räumst du im Hauptordner auf, bleibt
die Strecke trotzdem heil. Eine Aufnahme ist rund 200 KB groß, das
fällt nicht ins Gewicht.

Dieses Modul fliegt nicht. Es liest und schreibt nur Dateien, damit ein
Fehler hier die Drohne nicht betreffen kann. Das Flugskript hängt sich
in Schritt 3 und 4 daran.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime

TAKT = 0.05                 # s je Zeile der Aufnahme, wie im Flugskript
STILL_TEMPO = 0.08          # m/s, darunter gilt sie als schwebend
ORDNER = 'strecken'         # Unterordner, in dem die Strecken liegen
# Abheben und Landen laufen zwangsläufig durch niedrige Höhen. Für die
# Frage "war sie im Flug zu tief" zählen die ersten und letzten 2
# Sekunden deshalb nicht mit. Ohne das meldete jeder Flug 0,15 m, auch
# der saubere vom 20.09. 15:15 -- eine Warnung, die immer kommt, ist
# keine.
RAND_TAKTE = int(2.0 / TAKT)

# Erlaubt sind Buchstaben, Ziffern, Bindestrich und Unterstrich. Umlaute
# werden ersetzt, damit der Dateiname auf jedem System funktioniert.
_ERSATZ = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
           'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue'}


class StreckenFehler(Exception):
    """Etwas stimmt mit der Strecke oder dem Namen nicht."""


@dataclass
class Kennzahlen:
    """Was eine Aufnahme über den Flug verrät. Genau die Werte, die bei
    jeder Auswertung bisher von Hand ausgerechnet wurden."""
    takte: int              # Zeilen der Aufnahme
    dauer_s: float          # wie lange der Hinflug gedauert hat
    weg_m: float            # tatsächlich geflogene Strecke
    luftlinie_m: float      # Abstand Start zu Ende, Luftlinie
    umweg: float            # weg_m geteilt durch luftlinie_m
    gedreht_grad: float     # wie viel sie insgesamt gedreht hat
    schweben_anteil: float  # Anteil der Takte unter STILL_TEMPO (0 bis 1)
    tempo_max: float        # schnellster Takt
    hoehe_min: float        # tiefste Höhe im Flug, ohne Start und Landung
    hoehe_max: float
    hoehe_mittel: float
    squal_min: int          # schlechteste Bildqualität (unter 30 kritisch)
    shutter_min: int        # kürzeste Belichtung (41 = voll zugeblendet)

    def warnungen(self) -> list[str]:
        """Was an dieser Strecke beim Abfliegen Ärger machen kann. Die
        Grenzen stammen aus den Flügen vom 20.09.2026."""
        w: list[str] = []
        if self.gedreht_grad > 400:
            w.append('viel gedreht (%.0f Grad) -- der Rückflug landet '
                     'dadurch weiter daneben' % self.gedreht_grad)
        if self.umweg > 3.0:
            w.append('%.1ffacher Umweg -- der Rückflug dauert entsprechend '
                     'lange' % self.umweg)
        if self.schweben_anteil > 0.35:
            w.append('%.0f Prozent Schweben -- so viel Zeit steht sie im '
                     'Rückflug nur herum' % (100 * self.schweben_anteil))
        if self.squal_min < 30:
            w.append('Bodenkamera war bei squal %d fast blind'
                     % self.squal_min)
        if 0 < self.shutter_min <= 50:
            w.append('Bodenkamera stand bei shutter %d am Anschlag -- es '
                     'war zu hell' % self.shutter_min)
        if 0 < self.hoehe_min < 0.20:
            w.append('ging bis auf %.2f m herunter' % self.hoehe_min)
        return w


@dataclass
class Strecke:
    """Eine benannte Strecke: der Name, woher sie kommt, ihre
    Kennzahlen und wo die Aufnahme liegt."""
    name: str
    gespeichert: str        # Zeitstempel, wann sie benannt wurde
    geflogen: str           # Zeitstempel der Aufnahme, 2026-09-20_154141
    herkunft: str           # Dateiname, aus dem sie kopiert wurde
    kennzahlen: Kennzahlen
    bemerkung: str = ''
    csv_datei: str = ''     # ergibt sich beim Lesen, steht nicht im json


def _zahl(zeile: dict[str, str], feld: str) -> float | None:
    """Ein Feld als Zahl, oder None wenn es fehlt oder leer ist."""
    try:
        wert = zeile.get(feld, '')
        return float(wert) if wert not in ('', None) else None
    except (TypeError, ValueError):
        return None


def name_pruefen(name: str) -> str:
    """Macht aus dem, was getippt wurde, einen brauchbaren Dateinamen.
    Wirft StreckenFehler, wenn nichts Verwendbares übrig bleibt."""
    sauber = name.strip().lower()
    for zeichen, ersatz in _ERSATZ.items():
        sauber = sauber.replace(zeichen, ersatz)
    sauber = re.sub(r'[^a-z0-9_-]+', '_', sauber).strip('_-')
    if not sauber:
        raise StreckenFehler(
            'Aus "%s" lässt sich kein Name machen. Erlaubt sind '
            'Buchstaben, Ziffern, Bindestrich und Unterstrich.' % name)
    if len(sauber) > 40:
        raise StreckenFehler('Der Name ist zu lang (höchstens 40 Zeichen).')
    return sauber


def kennzahlen_rechnen(pfad: str, phase: str = 'hin') -> Kennzahlen:
    """Liest eine Aufnahme und rechnet aus, was der Flug war. Nimmt nur
    die Zeilen der angegebenen Phase (im Hinflug also 'hin')."""
    weg = 0.0
    x_vor: float | None = None
    y_vor: float | None = None
    x_erst: float | None = None
    y_erst: float | None = None
    x_letzt: float | None = None
    y_letzt: float | None = None
    gedreht = 0.0
    tempi: list[float] = []
    hoehen: list[float] = []
    squals: list[int] = []
    shutter: list[int] = []
    takte = 0

    with open(pfad, newline='', encoding='utf-8') as fh:
        for zeile_csv in csv.DictReader(fh, delimiter=';'):
            if phase and zeile_csv.get('phase') != phase:
                continue
            takte += 1
            vx, vy = _zahl(zeile_csv, 'vx_ms'), _zahl(zeile_csv, 'vy_ms')
            if vx is not None and vy is not None:
                tempi.append(math.hypot(vx, vy))
            gier = _zahl(zeile_csv, 'gier_grad_s')
            if gier is not None:
                gedreht += abs(gier) * TAKT
            z = _zahl(zeile_csv, 'z_ist_m')
            if z is not None:
                hoehen.append(z)
            sq = _zahl(zeile_csv, 'squal')
            if sq is not None:
                squals.append(int(sq))
            sh = _zahl(zeile_csv, 'shutter')
            if sh is not None:
                shutter.append(int(sh))
            x, y = _zahl(zeile_csv, 'x_m'), _zahl(zeile_csv, 'y_m')
            if x is None or y is None:
                continue
            if x_erst is None:
                x_erst, y_erst = x, y
            if x_vor is not None and y_vor is not None:
                weg += math.hypot(x - x_vor, y - y_vor)
            x_vor, y_vor = x, y
            x_letzt, y_letzt = x, y

    if takte == 0:
        raise StreckenFehler(
            'In %s steht keine Zeile der Phase "%s".'
            % (os.path.basename(pfad), phase))

    if (x_erst is None or y_erst is None
            or x_letzt is None or y_letzt is None):
        luft = 0.0
    else:
        luft = math.hypot(x_letzt - x_erst, y_letzt - y_erst)
    still = sum(1 for v in tempi if v < STILL_TEMPO)
    # Start und Landung aus der Höhenprüfung nehmen (siehe RAND_TAKTE).
    # Ist die Aufnahme dafür zu kurz, bleibt alles drin.
    mitte = (hoehen[RAND_TAKTE:-RAND_TAKTE]
             if len(hoehen) > 2 * RAND_TAKTE + 10 else hoehen)

    return Kennzahlen(
        takte           = takte,
        dauer_s         = takte * TAKT,
        weg_m           = weg,
        luftlinie_m     = luft,
        umweg           = weg / luft if luft > 0.05 else 0.0,
        gedreht_grad    = gedreht,
        schweben_anteil = still / len(tempi) if tempi else 0.0,
        tempo_max       = max(tempi) if tempi else 0.0,
        hoehe_min       = min(mitte) if mitte else 0.0,
        hoehe_max       = max(hoehen) if hoehen else 0.0,
        hoehe_mittel    = sum(hoehen) / len(hoehen) if hoehen else 0.0,
        squal_min       = min(squals) if squals else 0,
        shutter_min     = min(shutter) if shutter else 0,
    )


def _zeitstempel_aus(dateiname: str) -> str:
    """Holt 2026-09-20_154141 aus heim_hin_2026-09-20_154141.csv."""
    treffer = re.search(r'(\d{4}-\d{2}-\d{2}_\d{6})', dateiname)
    return treffer.group(1) if treffer else ''


def ordner_pfad(basis: str) -> str:
    """Der Streckenordner unterhalb von basis. Legt ihn an, wenn er noch
    nicht da ist."""
    ziel = os.path.join(basis, ORDNER)
    os.makedirs(ziel, exist_ok=True)
    return ziel


def speichern(quelle: str, name: str, basis: str, bemerkung: str = '',
              phase: str = 'hin', ueberschreiben: bool = False) -> Strecke:
    """Macht aus einer Aufnahme eine benannte Strecke.

    quelle: die CSV des Hinflugs. name: wie du sie nennen willst.
    basis:  der Ordner, in dem strecken/ liegen soll.

    Eine vorhandene Strecke wird nur überschrieben, wenn du es
    ausdrücklich erlaubst -- sonst gibt es einen Fehler."""
    if not os.path.isfile(quelle):
        raise StreckenFehler('Die Aufnahme %s gibt es nicht.' % quelle)
    sauber = name_pruefen(name)
    ziel = ordner_pfad(basis)
    csv_ziel = os.path.join(ziel, sauber + '.csv')
    json_ziel = os.path.join(ziel, sauber + '.json')
    if os.path.exists(json_ziel) and not ueberschreiben:
        raise StreckenFehler(
            'Es gibt schon eine Strecke "%s". Nimm einen anderen Namen '
            'oder sag ausdrücklich, dass sie ersetzt werden soll.' % sauber)

    kz = kennzahlen_rechnen(quelle, phase)     # erst rechnen, dann kopieren
    shutil.copy2(quelle, csv_ziel)
    s = Strecke(
        name        = sauber,
        gespeichert = datetime.now().strftime('%Y-%m-%d_%H%M%S'),
        geflogen    = _zeitstempel_aus(os.path.basename(quelle)),
        herkunft    = os.path.basename(quelle),
        kennzahlen  = kz,
        bemerkung   = bemerkung.strip(),
        csv_datei   = csv_ziel,
    )
    _kopf_schreiben(s, json_ziel)
    return s


def _kopf_schreiben(s: Strecke, json_datei: str) -> None:
    """Schreibt die json neben die Aufnahme. csv_datei kommt nicht mit
    hinein, der Pfad ergibt sich aus dem Namen."""
    kopf = asdict(s)
    kopf.pop('csv_datei')
    with open(json_datei, 'w', encoding='utf-8') as fh:
        json.dump(kopf, fh, ensure_ascii=False, indent=2)


def lesen(name: str, basis: str) -> Strecke:
    """Holt eine gespeicherte Strecke zurück."""
    sauber = name_pruefen(name)
    ziel = ordner_pfad(basis)
    json_datei = os.path.join(ziel, sauber + '.json')
    csv_datei = os.path.join(ziel, sauber + '.csv')
    if not os.path.isfile(json_datei):
        raise StreckenFehler('Eine Strecke "%s" gibt es nicht.' % sauber)
    if not os.path.isfile(csv_datei):
        raise StreckenFehler(
            'Zu "%s" fehlt die Aufnahme (%s.csv). Abfliegen geht nicht.'
            % (sauber, sauber))
    with open(json_datei, encoding='utf-8') as fh:
        kopf = json.load(fh)
    kopf['kennzahlen'] = Kennzahlen(**kopf['kennzahlen'])
    kopf.pop('csv_datei', None)
    return Strecke(csv_datei=csv_datei, **kopf)


def alle(basis: str) -> list[Strecke]:
    """Alle gespeicherten Strecken, die neueste zuerst. Kaputte Einträge
    werden übersprungen, statt die ganze Liste scheitern zu lassen."""
    ziel = ordner_pfad(basis)
    aus: list[Strecke] = []
    for datei in sorted(os.listdir(ziel)):
        if not datei.endswith('.json'):
            continue
        try:
            aus.append(lesen(datei[:-5], basis))
        except (StreckenFehler, json.JSONDecodeError, KeyError, TypeError,
                ValueError, OSError):
            continue
    aus.sort(key=lambda s: s.gespeichert, reverse=True)
    return aus


def umbenennen(alt: str, neu: str, basis: str) -> Strecke:
    """Gibt einer Strecke einen anderen Namen."""
    s = lesen(alt, basis)
    sauber = name_pruefen(neu)
    ziel = ordner_pfad(basis)
    if sauber == s.name:
        return s
    if os.path.exists(os.path.join(ziel, sauber + '.json')):
        raise StreckenFehler('Es gibt schon eine Strecke "%s".' % sauber)
    os.replace(s.csv_datei, os.path.join(ziel, sauber + '.csv'))
    os.replace(os.path.join(ziel, s.name + '.json'),
               os.path.join(ziel, sauber + '.json'))
    s.name = sauber
    s.csv_datei = os.path.join(ziel, sauber + '.csv')
    _kopf_schreiben(s, os.path.join(ziel, sauber + '.json'))
    return s


def aussortieren(name: str, basis: str) -> str:
    """Schiebt eine Strecke in den Unterordner ausrangiert/. Gelöscht
    wird hier nichts -- was einmal geflogen ist, bleibt erhalten."""
    s = lesen(name, basis)
    ziel = ordner_pfad(basis)
    lager = os.path.join(ziel, 'ausrangiert')
    os.makedirs(lager, exist_ok=True)
    stempel = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    for endung in ('.csv', '.json'):
        quelle = os.path.join(ziel, s.name + endung)
        if os.path.exists(quelle):
            os.replace(quelle, os.path.join(
                lager, '%s_%s%s' % (s.name, stempel, endung)))
    return lager


def zeile(s: Strecke) -> str:
    """Eine Strecke in einer Zeile, für die Liste im Menü."""
    k = s.kennzahlen
    return ('%-16s %5.0f s  %5.2f m Weg  %4.2f m Luftlinie  '
            '%4.0f Grad gedreht  %2.0f %% Schweben'
            % (s.name, k.dauer_s, k.weg_m, k.luftlinie_m,
               k.gedreht_grad, 100 * k.schweben_anteil))
