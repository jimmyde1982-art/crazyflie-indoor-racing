#!/usr/bin/env python3
"""
flug_auswerten.py  --  Aufgezeichnete Heimflüge durchrechnen
=============================================================
Version 1.0 vom 20.09.2026.

Nach jedem Heimflug liegen im Ordner mehrere CSV-Dateien. Dieses Skript
liest sie und sagt in Klartext, wie der Flug gelaufen ist und woran es
lag, wenn die Drohne das Ziel verfehlt hat.

Es fliegt nichts und es funkt nichts. Das Skript liest nur Dateien. Du
kannst es jederzeit starten, auch ohne Drohne am Rechner:

    python flug_auswerten.py                 alle Flüge im eigenen Ordner
    python flug_auswerten.py <ordner>        Flüge in einem anderen Ordner
    python flug_auswerten.py <ordner> kurz   nur eine Zeile je Flug

Woher die Zahlen kommen
-----------------------
Das Flow Deck kennt keine absolute Position. Es schaut nach unten und
rechnet aus, wie weit sich der Boden bewegt hat. Diese Schritte werden
addiert -- und jeder Fehler bleibt für immer drin. Das nennt sich
Koppelnavigation.

Zwei Dinge machen diesen Fehler groß:

1. Drehen. Dreht sich die Drohne, wandert das Bild unter ihr genauso,
   als wäre sie zur Seite geflogen. Die Kamera kann beides nicht
   auseinanderhalten. Bitcraze nennt im eigenen Forum rund 10 cm Drift
   je 90-Grad-Drehung.

2. Höhe. Je höher sie fliegt, desto mehr Zentimeter Boden entsprechen
   einem Pixel. Ein Messfehler wird dadurch einfach mitvergrößert.

Dazu kommt Licht: wird es zu dunkel, macht die Kamera die Belichtung
immer länger, bis sie am Anschlag steht (8191). Ab da sieht sie nur
noch Matsch.

Die Drohne merkt von all dem nichts. Sie meldet am Ende fast immer
einen kleinen Restfehler, weil sie ihren eigenen Drift nicht sehen
kann. Genau deshalb steht in der Auswertung eine geschätzte Abweichung
neben der behaupteten.
"""

from __future__ import annotations

import csv
import glob
import math
import os
import sys
from dataclasses import dataclass, field

TAKT = 0.05                 # s je Zeile der Aufnahme, wie im Flugskript

# --- Grenzwerte, gleich wie im Flugskript -----------------------------
SHUTTER_ANSCHLAG   = 8191   # darüber geht die Belichtung nicht
FLOW_SQUAL_SCHWACH = 30     # darunter arbeitet die Kamera dünn
FLOW_SQUAL_BLIND   = 5      # darunter sieht sie überhaupt nichts

# --- Grenzwerte für das Urteil ----------------------------------------
HOCH_M          = 1.00      # darüber wird der Flow-Fehler spürbar größer
DREH_VIEL_GRAD  = 360.0     # eine volle Umdrehung ist schon viel
DREH_ZUVIEL_GRAD = 1080.0   # drei Umdrehungen, ab hier wird es wacklig
DUNKEL_ANTEIL   = 0.05      # ab 5 % der Takte am Anschlag wird gewarnt
SCHWACH_ANTEIL  = 0.10      # ab 10 % schwacher Sicht wird gewarnt
GIER_SCHIEF     = 30.0      # Grad Restverdrehung, ab der es auffällt
# Der Rückflug dreht immer etwas mehr als der Hinflug: einmal wenden
# sind schon 180 Grad, und am Ende richtet sie sich aus. Erst deutlich
# darüber wird es zum Thema.
RUECK_MEHR_DREH_GRAD = 270.0
RUECK_MEHR_WEG       = 1.25 # 25 % Umweg gehen als Suchen durch

