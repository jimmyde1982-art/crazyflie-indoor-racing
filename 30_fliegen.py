"""
30_fliegen.py  -  Das eine Flugskript
======================================



STARTEN
  python 30_fliegen.py              fliegen
  python 30_fliegen.py 3            mit Einstellung 3 beginnen
  python 30_fliegen.py h50          Starthoehe 50 cm
  python 30_fliegen.py d10          10 cm Abstand zur Decke
  python 30_fliegen.py frei         ohne Wandschutz und Deckenbremse
  python 30_fliegen.py ohnewand     nur der seitliche Schutz aus
  python 30_fliegen.py ohnedecke    nur die Deckenbremse aus
  python 30_fliegen.py sport        im sportlichen Modus starten
  python 30_fliegen.py rec          Flug aufzeichnen

  Alles kombinierbar:  python 30_fliegen.py 3 h40 d10


STEUERUNG
  A              starten
  B              landen
  START          NOT-AUS
  Y / X          Einstellung vor / zurueck
  LB halten      Schleichgang
  Linker Stick   hoch/runter = steigen/sinken, links/rechts = drehen
  Rechter Stick  vor/zurueck und seitwaerts
  Steuerkreuz    Flugfigur (links Kreis, rechts Acht,
                 hoch Spirale, runter Auf-und-Ab)
  RB + Kreuz     Trimmung gegen staendiges Wegdriften
  BACK           Flugmodus wechseln (SCHWEBEN / SPORTLICH)
  Strg+C         ebenfalls Not-Aus


DIE ZWEI FLUGMODI  -  das ist der "Assisted Mode" aus dem cfclient
  SCHWEBEN   Der Stick befiehlt eine GESCHWINDIGKEIT. Loslassen heisst
             bremsen und stehenbleiben, das Flow Deck haelt die Position.
             Ruhig, verzeihend, gut fuer enge Stellen und zum Kartieren.

  SPORTLICH  Der Stick befiehlt einen NEIGUNGSWINKEL, wie bei einem
             normalen Quadrocopter. Die Hoehe wird weiter automatisch
             gehalten. Reagiert deutlich direkter, weil kein Regler
             dazwischenrechnet - dafuer gleitet sie beim Loslassen aus.

  Beide nutzen dieselben Stickwerte und denselben Wandschutz. Nur die
  Uebersetzung am Ende ist anders. Umschalten mit BACK, auch im Flug.


WAS AUS 24 UEBERNOMMEN WURDE
  NOT-AUS WIRKT AUCH WAEHREND DES STARTS. Vorher war das Skript beim
  Druck auf A rund 2,5 Sekunden lang taub - Kalman zuruecksetzen,
  armen, hochfahren, alles mit festen Wartezeiten. Kippte sie in
  dieser Zeit, half kein Knopf. Jetzt wird in jeder Wartezeit weiter
  auf START gehorcht, und ein Funkabriss bricht die Sequenz ebenfalls
  ab. Siehe warten().

WAS AUS 25 UEBERNOMMEN WURDE
  WEICHE HINDERNIS-UMLEITUNG. Vor einem Hindernis bleibt sie nicht
  mehr einfach stehen, sondern schaut, wo mehr Platz ist, und schiebt
  sich sanft dorthin. Siehe schutz().

  VORLAUF-BREMSE. Die Sollhoehe darf der echten Hoehe nur begrenzt
  vorauslaufen. Das ist die Bremse gegen das Ueberschiessen an der
  Decke. Siehe DECKE_VORLAUF und vorlauf_bremsen().

WAS BEWUSST NICHT UEBERNOMMEN WURDE
  Der Setpoint-Watchdog aus 25. Er hilft nur gegen Haenger des
  Laptops - der haeufigste Absturzgrund hier sind aber Funkabrisse,
  und dagegen richtet er nichts aus. Fabian wollte ihn nicht.
"""

import csv
import json
import math
import os
import sys
import time
from datetime import datetime

import pygame

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils import uri_helper

URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')

BELEGUNG_DATEI = 'controller.json'
PAKET_DATEI = 'flugpaket.json'

# --- Die vier Einstellungen, identisch zu 22_welche_ist_besser.py ---------
STUFEN = [
    {'name': 'WIE BISHER',     'deadzone': 0.12, 'expo': 1.80, 'rampe': 0.25},
    {'name': 'ETWAS DIREKTER', 'deadzone': 0.10, 'expo': 1.50, 'rampe': 0.35},
    {'name': 'DIREKT',         'deadzone': 0.08, 'expo': 1.30, 'rampe': 0.50},
    {'name': 'SEHR DIREKT',    'deadzone': 0.06, 'expo': 1.10, 'rampe': 0.70},
]

# --- Flugwerte, unveraendert aus 13 --------------------------------------
# STARTHOEHE - auf diese Hoehe steigt sie, wenn du A drueckst.
# Ueberschreibbar beim Aufruf, ohne diese Datei zu aendern:
#     python 30_fliegen.py h30     startet auf 30 cm
#     python 30_fliegen.py h80     startet auf 80 cm
# Tief starten geht, aber unter etwa 30 cm staut sich die Propellerluft
# unter ihr (Bodeneffekt) und sie wird zappelig. Das ist Physik, kein
# Steuerungsproblem. Wird sie beim Abheben unruhig: hoeher starten.
START_HOEHE = 0.30
MIN_HOEHE = 0.25        # der Flow-Sensor braucht mindestens ~8 cm Sicht
STEIG_RATE = 0.45

# DECKENABSTAND - so nah darf sie an die Decke, nicht naeher.
# Gemessen wird mit dem Sensor OBEN am Multi-Ranger, also der echte
# Abstand im Moment. Das ist zuverlaessiger als eine feste Maximalhoehe:
# es funktioniert in jedem Raum, unabhaengig von der Deckenhoehe und
# davon, ob sie ueber Teppich oder Fliesen steht.
# Beim Aufruf aenderbar:  python 30_fliegen.py d10   -> 10 cm
# Zu 5 cm ehrlich: Der Laser rauscht um rund +-2 cm, und sie schwankt
# beim Schweben selbst ein paar Zentimeter. Bei 5 cm beruehrt sie die
# Decke irgendwann. 10 cm ist der kleinste Wert, den ich empfehle.
DECKEN_ABSTAND = 0.15

# Ab hier wird das Steigen gedrosselt - je naeher, desto langsamer.
# Genauso macht es der seitliche Kollisionsschutz, und der pendelt nicht.
# Quadratisch statt linear: kurz vor der Decke wird deutlich schaerfer
# gebremst.
DECKE_BREMS = 0.80

# So weit darf die SOLLhoehe der ECHTEN Hoehe hoechstens vorauslaufen.
#
# WARUM (gemessen 17.08.2026)
#   Die Firmware gibt umso mehr Gas, je weiter die Sollhoehe ueber der
#   echten Hoehe liegt. Im Log stand: Soll 2.20 m bei Ist 1.72 m - also
#   48 cm Vorsprung. Damit baut sie so viel Schwung auf, dass sie ueber
#   jede Bremse hinausschiesst: gemessen 15 cm ueber die Sollhoehe, bis
#   auf 1 cm an die Decke.
#
#   Der Wert darf nicht zu klein sein: Im normalen Steigflug liegt die
#   Sollhoehe ohnehin rund 23 cm voraus (Soll 1.03 / Ist 0.80). Das ist
#   die normale Regelabweichung und muss erlaubt bleiben, sonst steigt
#   sie gar nicht mehr. 0.30 liegt dazwischen.
DECKE_VORLAUF = 0.30