# --- Drift-Schätzung --------------------------------------------------
# Zwei Quellen, beide hier nebeneinander, weil sie weit auseinander
# liegen und beide ihre Berechtigung haben:
#
# a) Nachgemessen auf dem eigenen Boden: ein Flug ohne Drehen landete
#    8 cm daneben, einer mit 723 Grad Drehung 30 cm. Daraus die Gerade
#    unten. Das sind zwei Punkte, keine Messreihe -- die Zahl ist ein
#    Anhalt, kein Versprechen.
# b) Die Faustregel aus dem Bitcraze-Forum: rund 10 cm je 90 Grad.
#    Deutlich pessimistischer, gilt aber allgemein und nicht nur für
#    einen bestimmten Teppich.
GRUND_CM            = 8.0                       # Sockel auch ohne Drehen
CM_JE_100_GRAD      = (30.0 - GRUND_CM) / 7.23  # aus den zwei Messungen
FORUM_CM_JE_90_GRAD = 10.0                      # Bitcraze-Forum

HIER = os.path.dirname(os.path.abspath(__file__))


@dataclass
class Kennzahlen:
    """Was eine einzelne Aufnahme über ihren Abschnitt verrät."""
    takte: int = 0
    dauer_s: float = 0.0
    strecke_m: float = 0.0          # tatsächlich zurückgelegter Weg
    dreh_grad: float = 0.0          # aufsummiert, als Betrag
    gier_von: float = 0.0           # Blickrichtung am Anfang
    gier_bis: float = 0.0           # Blickrichtung am Ende
    hoehe_min: float = 0.0
    hoehe_max: float = 0.0
    hoehe_mittel: float = 0.0
    squal_min: float = 0.0
    squal_mittel: float = 0.0
    shutter_max: float = 0.0
    dunkle_takte: int = 0           # Takte mit Belichtung am Anschlag
    blinde_takte: int = 0           # Takte, in denen sie nichts sah
    schwache_takte: int = 0
    gebremst_takte: int = 0         # Multiranger hat eingegriffen
    akku_von: float = 0.0
    akku_bis: float = 0.0


@dataclass
class Flug:
    """Ein kompletter Heimflug: hin, zurück und was am Ende herauskam."""
    stempel: str
    hin: Kennzahlen | None = None
    rueck: Kennzahlen | None = None
    rest_x: float | None = None     # Abweichung laut Drohne
    rest_y: float | None = None
    rest_gier: float | None = None

    @property
    def rest_cm(self) -> float | None:
        """Wie weit die Drohne selbst meint, danebengelandet zu sein."""
        if self.rest_x is None or self.rest_y is None:
            return None
        return math.hypot(self.rest_x, self.rest_y) * 100.0

    @property
    def geflogen(self) -> bool:
        """Ein Fehlstart hinterlässt zwar eine Datei, aber keinen Flug."""
        return self.hin is not None and self.hin.dauer_s >= 5.0


# ---------------------------------------------------------------- Lesen

def _zahl(text: str | None) -> float | None:
    """Wandelt ein CSV-Feld in eine Zahl. Leere Felder gibt es oft: ein
    Multiranger-Wert fehlt, sobald nichts in Reichweite ist."""
    if text is None or text == '':
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _zeilen(pfad: str) -> list[dict[str, str]]:
    """Liest eine CSV mit Semikolon als Trenner."""
    with open(pfad, newline='', encoding='utf-8') as datei:
        return list(csv.DictReader(datei, delimiter=';'))


def _spalte(zeilen: list[dict[str, str]], name: str) -> list[float]:
    """Holt eine Spalte als Liste von Zahlen, ohne die Lücken."""
    werte = [_zahl(z.get(name)) for z in zeilen]
    return [w for w in werte if w is not None]


def _mittel(werte: list[float]) -> float:
    return sum(werte) / len(werte) if werte else 0.0