# Der Sensor oben setzt kurz aus (Lampe, schraege Lage, lockerer Deck-
# Stecker). Einzelne Aussetzer werden ueberbrueckt. Sieht er laenger
# nichts, darf sie nicht weitersteigen - blind nach oben ist gefaehrlich.
DECKE_BLIND_ZEIT = 1.0

# Bis hierher darf sie auch steigen, wenn der Sensor oben nichts sieht.
# Grund: In deinem Flug meldete er am Boden dauernd "---", weil die Decke
# mit gut 2 m schlicht ausserhalb seiner sicheren Reichweite lag. Ohne
# diese Ausnahme kaeme sie gar nicht erst hoch. Unter 1.20 m ist in einer
# Wohnung ohnehin keine Decke im Weg.
DECKE_FREI_BIS = 1.20

# So schnell darf die Deckenbegrenzung die Sollhoehe hoechstens senken.
# Ohne diese Bremse reisst ein Sprung des BODENsensors (Moebel, Teppich-
# kante - bekanntes Verhalten des Flow Decks) die Sollhoehe mit nach
# unten, und sie sackt schlagartig weg. Genau das ist am 16.08. passiert:
# Soll fiel in einem Schritt von 2.03 m auf 0.45 m.
DECKE_SINK_MAX = 0.35        # Meter pro Sekunde

decke_puffer = []
decke_zuletzt = [0.0]

# Notbremse, falls der Sensor oben nichts sieht (Dachschraege, offene
# Tuer nach oben, Sensor verdeckt). Muss HOEHER liegen als die Hoehe,
# die der Sensor ansteuert - sonst bremst sie zu frueh und der Sensor
# kommt nie zum Zug.
#   Deine Decke 2.39 m - 0.20 Abstand - 0.03 Bauhoehe = 2.16 m Sollhoehe.
#   Notbremse bei 2.20 m liegt knapp darueber und greift nur im Notfall
#   (dann bleiben immer noch 16 cm Luft).
MAX_HOEHE = 2.20
MAX_SPEED = 0.70
MAX_YAW = 90.0

TAKT = 0.03             # 33 Steuerbefehle pro Sekunde. Nicht erhoehen -
                        # mehr Funkverkehr hat frueher zu Abrissen gefuehrt,
                        # und ein Abriss im Flug bedeutet Absturz.

TRIMM_SCHRITT = 0.02
TRIMM_MAX = 0.25

# SICHERUNGEN
# Beide lassen sich beim Aufruf abschalten, ohne diese Datei zu aendern:
#     python 30_fliegen.py frei        beide aus, volle Handsteuerung
#     python 30_fliegen.py ohnewand    nur der seitliche Schutz aus
#     python 30_fliegen.py ohnedecke   nur die Deckenbremse aus
# Ohne Argument sind beide an.
SCHUTZ_AN = True         # seitlich: bremst vor Waenden und Moebeln
DECKE_AN = True          # oben: haelt Abstand zur Decke
BREMS_ABSTAND = 0.60
STOPP_ABSTAND = 0.30

# AKKUSCHUTZ
#
# GEMESSEN am 21.08.2026 mit 26_akku_ausdauer.py, 6869 Messpunkte:
#     3.20 V nach 2:43     <- hier stand die Grenze vorher
#     3.10 V nach 4:19
#     3.05 V nach 5:25
#     3.00 V nach 5:47     <- Ende
#
# Bei 3.20 V unter Motorlast ist die Zelle NICHT leer. Sie erholte sich
# nach dem Abschalten sofort wieder auf 3.45 V. Die Grenze von 3.20 V
# hat mehr als die Haelfte der nutzbaren Flugzeit abgeschnitten - genau
# das war der Grund fuer die 2:30, ueber die Fabian sich gewundert hat.
#
# 3.10 V liegt im flachen Teil der Entladekurve und laesst noch rund
# 1:30 Reserve bis zum echten Ende. Das ist der Kompromiss zwischen
# Flugzeit und Zellschonung.
#
# Achtung: Das ist die Spannung UNTER LAST, gemittelt ueber AKKU_FENSTER
# Messungen (rund 4 s). Die Ruhespannung liegt deutlich hoeher.
AKKU_NOTLANDUNG = 3.10
AKKU_FENSTER = 40

# Ab hier lohnt der Flug wirklich. Voll sind 4.2 V, ab 3.80 V verweigert
# die Firmware ohnehin den Start. Dazwischen fliegt sie zwar, haelt die
# Hoehe aber schlecht - die Motoren haben nicht mehr genug Reserve.
AKKU_EMPFOHLEN = 4.00

AUFZEICHNUNG_TAKT = 0.2
LANGSAM_FAKTOR = 0.4

# --- Belegung -------------------------------------------------------------
# Standardwerte = die aus 13_xbox_einfach.py, von Fabian bestaetigt.
# controller.json ueberschreibt sie, falls vorhanden.
ACHSEN = {'hoehe':  {'nr': 1, 'richtung': -1},
          'drehen': {'nr': 0, 'richtung': -1},
          'vor':    {'nr': 3, 'richtung': -1},
          'seit':   {'nr': 2, 'richtung': -1}}
KNOEPFE = {'start': 0, 'landen': 1, 'notaus': 7, 'langsam': 4,
           'zurueck': 2, 'weiter': 3,          # X = 2, Y = 3
           'trimm': 5,                          # RB = 5, haelt den Trimm-Modus
           'modus': 6}                          # BACK/Ansicht = Flugmodus

# ---------------------------------------------------------------------------
# FLUGMODUS - das ist derselbe Unterschied wie "Assisted Mode" im cfclient
#
#   SCHWEBEN   send_hover_setpoint(vx, vy, yawrate, hoehe)
#              Der Stick befiehlt eine GESCHWINDIGKEIT. Laesst du los,
#              bremst sie und bleibt stehen. Das Flow Deck haelt die
#              Position. Ruhig und verzeihend - gut zum Kartieren und
#              fuer enge Stellen.
#
#   SPORTLICH  send_zdistance_setpoint(roll, pitch, yawrate, hoehe)
#              Der Stick befiehlt einen NEIGUNGSWINKEL, so wie bei einem
#              normalen Quadrocopter. Die Hoehe wird weiter automatisch
#              gehalten. Reagiert deutlich direkter, weil kein Regler
#              dazwischenrechnet. Dafuer bleibt sie beim Loslassen nicht
#              stehen, sondern gleitet aus - du musst gegensteuern.
#
# Umschalten mit BACK (der kleine Knopf links neben der Xbox-Taste),
# am Boden und im Flug. Beim Aufruf:  python 30_fliegen.py sport
MODUS_SCHWEBEN = 'SCHWEBEN'
MODUS_SPORT = 'SPORTLICH'
modus = [MODUS_SCHWEBEN]

# Maximaler Neigungswinkel im sportlichen Modus, in Grad.
# Der cfclient nimmt ab Werk 30 Grad. Das ist fuer eine Wohnung viel:
# bei 30 Grad ist sie quer durch den Raum, bevor du reagierst.
# 15 Grad ist zuegig und noch beherrschbar - hochdrehen kannst du
# spaeter immer noch.
MAX_NEIGUNG = 15.0