def kennzahlen(zeilen: list[dict[str, str]]) -> Kennzahlen:
    """Rechnet eine Aufnahme zu einem Satz Kennzahlen zusammen."""
    k = Kennzahlen(takte=len(zeilen))
    if not zeilen:
        return k

    zeit = _spalte(zeilen, 't_s')
    k.dauer_s = zeit[-1] if zeit else len(zeilen) * TAKT

    # Weg und Drehung aus den Sollwerten aufaddieren. Die Sollwerte
    # stehen lückenlos in jeder Zeile, die gemessene Position nicht.
    vorige_zeit: float | None = None
    for z in zeilen:
        t = _zahl(z.get('t_s'))
        if vorige_zeit is None or t is None:
            dt = TAKT
        else:
            dt = t - vorige_zeit
        if t is not None:
            vorige_zeit = t
        if dt <= 0.0 or dt > 1.0:       # Lücke oder Sprung in der Zeit
            dt = TAKT
        vx, vy = _zahl(z.get('vx_ms')), _zahl(z.get('vy_ms'))
        if vx is not None and vy is not None:
            k.strecke_m += math.hypot(vx, vy) * dt
        gier = _zahl(z.get('gier_grad_s'))
        if gier is not None:
            k.dreh_grad += abs(gier) * dt

    gier_ist = _spalte(zeilen, 'gier_ist_grad')
    if gier_ist:
        k.gier_von, k.gier_bis = gier_ist[0], gier_ist[-1]

    hoehen = _spalte(zeilen, 'z_ist_m')
    if hoehen:
        k.hoehe_min, k.hoehe_max = min(hoehen), max(hoehen)
        k.hoehe_mittel = _mittel(hoehen)

    squals = _spalte(zeilen, 'squal')
    if squals:
        k.squal_min, k.squal_mittel = min(squals), _mittel(squals)
        k.blinde_takte = sum(1 for s in squals if s < FLOW_SQUAL_BLIND)
        k.schwache_takte = sum(1 for s in squals if s < FLOW_SQUAL_SCHWACH)

    shutter = _spalte(zeilen, 'shutter')
    if shutter:
        k.shutter_max = max(shutter)
        k.dunkle_takte = sum(1 for s in shutter if s >= SHUTTER_ANSCHLAG)

    k.gebremst_takte = sum(1 for z in zeilen if z.get('gebremst') == '1')

    akku = _spalte(zeilen, 'vbat_v')
    if akku:
        k.akku_von, k.akku_bis = akku[0], akku[-1]

    return k


def flug_lesen(ordner: str, stempel: str) -> Flug:
    """Sammelt alle Dateien, die zu einem Zeitstempel gehören."""
    flug = Flug(stempel=stempel)

    for feld in ('hin', 'rueck'):
        pfad = os.path.join(ordner, 'heim_%s_%s.csv' % (feld, stempel))
        if os.path.exists(pfad):
            setattr(flug, feld, kennzahlen(_zeilen(pfad)))

    lande = os.path.join(ordner, 'heim_lande_%s.csv' % stempel)
    if os.path.exists(lande):
        zeilen = _zeilen(lande)
        if zeilen:
            flug.rest_x    = _zahl(zeilen[0].get('x_m'))
            flug.rest_y    = _zahl(zeilen[0].get('y_m'))
            flug.rest_gier = _zahl(zeilen[0].get('gier_grad'))

    return flug


def fluege_finden(ordner: str) -> list[str]:
    """Alle Zeitstempel im Ordner, ältester zuerst."""
    muster = os.path.join(ordner, 'heim_hin_*.csv')
    stempel = [os.path.basename(p)[len('heim_hin_'):-len('.csv')]
               for p in glob.glob(muster)]
    return sorted(stempel)


# ------------------------------------------------------------ Schätzung

def drift_schaetzen(dreh_grad: float) -> tuple[float, float]:
    """Wie weit sie vermutlich danebenliegt, in Zentimetern.

    Zurück kommen zwei Zahlen: die Schätzung nach den nachgemessenen
    Flügen und die pessimistischere Faustregel aus dem Bitcraze-Forum.
    Die Wahrheit liegt erfahrungsgemäß dazwischen.
    """
    gemessen = GRUND_CM + dreh_grad / 100.0 * CM_JE_100_GRAD
    forum    = GRUND_CM + dreh_grad / 90.0 * FORUM_CM_JE_90_GRAD
    return gemessen, forum


def _gier_differenz(von: float, bis: float) -> float:
    """Wie weit die Nase am Ende verdreht war, kürzester Weg."""
    return abs((bis - von + 180.0) % 360.0 - 180.0)


@dataclass
class Urteil:
    """Was an einem Flug auffällt, in Klartext."""
    note: str = 'gut'               # gut / brauchbar / schlecht
    gruende: list[str] = field(default_factory=list)
    rat: list[str] = field(default_factory=list)


def bewerten(flug: Flug) -> Urteil:
    """Sucht die Stellen, an denen der Flug Genauigkeit verloren hat."""
    u = Urteil()

    if not flug.geflogen:
        u.note = 'schlecht'
        if flug.hin is not None and flug.hin.blinde_takte >= flug.hin.takte:
            u.gruende.append('Fehlstart: die Bodenkamera sah nichts '
                             '(squal 0 von der ersten Zeile an)')
            u.rat.append('Licht an, gemusterter Boden, Linse unten am '
                         'Flow Deck sauber und frei')
        else:
            u.gruende.append('kein richtiger Flug, nur %.0f Sekunden'
                             % (flug.hin.dauer_s if flug.hin else 0.0))
        return u

    hin = flug.hin
    assert hin is not None          # von flug.geflogen schon geprüft

    # --- Drehen -------------------------------------------------------
    if hin.dreh_grad >= DREH_ZUVIEL_GRAD:
        u.note = 'schlecht'
        u.gruende.append('sehr viel gedreht: %.0f Grad, das sind %.1f '
                         'volle Umdrehungen'
                         % (hin.dreh_grad, hin.dreh_grad / 360.0))
        u.rat.append('Nase möglichst geradeaus lassen und mit den '
                     'Schultertasten seitwärts fliegen statt zu drehen')
    elif hin.dreh_grad >= DREH_VIEL_GRAD:
        u.note = 'brauchbar'
        u.gruende.append('viel gedreht: %.0f Grad' % hin.dreh_grad)
        u.rat.append('weniger drehen, das ist der größte Hebel')

    # --- Höhe ---------------------------------------------------------
    if hin.hoehe_max > HOCH_M:
        if u.note == 'gut':
            u.note = 'brauchbar'
        u.gruende.append('zeitweise hoch geflogen: bis %.2f m, im Mittel '
                         '%.2f m' % (hin.hoehe_max, hin.hoehe_mittel))
        u.rat.append('auf etwa 0,40 m bleiben -- je tiefer, desto '
                     'genauer sieht die Kamera den Boden')

    # --- Licht --------------------------------------------------------
    if hin.takte > 0:
        dunkel = hin.dunkle_takte / hin.takte
        schwach = hin.schwache_takte / hin.takte
        if dunkel >= DUNKEL_ANTEIL:
            if u.note == 'gut':
                u.note = 'brauchbar'
            u.gruende.append('zu dunkel: %.0f %% der Zeit stand die '
                             'Belichtung am Anschlag' % (dunkel * 100.0))
            u.rat.append('mehr Licht in die dunkle Raumhälfte')
        if schwach >= SCHWACH_ANTEIL:
            if u.note == 'gut':
                u.note = 'brauchbar'
            u.gruende.append('Bodenkamera zeitweise schwach: %.0f %% der '
                             'Zeit unter squal %d'
                             % (schwach * 100.0, FLOW_SQUAL_SCHWACH))
            u.rat.append('gemusterten Boden suchen, glänzendes Vinyl '
                         'spiegelt und gibt der Kamera nichts')

    # --- Rückflug gegen Hinflug ---------------------------------------
    # Der Rückflug soll denselben Weg zurücklegen. Braucht er deutlich
    # mehr Weg oder dreht er mehr, dann sucht er unterwegs -- und jede
    # dieser Zusatzdrehungen kostet wieder Genauigkeit.
    if flug.rueck is not None:
        mehr_dreh = flug.rueck.dreh_grad - hin.dreh_grad
        if mehr_dreh > RUECK_MEHR_DREH_GRAD:
            if u.note == 'gut':
                u.note = 'brauchbar'
            u.gruende.append('der Rückflug hat %.0f Grad mehr gedreht als '
                             'der Hinflug (%.0f statt %.0f)'
                             % (mehr_dreh, flug.rueck.dreh_grad,
                                hin.dreh_grad))
            u.rat.append('das macht das Skript selbst: es hält die Nase '
                         'in Flugrichtung und richtet am Ende aus')
    if flug.rueck is not None and hin.strecke_m > 0.5:
        mehr = flug.rueck.strecke_m / hin.strecke_m
        if mehr > RUECK_MEHR_WEG:
            if u.note == 'gut':
                u.note = 'brauchbar'
            u.gruende.append('der Rückflug brauchte %.0f %% mehr Weg '
                             '(%.1f statt %.1f m)'
                             % ((mehr - 1.0) * 100.0,
                                flug.rueck.strecke_m, hin.strecke_m))

    # --- Wie schief sie am Ende stand ---------------------------------
    if flug.rest_gier is not None and abs(flug.rest_gier) >= GIER_SCHIEF:
        u.note = 'schlecht'
        u.gruende.append('am Ende um %.0f Grad verdreht -- die '
                         'Positionsschätzung war weggelaufen'
                         % abs(flug.rest_gier))
        u.rat.append('diesen Flug nicht als Strecke aufheben')

    if not u.gruende:
        u.gruende.append('nichts Auffälliges')

    return u