# ---------------------------------------------------------------------------
# FLUGFIGUREN auf dem Steuerkreuz
#
# Ein echter Looping geht nicht - Bitcraze schreibt selbst, dass das
# ueber Funk wegen Latenz und Bandbreite nicht machbar ist, und die
# Firmware schaltet bei Kopfueberlage die Motoren ab. Diese Figuren
# bleiben deshalb immer waagerecht und sind trotzdem etwas fuers Auge.
#
#   Steuerkreuz LINKS    Kreis
#   Steuerkreuz RECHTS   liegende Acht
#   Steuerkreuz HOCH     Spirale nach oben
#   Steuerkreuz RUNTER   Auf und Ab
#
# Waehrend einer Figur: jeder Stickausschlag bricht ab, START ebenfalls.
#
# WIE EIN KREIS ENTSTEHT
#   Konstant vorwaerts fliegen UND gleichzeitig konstant drehen ergibt
#   einen Kreis. Der Radius folgt aus beidem:
#       Radius = Geschwindigkeit / Drehrate (im Bogenmass)
#   Bei 0.40 m/s und 60 Grad/s sind das rund 0.38 m Radius,
#   also gut 0.75 m Durchmesser.
FIGUR_TEMPO = 0.40          # m/s vorwaerts waehrend der Figur
FIGUR_DREHRATE = 60.0       # Grad/s
FIGUR_STICK_ABBRUCH = 0.25  # ab diesem Stickausschlag wird abgebrochen

# Platzbedarf je Figur, in Metern rundum. Nachgemessen an der
# simulierten Flugbahn, plus rund 0.3 m Puffer:
#   Kreis     0.76 m Ausdehnung
#   Acht      1.47 m  (sie wandert waehrend der zwei Boegen)
#   Spirale   0.76 m
#   Auf-Ab    bleibt auf der Stelle
FIGUR_PLATZ = {'kreis': 1.10, 'acht': 1.80,
               'spirale': 1.10, 'aufab': 0.40}