# -------------------------------------------------------------- Bericht

def _abschnitt(titel: str, k: Kennzahlen) -> list[str]:
    """Die Kennzahlen eines Abschnitts als Textblock."""
    zeilen = ['  %s' % titel]
    zeilen.append('    Dauer %.0f s, Weg %.1f m, %d Takte'
                  % (k.dauer_s, k.strecke_m, k.takte))
    zeilen.append('    Drehung %.0f Grad (%.1f Umdrehungen)'
                  % (k.dreh_grad, k.dreh_grad / 360.0))
    zeilen.append('    Höhe %.2f bis %.2f m, im Mittel %.2f m'
                  % (k.hoehe_min, k.hoehe_max, k.hoehe_mittel))
    zeilen.append('    Bodenkamera squal %.0f im Mittel, %.0f am '
                  'schlechtesten' % (k.squal_mittel, k.squal_min))
    if k.dunkle_takte:
        zeilen.append('    Belichtung %d mal am Anschlag (%.0f %% der Zeit)'
                      % (k.dunkle_takte, 100.0 * k.dunkle_takte / max(k.takte, 1)))
    if k.gebremst_takte:
        zeilen.append('    Multiranger hat %d mal gebremst'
                      % k.gebremst_takte)
    if k.akku_von:
        zeilen.append('    Akku %.2f auf %.2f V' % (k.akku_von, k.akku_bis))
    return zeilen


def bericht(flug: Flug) -> list[str]:
    """Der vollständige Bericht zu einem Flug, Zeile für Zeile."""
    zeilen = ['', '=' * 62, 'Flug %s' % flug.stempel, '=' * 62]

    if flug.hin is not None:
        zeilen += _abschnitt('Hinflug (von Hand geflogen):', flug.hin)
    if flug.rueck is not None:
        zeilen.append('')
        zeilen += _abschnitt('Rückflug (allein geflogen):', flug.rueck)

    u = bewerten(flug)

    zeilen.append('')
    zeilen.append('  Wie weit daneben:')
    rest = flug.rest_cm
    if rest is None:
        zeilen.append('    Die Drohne hat nichts gemeldet (kein Rückflug).')
    else:
        zeilen.append('    Die Drohne behauptet %.0f cm' % rest)
        if flug.rest_gier is not None:
            zeilen.append('    und %.0f Grad Restverdrehung.'
                          % flug.rest_gier)
    if flug.geflogen and flug.hin is not None:
        gemessen, forum = drift_schaetzen(flug.hin.dreh_grad)
        if rest is not None and rest > forum:
            # Meldet sie selbst mehr, als die Faustregel hergibt, ist im
            # Flug etwas gerissen. Dann taugt keine Schätzung mehr, und
            # die echte Abweichung ist mindestens die gemeldete.
            zeilen.append('    Das ist mehr, als die Faustregel hergibt '
                          '(%.0f cm).' % forum)
            zeilen.append('    Hier ist die Positionsschätzung im Flug '
                          'zusammengebrochen --')
            zeilen.append('    sie lag also mindestens so weit daneben, '
                          'eher weiter.')
        else:
            zeilen.append('    Geschätzt sind es eher %.0f cm '
                          '(Faustregel aus dem Forum: bis %.0f cm).'
                          % (gemessen, forum))
            zeilen.append('    Nachmessen lohnt sich -- die Drohne sieht '
                          'ihren eigenen Drift nicht.')

    zeilen.append('')
    zeilen.append('  Urteil: %s' % u.note.upper())
    for grund in u.gruende:
        zeilen.append('    - %s' % grund)
    if u.rat:
        zeilen.append('')
        zeilen.append('  Was beim nächsten Mal hilft:')
        for rat in u.rat:
            zeilen.append('    -> %s' % rat)

    return zeilen


def kurz_zeile(flug: Flug) -> str:
    """Ein Flug in einer Zeile, für den Überblick."""
    if not flug.geflogen:
        return '%s  --  Fehlstart' % flug.stempel
    hin = flug.hin
    assert hin is not None
    rest = flug.rest_cm
    u = bewerten(flug)
    return ('%s  %3.0fs  %4.1fm  dreh %5.0f gr  hoch %.2fm  '
            'daneben %s  %s'
            % (flug.stempel, hin.dauer_s, hin.strecke_m, hin.dreh_grad,
               hin.hoehe_max,
               ('%3.0fcm' % rest) if rest is not None else '  ?  ',
               u.note))


def bestenliste(fluege: list[Flug]) -> list[str]:
    """Stellt die Flüge gegenüber und zieht das Fazit."""
    echte = [f for f in fluege if f.geflogen and f.rest_cm is not None]
    if len(echte) < 2:
        return []

    zeilen = ['', '=' * 62, 'Alle Flüge nebeneinander', '=' * 62, '']
    zeilen.append('  Drehung   behauptet   geschätzt   Urteil')
    zeilen.append('  ' + '-' * 46)
    for f in sorted(echte, key=lambda x: x.hin.dreh_grad if x.hin else 0.0):
        hin = f.hin
        assert hin is not None
        gemessen, _ = drift_schaetzen(hin.dreh_grad)
        zeilen.append('  %5.0f gr   %5.0f cm    %5.0f cm    %s'
                      % (hin.dreh_grad, f.rest_cm or 0.0, gemessen,
                         bewerten(f).note))

    bester = min(echte, key=lambda f: f.hin.dreh_grad if f.hin else 0.0)
    zeilen.append('')
    zeilen.append('  Am wenigsten gedreht hat der Flug %s.' % bester.stempel)
    zeilen.append('  Das ist die Richtung: wenig drehen, tief bleiben,')
    zeilen.append('  Licht an. Alles andere ist zweitrangig.')
    return zeilen


# ----------------------------------------------------------------- Main

def main(argumente: list[str]) -> int:
    kurz = 'kurz' in argumente
    # Alles außer dem Wort "kurz" gilt als Ordnername. Sonst landet ein
    # "python flug_auswerten.py kurz" bei einem Ordner namens kurz.
    rest = [a for a in argumente if a != 'kurz']
    ordner = rest[0] if rest else HIER

    if not os.path.isdir(ordner):
        print('Den Ordner gibt es nicht: %s' % ordner)
        return 1

    stempel = fluege_finden(ordner)
    if not stempel:
        print('In %s liegt kein Heimflug.' % ordner)
        print('Gesucht wird nach Dateien namens heim_hin_*.csv.')
        return 1

    print('Ordner: %s' % ordner)
    print('%d Flüge gefunden.' % len(stempel) if len(stempel) != 1
          else '1 Flug gefunden.')

    fluege = [flug_lesen(ordner, s) for s in stempel]

    if kurz:
        print('')
        for flug in fluege:
            print(kurz_zeile(flug))
    else:
        for flug in fluege:
            for zeile in bericht(flug):
                print(zeile)

    for zeile in bestenliste(fluege):
        print(zeile)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