d = {'vbat': 0.0, 'zrange': None, 'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0}
verlauf = []
glatt = {'vor': 0.0, 'seit': 0.0, 'dreh': 0.0}
trimm = {'vor': 0.0, 'seit': 0.0}
nullpunkt = {}

# Funkabriss. Wird vom Verbindungs-Callback gesetzt und in warten()
# geprueft - dann bricht auch eine laufende Startsequenz sofort ab.
# Ein Abriss im Flug bedeutet, dass die Firmware die Motoren abschaltet.
funk = {'weg': False}
stufe = [0]


def belegung_laden():
    """Achsen und Knoepfe aus der Datei. Die Ruhelage NICHT - die springt
    bei jedem Einschalten des Controllers und wird unten frisch gemessen."""
    if not os.path.exists(BELEGUNG_DATEI):
        return 'Standardwerte (controller.json nicht gefunden)'
    try:
        with open(BELEGUNG_DATEI, encoding='utf-8') as f:
            g = json.load(f)
        if 'achsen' in g:
            ACHSEN.update(g['achsen'])
        if 'knoepfe' in g:
            for k, v in g['knoepfe'].items():
                KNOEPFE[k] = v
        return BELEGUNG_DATEI
    except Exception as fehler:
        return 'controller.json unlesbar (%s), Standardwerte' % fehler


def pose_empfangen(zeitstempel, daten, logconf):
    for name, ziel in [('kalman.stateX', 'x'), ('kalman.stateY', 'y'),
                       ('kalman.stateZ', 'z'), ('stabilizer.yaw', 'yaw')]:
        if name in daten:
            d[ziel] = daten[name]


def telemetrie(zeitstempel, daten, logconf):
    if 'pm.vbat' in daten:
        d['vbat'] = daten['pm.vbat']
        verlauf.append(d['vbat'])
        if len(verlauf) > AKKU_FENSTER:
            verlauf.pop(0)
    for name in ['range.zrange', 'range.front', 'range.back',
                 'range.left', 'range.right', 'range.up']:
        if name in daten:
            d[name] = daten[name] / 1000.0
    d['zrange'] = d.get('range.zrange')


def akku_mittel():
    return sum(verlauf) / len(verlauf) if verlauf else 0.0


def nullpunkt_messen(pad):
    """Ruhelage der Sticks. Muss jedes Mal neu gemessen werden - der
    Xbox-Nullpunkt springt bei jedem Einschalten des Controllers."""
    print('Messe die Ruhelage der Sticks - bitte NICHT anfassen ...')
    proben = {}
    for _ in range(30):
        pygame.event.pump()
        for i in range(pad.get_numaxes()):
            proben.setdefault(i, []).append(pad.get_axis(i))
        time.sleep(0.02)

    groesster = 0.0
    for i, werte in proben.items():
        nullpunkt[i] = sum(werte) / len(werte)
        if abs(nullpunkt[i]) < 0.9:        # Trigger stehen in Ruhe bei -1
            groesster = max(groesster, abs(nullpunkt[i]))

    if groesster > 0.25:
        print('ACHTUNG: sehr grosser Versatz (%.3f).' % groesster)
        print('Lag der Controller beim Einschalten schief?')
        print('Controller aus- und einschalten, dann neu starten.')
    elif groesster > 0.03:
        print('Leichter Versatz (%.3f) erkannt und herausgerechnet.'
              % groesster)
    else:
        print('Sticks stehen sauber auf null.')
    print('')


def stick(pad, name):
    """Stickwert einer Funktion, fertig umgerechnet nach aktueller Stufe."""
    a = ACHSEN.get(name)
    if a is None or a['nr'] >= pad.get_numaxes():
        return 0.0
    x = pad.get_axis(a['nr']) - nullpunkt.get(a['nr'], 0.0)
    x = max(-1.0, min(1.0, x * a['richtung']))
    s = STUFEN[stufe[0]]
    if abs(x) < s['deadzone']:
        return 0.0
    rest = (abs(x) - s['deadzone']) / (1.0 - s['deadzone'])
    return math.copysign(rest ** s['expo'], x)


def glaetten(name, ziel):
    glatt[name] += (ziel - glatt[name]) * STUFEN[stufe[0]]['rampe']
    if abs(glatt[name]) < 0.005:
        glatt[name] = 0.0
    return glatt[name]


def knopf(pad, name):
    nr = KNOEPFE.get(name)
    if nr is None or nr >= pad.get_numbuttons():
        return False
    return bool(pad.get_button(nr))


def abstand(name):
    wert = d.get('range.' + name)
    if wert is None or wert <= 0 or wert > 4.0:
        return None
    return wert


def bremsfaktor(name):
    weg = abstand(name)
    if weg is None or weg >= BREMS_ABSTAND:
        return 1.0
    if weg <= STOPP_ABSTAND:
        return 0.0
    return (weg - STOPP_ABSTAND) / (BREMS_ABSTAND - STOPP_ABSTAND)


# BODEN-SPRUNG-AUSGLEICH
# Das ist KEINE Sicherung, sondern eine Korrektur - deshalb bleibt sie
# auch bei "frei" eingeschaltet.
#
# Das Problem: Der Flow-Sensor misst den Abstand zum naechsten Ding
# unter ihr. Fliegst du ueber den Tisch, sieht er statt des Bodens die
# Tischplatte - aus 1.00 m werden schlagartig 0.30 m. Die Firmware
# haelt sich fuer viel zu tief und gibt Vollgas: Sie schiesst senkrecht
# hoch. Beim Verlassen des Tisches passiert dasselbe nach unten.
#
# Die Loesung: Springt der Messwert in einem Takt um mehr als
# BODEN_SPRUNG_SCHWELLE, ist das kein echtes Sinken, sondern ein neuer
# Untergrund. Die Sollhoehe wird dann um denselben Betrag mitgezogen -
# damit bleibt sie auf gleicher Hoehe ueber dem Tisch stehen, statt
# hochzuschiessen.
BODEN_SPRUNG_AUS = True
BODEN_SPRUNG_SCHWELLE = 0.25     # Meter in einem Takt

# Sperrzeit nach einem Ausgleich, in Sekunden.
#
# WARUM (Fabian, 19.08.2026: "schaukelt und wippt stark")
#   Fliegst du GENAU ueber eine Kante - Tischrand, Teppichkante,
#   Sofalehne - springt der Bodensensor mehrfach hin und her: Tisch,
#   Boden, Tisch, Boden. Ohne Sperre wird die Sollhoehe jedes Mal
#   mitgezogen, und die Firmware versucht jedem Sprung zu folgen.
#   Gas rauf, Gas runter, rauf, runter - das ist das Wippen.
#
#   Mit Sperre wird nach einem Ausgleich kurz nicht mehr korrigiert.
#   Ein einzelner Kantenwechsel wird sauber ausgeglichen, das schnelle
#   Hin und Her aber nicht mehr mitgemacht.
#
#   Die Schwelle stand vorher auf 0.15 m - das reagierte schon auf das
#   normale Rauschen des Flow Decks. 0.25 m loest nur noch bei echten
#   Moebelkanten aus.
BODEN_SPERRE = 0.5

boden_letzt = [None]
boden_sperre_bis = [0.0]


def boden_sprung_ausgleichen(hoehe):
    """Faengt den Vollgas-Schub ab, wenn sie ueber ein Moebel fliegt."""
    ist = d.get('zrange')
    if not BODEN_SPRUNG_AUS or ist is None or ist <= 0:
        boden_letzt[0] = ist
        return hoehe, ''

    vorher = boden_letzt[0]
    boden_letzt[0] = ist
    if vorher is None:
        return hoehe, ''

    sprung = ist - vorher
    if abs(sprung) < BODEN_SPRUNG_SCHWELLE:
        return hoehe, ''

    # Kurz nach einem Ausgleich nicht schon wieder korrigieren -
    # sonst schaukelt sie sich an einer Kante auf.
    if time.time() < boden_sperre_bis[0]:
        return hoehe, '  BODEN?'

    boden_sperre_bis[0] = time.time() + BODEN_SPERRE
    neu = max(MIN_HOEHE, min(MAX_HOEHE, hoehe + sprung))
    return neu, '  BODEN %+.2f' % sprung


def deckenabstand():
    """Geglaetteter Abstand nach oben. None, wenn der Sensor blind ist.

    Einzelne Aussetzer ueberbrueckt der Puffer. Der Median wirft
    Ausreisser raus - eine einzelne Fehlmessung soll die Drohne nicht
    ruckartig absacken lassen.
    """
    roh = abstand('up')
    if roh is not None:
        decke_puffer.append(roh)
        if len(decke_puffer) > 6:
            decke_puffer.pop(0)
        decke_zuletzt[0] = time.time()
    elif time.time() - decke_zuletzt[0] > DECKE_BLIND_ZEIT:
        decke_puffer.clear()
        return None
    if not decke_puffer:
        return None
    return sorted(decke_puffer)[len(decke_puffer) // 2]


def vorlauf_bremsen(neu, hinweis):
    """Die Sollhoehe darf der echten Hoehe nur ein Stueck vorauslaufen.

    Das ist die eigentliche Bremse gegen das Ueberschiessen an der
    Decke - Begruendung und Messwerte stehen oben bei DECKE_VORLAUF.
    """
    ist = d.get('zrange')
    if ist is None or ist <= 0:
        return neu, hinweis
    obergrenze = ist + DECKE_VORLAUF
    if neu > obergrenze:
        return obergrenze, (hinweis or '  BREMST')
    return neu, hinweis


def decke_begrenzen(hoehe, steig):
    """Haelt DECKEN_ABSTAND ein, ohne zu pendeln.

    WARUM DIE ERSTE FASSUNG GESCHAUKELT HAT
      Sie hat die Sollhoehe pro Takt um 1 cm zurueckgezogen, waehrend
      der Stick weiter "hoch" sagte. Zwei Kraefte gegeneinander, dazu
      die traege echte Hoehe, die der Sollhoehe hinterherhinkt und dann
      drueberschiesst - das ergibt eine Schaukel. Gemessen wurden 4 cm
      Restabstand statt 20.

    WAS JETZT PASSIERT - zwei Stufen, beide ohne Rueckzug:

      1. DROSSELN. Je naeher die Decke, desto langsamer das Steigen.
         Ab DECKE_BREMS wird gebremst, beim Zielabstand ist Schluss.
         Genau wie der seitliche Kollisionsschutz, der nicht pendelt.
         Langsames Steigen heisst auch: kaum Ueberschwingen.

      2. ABSOLUTE OBERGRENZE. Aus den Messwerten wird direkt bestimmt,
         wo die Sollhoehe hoechstens stehen darf:

             Grenze = aktuelle Hoehe + (Deckenabstand - Zielabstand)

         Das ist selbstkorrigierend und hat kein Gedaechtnis:
           Abstand groesser als Ziel -> Grenze liegt ueber ihr, sie darf hoch
           Abstand genau Ziel        -> Grenze = aktuelle Hoehe, sie haelt
           Abstand kleiner als Ziel  -> Grenze liegt darunter, sie sinkt
         Weil nichts aufaddiert wird, kann sich auch nichts aufschaukeln.

      Blinder Sensor: nicht weitersteigen. Nach oben blind zu fliegen
      ist genau die Situation, in der man anstoesst.
    """
    if not DECKE_AN:
        # Deckenbremse abgeschaltet - nur die harte Notbremse MAX_HOEHE
        # bleibt, sonst faehrt sie ins Unendliche.
        neu = hoehe + steig * TAKT
        return max(MIN_HOEHE, min(MAX_HOEHE, neu)), ''

    oben = deckenabstand()
    hinweis = ''

    if oben is None:
        # Kein Messwert. Unterhalb von DECKE_FREI_BIS ist das harmlos -
        # dort ist die Decke einfach ausser Reichweite des Sensors.
        # Darueber wird das Steigen gesperrt, Sinken bleibt frei.
        if hoehe < DECKE_FREI_BIS:
            neu = hoehe + steig * TAKT
            neu, hinweis = vorlauf_bremsen(neu, '')
            return max(MIN_HOEHE, min(DECKE_FREI_BIS, neu)), hinweis
        steig = min(steig, 0.0)
        neu = hoehe + steig * TAKT
        return max(MIN_HOEHE, min(MAX_HOEHE, neu)), '  DECKE?'

    # 1. Steigen drosseln - quadratisch, also nah an der Decke deutlich
    #    schaerfer als bei gleichmaessiger Drosselung
    if steig > 0:
        if oben <= DECKEN_ABSTAND:
            f = 0.0
        elif oben >= DECKE_BREMS:
            f = 1.0
        else:
            anteil = (oben - DECKEN_ABSTAND) / (DECKE_BREMS - DECKEN_ABSTAND)
            f = anteil * anteil
        if f < 1.0:
            hinweis = '  DECKE'
        steig *= f

    neu = hoehe + steig * TAKT

    # 2. absolute Obergrenze aus der Messung
    ist = d.get('zrange')
    if ist is not None and ist > 0:
        grenze = ist + (oben - DECKEN_ABSTAND)
        # Nach unten nur mit begrenztem Tempo. Springt der Bodensensor
        # (Moebel unter ihr), springt sonst die Sollhoehe mit und sie
        # faellt. Steigen bleibt davon unberuehrt.
        grenze = max(grenze, hoehe - DECKE_SINK_MAX * TAKT)
        if grenze < neu:
            neu = grenze
            hinweis = '  DECKE'

    # 3. zuletzt: Sollhoehe darf der echten Hoehe nicht davonlaufen
    neu, hinweis = vorlauf_bremsen(neu, hinweis)

    return max(MIN_HOEHE, min(MAX_HOEHE, neu)), hinweis


def schutz(vor, seit):
    """Drosselt nur die Richtung, in der ein Hindernis steht.
    Wegfliegen bleibt immer moeglich."""
    if not SCHUTZ_AN:
        return vor, seit, ''
    warnung = []
    if vor > 0:
        f = bremsfaktor('front')
        if f < 1.0:
            warnung.append('vorne')
            # WEICHE UMLEITUNG (uebernommen aus 25, 19.08.2026)
            # Vorher blieb sie vor einem Hindernis einfach stehen. Jetzt
            # schaut sie, ob links oder rechts mehr Platz ist, und schiebt
            # sich sanft dorthin. Sie fliesst um das Hindernis herum,
            # statt davor zu kleben. Der Ausweichanteil ist bewusst klein
            # (hoechstens 0.2 m/s) - du sollst nicht das Gefuehl haben,
            # dass sie dir den Stick aus der Hand nimmt.
            links_frei = abstand('left')
            rechts_frei = abstand('right')
            ausweich = 0.2 * (1.0 - f)
            genug = STOPP_ABSTAND + 0.1
            if links_frei is not None and rechts_frei is not None:
                if links_frei > rechts_frei and links_frei > genug:
                    seit += ausweich * min(1.0, links_frei)
                elif rechts_frei > genug:
                    seit -= ausweich * min(1.0, rechts_frei)
            elif links_frei is not None and links_frei > genug:
                seit += ausweich * min(1.0, links_frei)
            elif rechts_frei is not None and rechts_frei > genug:
                seit -= ausweich * min(1.0, rechts_frei)
        vor *= f
    elif vor < 0:
        f = bremsfaktor('back')
        if f < 1.0:
            warnung.append('hinten')
        vor *= f
    if seit > 0:
        f = bremsfaktor('left')
        if f < 1.0:
            warnung.append('links')
        seit *= f
    elif seit < 0:
        f = bremsfaktor('right')
        if f < 1.0:
            warnung.append('rechts')
        seit *= f
    return vor, seit, ('  STOPP: ' + '/'.join(warnung)) if warnung else ''


def genug_platz(welche):
    """Ist rundum genug frei fuer DIESE Figur? Gibt (ja, Meldung) zurueck."""
    noetig = FIGUR_PLATZ.get(welche, 1.10)
    eng = []
    for name, wohin in [('front', 'vorne'), ('back', 'hinten'),
                        ('left', 'links'), ('right', 'rechts')]:
        weg = abstand(name)
        if weg is not None and weg < noetig:
            eng.append('%s %.2f m' % (wohin, weg))
    if eng:
        return False, 'zu eng: ' + ', '.join(eng)
    return True, ''


def figur_abbruch(pad):
    """True, wenn der Pilot eingreift - Stick bewegt oder Not-Aus."""
    if knopf(pad, 'notaus'):
        return 'NOT-AUS'
    for name in ('vor', 'seit', 'drehen', 'hoehe'):
        if abs(stick_roh(pad, name)) > FIGUR_STICK_ABBRUCH:
            return 'Stick bewegt'
    return None


def stick_roh(pad, name):
    """Stickwert OHNE Deadzone und Expo - nur zum Abbruch-Erkennen."""
    a = ACHSEN.get(name)
    if a is None or a['nr'] >= pad.get_numaxes():
        return 0.0
    x = pad.get_axis(a['nr']) - nullpunkt.get(a['nr'], 0.0)
    return max(-1.0, min(1.0, x * a['richtung']))


def figur_fliegen(cf, pad, welche, hoehe):
    """Faehrt eine Figur ab. Gibt die Hoehe am Ende zurueck.

    Waehrend der Figur laeuft der Kollisionsschutz weiter, sofern er
    eingeschaltet ist. Die Drohne kann also auch mitten in der Figur
    noch vor einem Hindernis bremsen.
    """
    namen = {'kreis': 'KREIS', 'acht': 'LIEGENDE ACHT',
             'spirale': 'SPIRALE HOCH', 'aufab': 'AUF UND AB'}
    print('\n  >>> %s' % namen.get(welche, welche))

    ok, meldung = genug_platz(welche)
    if not ok:
        print('  Abgebrochen - %s' % meldung)
        print('  Diese Figur braucht rundum %.2f m Platz.'
              % FIGUR_PLATZ.get(welche, 1.10))
        return hoehe

    start_hoehe = hoehe
    beginn = time.time()

    # Bauplan jeder Figur: Liste aus (Dauer, vorwaerts, Drehrate, Steigen)
    umlauf = 360.0 / FIGUR_DREHRATE          # Sekunden fuer einen Kreis
    if welche == 'kreis':
        plan = [(umlauf, FIGUR_TEMPO, -FIGUR_DREHRATE, 0.0)]
    elif welche == 'acht':
        plan = [(umlauf, FIGUR_TEMPO, -FIGUR_DREHRATE, 0.0),
                (umlauf, FIGUR_TEMPO, +FIGUR_DREHRATE, 0.0)]
    elif welche == 'spirale':
        plan = [(umlauf, FIGUR_TEMPO, -FIGUR_DREHRATE, +0.12)]
    elif welche == 'aufab':
        plan = [(1.5, 0.0, 0.0, +0.30), (1.5, 0.0, 0.0, -0.30),
                (1.5, 0.0, 0.0, +0.30), (1.5, 0.0, 0.0, -0.30)]
    else:
        return hoehe

    for dauer, vor, dreh, steig in plan:
        ende = time.time() + dauer
        while time.time() < ende:
            grund = figur_abbruch(pad)
            if grund:
                print('  Abgebrochen (%s)' % grund)
                return hoehe

            v, s, _ = schutz(vor, 0.0)
            hoehe, _ = boden_sprung_ausgleichen(hoehe)
            hoehe, _ = decke_begrenzen(hoehe, steig)
            cf.commander.send_hover_setpoint(v, s, dreh, hoehe)
            time.sleep(TAKT)

    # sanft zurueck auf die Ausgangshoehe
    while abs(hoehe - start_hoehe) > 0.02:
        if figur_abbruch(pad):
            break
        richtung = 0.3 if hoehe < start_hoehe else -0.3
        hoehe, _ = decke_begrenzen(hoehe, richtung)
        cf.commander.send_hover_setpoint(0, 0, 0, hoehe)
        time.sleep(TAKT)

    print('  Fertig nach %.1f s' % (time.time() - beginn))
    return hoehe


def trimmen(pad, frei):
    if pad.get_numhats() < 1 or not frei:
        return False
    if not knopf(pad, 'trimm'):     # Trimmen nur mit gedruecktem RB
        return False
    x, y = pad.get_hat(0)
    if x == 0 and y == 0:
        return False
    if y != 0:
        trimm['vor'] = max(-TRIMM_MAX, min(TRIMM_MAX,
                                           trimm['vor'] + y * TRIMM_SCHRITT))
    if x != 0:
        trimm['seit'] = max(-TRIMM_MAX, min(TRIMM_MAX,
                                            trimm['seit'] + x * TRIMM_SCHRITT))
    return True


def arm(cf, an):
    try:
        cf.supervisor.send_arming_request(an)
    except Exception:
        try:
            cf.platform.send_arming_request(an)
        except Exception:
            pass


class NotAus(Exception):
    """Wird geworfen, sobald der Not-Aus-Knopf gedrueckt wird."""


def warten(pad, sekunden):
    """Wie time.sleep(), aber der Not-Aus bleibt die ganze Zeit scharf.

    UEBERNOMMEN AUS 24_fliegen.py (19.08.2026)
      Vorher hat das Skript beim Druck auf A rund 2,5 Sekunden lang gar
      nichts mehr vom Controller gelesen: Kalman zuruecksetzen, armen,
      hochfahren - alles mit festen Wartezeiten. Genau in dieser Zeit
      kippt sie, wenn etwas schiefgeht, und der Not-Aus half nicht.
      Jetzt wird waehrend jeder Wartezeit weiter auf START gehorcht.
    """
    ende = time.time() + sekunden
    while time.time() < ende:
        pygame.event.pump()
        if knopf(pad, 'notaus'):
            raise NotAus()
        if funk['weg']:
            raise NotAus()
        time.sleep(0.01)


def start_vorbereiten(cf, pad):
    cf.commander.send_stop_setpoint()
    warten(pad, 0.1)
    cf.commander.send_setpoint(0, 0, 0, 0)
    warten(pad, 0.1)
    cf.param.set_value('kalman.resetEstimation', '1')
    warten(pad, 0.2)
    cf.param.set_value('kalman.resetEstimation', '0')
    warten(pad, 1.5)
    arm(cf, True)
    warten(pad, 0.3)


def hochfahren(cf, pad, ziel):
    hoehe = 0.05
    while hoehe < ziel:
        hoehe += 0.02
        cf.commander.send_hover_setpoint(0, 0, 0, hoehe)
        warten(pad, TAKT)
    warten(pad, 0.5)
    gemessen = d.get('zrange')
    if gemessen is not None and gemessen < 0.10:
        print('\n  SIE HEBT NICHT AB (gemessen %.2f m).' % gemessen)
        print('  Motoren laufen, aber sie bleibt liegen. Pruefe:')
        print('   - Propeller verbogen, lose oder falsch herum?')
        print('   - diagonal gegenueber derselbe Buchstabe?')
        print('   - Akku unter 3.8 V?')
        print('  Landen mit B, dann Propeller kontrollieren.\n')
        return False
    return True


def runterfahren(cf, pad, von):
    """Sanft landen. Beim Landen wird der Not-Aus NICHT abgefragt -
    sie ist ohnehin auf dem Weg nach unten, und ein Abbruch mitten im
    Sinkflug wuerde sie aus der Luft fallen lassen."""
    hoehe = von
    while hoehe > 0.06:
        hoehe -= 0.015
        cf.commander.send_hover_setpoint(0, 0, 0, hoehe)
        time.sleep(TAKT)
    for _ in range(3):
        cf.commander.send_stop_setpoint()
        time.sleep(0.05)
    arm(cf, False)


def aufzeichnung_starten():
    name = 'flug_' + datetime.now().strftime('%Y-%m-%d_%H%M') + '.csv'
    datei = open(name, 'w', newline='', encoding='utf-8')
    schreiber = csv.writer(datei, delimiter=';')
    schreiber.writerow(['zeit_s', 'x_m', 'y_m', 'z_m', 'yaw_grad',
                        'vorne_m', 'hinten_m', 'links_m', 'rechts_m',
                        'oben_m', 'unten_m', 'einstellung'])
    return datei, schreiber, name


def aufzeichnen(schreiber, start):
    def w(schluessel):
        wert = d.get('range.' + schluessel)
        if wert is None or wert <= 0 or wert > 4.0:
            return ''
        return '%.3f' % wert
    schreiber.writerow([
        '%.2f' % (time.time() - start),
        '%.3f' % d['x'], '%.3f' % d['y'], '%.3f' % d['z'], '%.1f' % d['yaw'],
        w('front'), w('back'), w('left'), w('right'), w('up'), w('zrange'),
        stufe[0] + 1])


def paket_speichern():
    s = STUFEN[stufe[0]]
    paket = {'_gewaehlt': s['name'], '_stufe': stufe[0] + 1,
             'deadzone': s['deadzone'], 'expo': s['expo'], 'rampe': s['rampe'],
             'max_speed': MAX_SPEED, 'max_yaw': MAX_YAW,
             'steig_rate': STEIG_RATE, 'min_hoehe': MIN_HOEHE,
             'max_hoehe': MAX_HOEHE, 'start_hoehe': START_HOEHE,
             'hoehen_modus': 'A'}
    try:
        with open(PAKET_DATEI, 'w', encoding='utf-8') as f:
            json.dump(paket, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def log_variablen_pruefen(cf, namen):
    """Welche dieser Messwerte kennt DIESE Drohne wirklich?

    Jedes Deck bringt eigene Messwerte mit. Steckt das Deck nicht, kennt
    die Firmware den Namen nicht, und add_config wirft einen KeyError -
    das Skript stuerzt beim Start ab, noch bevor irgendetwas erklaert wird.
    Also vorher im Inhaltsverzeichnis (TOC) nachsehen."""
    da, fehlt = [], []
    for n in namen:
        try:
            if cf.log.toc.get_element_by_complete_name(n) is not None:
                da.append(n)
            else:
                fehlt.append(n)
        except Exception:
            fehlt.append(n)
    return da, fehlt


def main():
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print('Kein Gamepad gefunden. Controller einschalten, neu starten.')
        return
    pad = pygame.joystick.Joystick(0)
    pad.init()
    print('Gamepad : ' + pad.get_name())
    print('Belegung: ' + belegung_laden())

    global START_HOEHE, SCHUTZ_AN, DECKE_AN, DECKEN_ABSTAND
    global BODEN_SPRUNG_AUS
    aufnahme = False
    for a in sys.argv[1:]:
        a = a.lower()
        if a == 'rec':
            aufnahme = True
        elif a == 'frei':
            SCHUTZ_AN = False
            DECKE_AN = False
        elif a == 'ohnewand':
            SCHUTZ_AN = False
        elif a == 'ohnedecke':
            DECKE_AN = False
        elif a.startswith('h') and a[1:].isdigit():
            # h30 = 30 cm. Nicht tiefer als die Mindesthoehe, nicht
            # hoeher als die Notbremse - sonst startet sie in die Decke.
            gewuenscht = int(a[1:]) / 100.0
            START_HOEHE = max(MIN_HOEHE, min(MAX_HOEHE, gewuenscht))
            if START_HOEHE != gewuenscht:
                print('Starthoehe %.2f m ist nicht erlaubt, nehme %.2f m'
                      % (gewuenscht, START_HOEHE))
        elif a in ('sport', 'sportlich'):
            modus[0] = MODUS_SPORT
        elif a in ('ohneboden', 'ohnebodensprung'):
            BODEN_SPRUNG_AUS = False
        elif a.startswith('d') and a[1:].isdigit():
            # d10 = 10 cm Abstand zur Decke
            gewuenscht = int(a[1:]) / 100.0
            DECKEN_ABSTAND = max(0.05, min(1.00, gewuenscht))
            if DECKEN_ABSTAND != gewuenscht:
                print('Deckenabstand %.2f m nicht erlaubt, nehme %.2f m'
                      % (gewuenscht, DECKEN_ABSTAND))
        elif a.isdigit() and 1 <= int(a) <= len(STUFEN):
            stufe[0] = int(a) - 1
    print('Start mit Einstellung %d - %s'
          % (stufe[0] + 1, STUFEN[stufe[0]]['name']))
    print('Starthoehe %.2f m%s'
          % (START_HOEHE,
             '   (tief - achte auf Zappeln beim Abheben)'
             if START_HOEHE < 0.35 else ''))
    print('')

    nullpunkt_messen(pad)

    cflib.crtp.init_drivers()
    print('Verbinde mit ' + URI + ' ...')

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf
        print('Verbunden.')

        # range.up kommt ins SELBE Paket - kein zusaetzlicher Funkverkehr.
        # 4 Byte (vbat) + 6 x 2 Byte = 16 Byte, die Grenze liegt bei 26.
        # Eingetragen wird aber nur, was diese Drohne auch kennt: ohne
        # Multi-Ranger gibt es front/back/left/right/up schlicht nicht.
        wunsch = ['range.zrange', 'range.front', 'range.back',
                  'range.left', 'range.right', 'range.up']
        vorhanden, fehlen = log_variablen_pruefen(cf, wunsch)

        if 'range.zrange' not in vorhanden:
            print('')
            print('  !!! KEIN FLOW-DECK ERKANNT !!!')
            print('  Ohne Hoehenmesser kann dieses Skript nicht fliegen.')
            print('  Deck sauber aufstecken, Drohne aus und wieder an.')
            print('')
            return

        if fehlen:
            print('')
            print('  Kein Multi-Ranger erkannt (es fehlen: %s).'
                  % ', '.join(n.split('.')[1] for n in fehlen))
            print('  Wand- und Deckenschutz sind damit AUS - die Drohne')
            print('  bremst vor nichts. Du fliegst komplett auf Sicht.')
            print('')
            SCHUTZ_AN = False
            DECKE_AN = False

        log = LogConfig(name='Flug', period_in_ms=250)
        log.add_variable('pm.vbat', 'float')
        for v in vorhanden:
            log.add_variable(v, 'uint16_t')
        cf.log.add_config(log)
        log.data_received_cb.add_callback(telemetrie)
        log.start()

        def funk_weg(uri, meldung):
            funk['weg'] = True
            print('\n\n  !!! FUNKVERBINDUNG VERLOREN !!!')
            print('  ' + str(meldung))
            print('  Die Drohne schaltet dabei die Motoren ab.')
            print('  Funkstick freier platzieren (USB-Verlaengerung),')
            print('  naeher an die Flugzone, nicht mit dem Koerper abschatten.')

        cf.connection_lost.add_callback(funk_weg)

        pose_log = None
        datei = schreiber = None
        dateiname = ''
        if aufnahme:
            pose_log = LogConfig(name='Pose', period_in_ms=200)
            for v in ['kalman.stateX', 'kalman.stateY', 'kalman.stateZ',
                      'stabilizer.yaw']:
                pose_log.add_variable(v, 'float')
            cf.log.add_config(pose_log)
            pose_log.data_received_cb.add_callback(pose_empfangen)
            pose_log.start()
            datei, schreiber, dateiname = aufzeichnung_starten()
            print('  AUFZEICHNUNG laeuft -> ' + dateiname)

        time.sleep(0.8)

        # Akkulage vor dem Start ehrlich benennen. Ein halbvoller Akku
        # sieht wie ein Steuerungsproblem aus: sie haelt die Hoehe nicht,
        # sackt weg und schiesst dann ueber.
        volt = d['vbat']
        print('')
        if volt <= 0:
            print('Akku: kein Messwert.')
        elif volt < 3.75:
            print('Akku %.2f V   ZU LEER' % volt)
            print('  Sie hebt wahrscheinlich nicht ab. Erst laden')
            print('  (rund 30 Minuten von leer auf voll).')
        elif volt < AKKU_EMPFOHLEN:
            print('Akku %.2f V   SCHWACH  (voll waeren 4.2 V)' % volt)
            print('  Sie fliegt, haelt die Hoehe aber schlecht - die')
            print('  Motoren haben keine Reserve mehr. Sieht aus wie ein')
            print('  Steuerungsproblem, ist aber der Akku.')
            print('  Fuer einen Vergleichsflug lieber erst laden.')
        else:
            print('Akku %.2f V   gut' % volt)
        print('')

        print('')
        print('  A = starten    B = landen    START = NOT-AUS')
        print('  Y = naechste Einstellung     X = vorherige')
        print('  LB halten = Schleichgang')
        print('')
        print('  FIGUREN auf dem Steuerkreuz (nur im Flug):')
        print('    links  Kreis        rechts  liegende Acht')
        print('    hoch   Spirale      runter  Auf und Ab')
        print('    Stick bewegen bricht jede Figur sofort ab.')
        print('    Platzbedarf rundum: Kreis %.2f  Acht %.2f  '
              'Spirale %.2f  Auf-Ab %.2f m'
              % (FIGUR_PLATZ['kreis'], FIGUR_PLATZ['acht'],
                 FIGUR_PLATZ['spirale'], FIGUR_PLATZ['aufab']))
        print('')
        print('  RB halten + Steuerkreuz = Trimmung')
        print('')
        print('  FLUGMODUS: %s   (BACK wechselt, auch im Flug)' % modus[0])
        print('    SCHWEBEN   Stick = Tempo. Loslassen -> sie bleibt stehen')
        print('    SPORTLICH  Stick = Neigung (max %.0f Grad). Direkter,'
              % MAX_NEIGUNG)
        print('               aber sie gleitet beim Loslassen aus')
        print('')
        print('  Wandschutz          %s' % ('an' if SCHUTZ_AN else 'AUS'))
        print('  Deckenbremse        %s' % ('an' if DECKE_AN else 'AUS'))
        print('  Boden-Sprung-Ausgl. %s%s'
              % ('an' if BODEN_SPRUNG_AUS else 'AUS',
                 '   (ab %.2f m Sprung, dann %.1f s Ruhe)'
                 % (BODEN_SPRUNG_SCHWELLE, BODEN_SPERRE)
                 if BODEN_SPRUNG_AUS
                 else '   (sie schiesst ueber Moebeln hoch)'))
        if not (SCHUTZ_AN and DECKE_AN):
            print('')
            print('  Du fliegst ohne Netz. Sie bremst nicht mehr vor')
            print('  Waenden%s - du bist allein zustaendig.'
                  % ('' if DECKE_AN else ' und Decke'))
        print('')

        fliegt = False
        hoehe = START_HOEHE
        frei = True
        frei_stufe = True
        frei_modus = True
        letzte = 0.0
        letzte_aufnahme = 0.0
        beginn = time.time()
        zeilen = 0

        try:
            while True:
                pygame.event.pump()
                a = knopf(pad, 'start')
                b = knopf(pad, 'landen')

                if knopf(pad, 'notaus'):
                    cf.commander.send_stop_setpoint()
                    arm(cf, False)
                    print('\nNOT-AUS')
                    break

                # Einstellung wechseln - geht am Boden und im Flug
                weiter = knopf(pad, 'weiter')
                zurueck = knopf(pad, 'zurueck')
                if (weiter or zurueck) and frei_stufe:
                    frei_stufe = False
                    stufe[0] = (stufe[0] + (1 if weiter else -1)) % len(STUFEN)
                    print('\n  >>> Einstellung %d: %s'
                          % (stufe[0] + 1, STUFEN[stufe[0]]['name']))
                if not weiter and not zurueck:
                    frei_stufe = True

                # BACK = Flugmodus wechseln, am Boden und im Flug
                if knopf(pad, 'modus'):
                    if frei_modus:
                        frei_modus = False
                        modus[0] = (MODUS_SPORT if modus[0] == MODUS_SCHWEBEN
                                    else MODUS_SCHWEBEN)
                        for k in glatt:
                            glatt[k] = 0.0
                        print('\n  >>> Flugmodus: %s%s'
                              % (modus[0],
                                 '   (Stick = Neigung, sie gleitet aus)'
                                 if modus[0] == MODUS_SPORT
                                 else '   (Stick = Tempo, sie bleibt stehen)'))
                else:
                    frei_modus = True

                if a and not fliegt and frei:
                    frei = False
                    print('\nStarte ... (nicht anfassen)')
                    start_vorbereiten(cf, pad)
                    hoehe = START_HOEHE
                    hochfahren(cf, pad, hoehe)
                    fliegt = True
                    print('In der Luft.')

                if b and fliegt and frei:
                    frei = False
                    print('\nLande ...')
                    runterfahren(cf, pad, hoehe)
                    fliegt = False
                    for k in glatt:
                        glatt[k] = 0.0
                    print('Gelandet. A zum Neustart.')

                if not a and not b:
                    frei = True

                if trimmen(pad, frei):
                    frei = False
                    print('\n  Trimmung: vor %+.2f   seitwaerts %+.2f'
                          % (trimm['vor'], trimm['seit']))
                    time.sleep(0.15)

                # Steuerkreuz ohne RB = Flugfigur, nur im Flug
                elif fliegt and frei and pad.get_numhats() > 0 \
                        and not knopf(pad, 'trimm'):
                    hx, hy = pad.get_hat(0)
                    welche = None
                    if hy > 0:
                        welche = 'spirale'
                    elif hy < 0:
                        welche = 'aufab'
                    elif hx < 0:
                        welche = 'kreis'
                    elif hx > 0:
                        welche = 'acht'
                    if welche:
                        frei = False
                        hoehe = figur_fliegen(cf, pad, welche, hoehe)
                        for k in glatt:
                            glatt[k] = 0.0
                        letzte = 0.0

                if fliegt:
                    mittel = akku_mittel()
                    if (0 < mittel < AKKU_NOTLANDUNG
                            and len(verlauf) >= AKKU_FENSTER):
                        print('\n  AKKU LEER (%.2f V im Mittel) - '
                              'automatische Landung' % mittel)
                        runterfahren(cf, pad, hoehe)
                        fliegt = False
                        continue

                    tempo = MAX_SPEED
                    schleich = knopf(pad, 'langsam')
                    if schleich:
                        tempo *= LANGSAM_FAKTOR

                    dreh = glaetten('dreh', stick(pad, 'drehen') * MAX_YAW)
                    steig = stick(pad, 'hoehe') * STEIG_RATE
                    seit = glaetten('seit', stick(pad, 'seit') * tempo)
                    vor = glaetten('vor', stick(pad, 'vor') * tempo)

                    # erst den Untergrund-Sprung ausgleichen, dann die Decke
                    hoehe, boden_hinweis = boden_sprung_ausgleichen(hoehe)
                    hoehe, decke_hinweis = decke_begrenzen(hoehe, steig)

                    vor += trimm['vor']
                    seit += trimm['seit']
                    vor, seit, warnung = schutz(vor, seit)
                    warnung += decke_hinweis + boden_hinweis

                    if modus[0] == MODUS_SPORT:
                        # Sportlich: dieselben Stickwerte, aber als
                        # Neigungswinkel statt als Geschwindigkeit.
                        # vor/seit stehen hier in m/s und werden auf den
                        # Winkelbereich umgerechnet - der Kollisions-
                        # schutz hat sie vorher schon gedrosselt, das
                        # wirkt dadurch genauso.
                        anteil_vor = vor / MAX_SPEED if MAX_SPEED else 0.0
                        anteil_seit = seit / MAX_SPEED if MAX_SPEED else 0.0
                        pitch = max(-1.0, min(1.0, anteil_vor)) * MAX_NEIGUNG
                        roll = max(-1.0, min(1.0, anteil_seit)) * MAX_NEIGUNG
                        # Vorzeichen wie bei hover: seit > 0 heisst links
                        cf.commander.send_zdistance_setpoint(
                            -roll, pitch, dreh, hoehe)
                    else:
                        cf.commander.send_hover_setpoint(vor, seit, dreh,
                                                         hoehe)

                    if (aufnahme
                            and time.time() - letzte_aufnahme > AUFZEICHNUNG_TAKT):
                        aufzeichnen(schreiber, beginn)
                        zeilen += 1
                        letzte_aufnahme = time.time()

                    jetzt = time.time()
                    if jetzt - letzte > 0.5:
                        boden = d['zrange'] if d['zrange'] is not None else 0
                        zusatz = ''
                        if aufnahme:
                            zusatz += '  [REC %d]' % zeilen
                        if schleich:
                            zusatz += '  [langsam]'
                        if trimm['vor'] or trimm['seit']:
                            zusatz += '  Trimm %+.2f/%+.2f' % (trimm['vor'],
                                                               trimm['seit'])
                        oben = abstand('up')
                        zur_decke = ('%.2f m' % oben) if oben else ' --- '
                        zeile = ('  [%d %s|%s]  Soll %.2f m  Ist %.2f m  '
                                 'Decke %s   vor %+.2f  seit %+.2f  '
                                 'dreh %+3.0f   Akku %.2f V%s%s'
                                 % (stufe[0] + 1, STUFEN[stufe[0]]['name'],
                                    modus[0][:5],
                                    hoehe, boden, zur_decke, vor, seit, dreh,
                                    akku_mittel(), zusatz, warnung))
                        print('\r' + zeile.ljust(130)[:130], end='')
                        letzte = jetzt

                time.sleep(TAKT)

        except NotAus:
            # Kommt aus warten() - also aus einer Startsequenz oder einem
            # Funkabriss. Motoren mehrfach stoppen, damit es ankommt.
            for _ in range(5):
                try:
                    cf.commander.send_stop_setpoint()
                except Exception:
                    pass
                time.sleep(0.02)
            arm(cf, False)
            print('\nNOT-AUS' + ('  (Funk weg)' if funk['weg'] else ''))

        except KeyboardInterrupt:
            cf.commander.send_stop_setpoint()
            arm(cf, False)
            print('\nAbbruch.')

        for l in [log, pose_log]:
            try:
                if l:
                    l.stop()
                    l.delete()
            except Exception:
                pass

        if datei:
            datei.close()
            print('\n\nAufzeichnung beendet: %d Messpunkte in %s'
                  % (zeilen, dateiname))

    print('')
    print('=' * 60)
    print('Zuletzt geflogen: Einstellung %d - %s'
          % (stufe[0] + 1, STUFEN[stufe[0]]['name']))
    if paket_speichern():
        print('In %s gespeichert.' % PAKET_DATEI)
    print('')
    print('War das die beste? Falls nicht, sag mir einfach die Nummer,')
    print('die sich am besten angefuehlt hat - oder was noch stoert.')
    print('=' * 60)


if __name__ == '__main__':
    try:
        main()
    except Exception as fehler:
        print('\nFehler: ' + str(fehler))
        sys.exit(1)
