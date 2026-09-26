#!/usr/bin/env python3
"""
race_indoor.py  --  Schnell fliegen im Zimmer, mit Wende auf Knopfdruck
=======================================================================
Version 1.0 vom 15.09.2026 (Final). Die unfertige Fassung von 02:22 Uhr
liegt unverändert als race_indoor_SICHERUNG_2026-09-15_140917.py daneben.
Die Schutzfunktionen stammen aus flow_ranger_recorder.py 3.2, das am
14.09.2026 echt geflogen ist.

Was es tut
----------
Du fliegst mit dem Xbox-Controller, schneller und direkter als mit dem
Recorder. Y dreht sie auf der Stelle um 180 Grad (Wende). Vor Wänden
bremst sie selbst ab. Alles wird mitgeschrieben.

Voraussetzungen
---------------
  Hardware   Crazyflie 2.1 mit Flow Deck v2 und Multi-Ranger Deck,
             Crazyradio, Xbox-Controller (Pflicht)
  Akku       350 mAh, voll geladen. Er hat keine Schutzschaltung, darf
             also nie unter 3,0 V unter Last. Deshalb gibt es hier keinen
             Modus ohne Akkuprüfung.
  Software   Python 3.12 mit cflib und pygame
  Vorher     cfclient schließen, sonst ist der Funkstick belegt

Start
-----
  python race_indoor.py

Tasten (Belegung wie in der alten race_indoor.py)
------
  linker Stick      vor/zurück und seitlich
  rechter Stick     drehen (links/rechts)
  Steuerkreuz       hoch/runter, gedrückt halten
  Y                 Wende um 180 Grad. Richtung: wie der rechte Stick
                    gerade steht, sonst links herum. Während der Wende
                    bleibt sie auf der Stelle stehen.
  X, B oder START   landen
  START nochmal     während der Landung: Motoren sofort aus (Not-Aus)
  Strg+C            landen, ein zweites Strg+C: Motoren aus

Schutz im Flug
--------------
Maßgeblich sind die Werte unter KONFIGURATION.
  Hindernis      ab 1,27 m gebremst (wird aus MAX_SPEED gerechnet und beim
                 Start angezeigt), bei 22 cm steht sie, unter 5 cm
                 Notlandung. Wegfliegen geht immer. Bremst sie, gehen alle
                 LEDs an (Bremslicht).
  Decke          weniger als 30 cm frei: sie sinkt
  Möbel          springt die Höhe in einem Takt um mehr als 25 cm, war es
                 eine Kante, und das Möbel wird herausgerechnet
  Steigen        Ziel höchstens 15 cm über der gemessenen Höhe
  Höhe verloren  unter 10 cm, obwohl sie höher soll: die Fahrt stoppt
  Akku           2 s unter 3,40 V unter Last: Warnung,
                 2 s unter 3,20 V unter Last: Landung
  Funk, Sensoren Funk weg oder 0,5 s keine Sensordaten: Notlandung
  Controller     abgezogen oder Funk zum Controller weg: Landung
  Höhenbereich   0,17 bis 1,70 m, Start auf 0,55 m
  Landung        mit 0,2 m/s, Notlandung mit 0,5 m/s
Egal was passiert (Strg+C, Programmfehler, Controller weg), sie landet.
Die Motoren gehen nie mitten in der Luft aus, außer beim Not-Aus.

Log und Parameter, Schritt für Schritt
--------------------------------------
  1. Verbinden: SyncCrazyflie baut die Verbindung auf und holt die Listen
     aller Log-Variablen und Parameter von der Drohne (der Ordner 'cache'
     neben dem Skript spart das beim nächsten Mal).
  2. Parameter lesen: deck.bcFlow2 und deck.bcMultiranger stehen auf 1,
     wenn die Firmware das Deck erkannt hat. Fehlt eins, startet sie nicht.
  3. Drei Logs anmelden. Ein Log-Paket fasst höchstens 26 Byte, deshalb
     sind es drei:
       RaceSensoren  alle 20 ms: sechs Abstände in mm (je 2 Byte),
                     Akku und Höhe (je 4 Byte)                  = 20 Byte
       RacePosition  alle 50 ms: x, y und Richtung (je 4 Byte)  = 12 Byte
       RaceGas       alle 100 ms: vier Motoren (je 2 Byte) und
                     der Schub-Sollwert (4 Byte)                = 12 Byte
     Danach schickt die Drohne die Werte von selbst. cflib ruft für jedes
     Paket eine Funktion auf (_empfangen, _pos_empfangen, _gas_empfangen),
     die die Werte hier ablegt. Die Flugschleife liest nur noch ab.
  4. Parameter schreiben: kalman.resetEstimation erst 1, dann 0 setzt die
     Positionsschätzung vor dem Start auf null. led.bitmask schaltet das
     Bremslicht: 255 heißt "alle LEDs an", 0 gibt die LEDs an die Firmware
     zurück. Geschrieben wird nur beim Wechsel, nicht dauernd.
  5. Fliegen: 20-mal pro Sekunde send_hover_setpoint(vx, vy, gier, z).
     vx vorwärts und vy nach links in m/s, gier in Grad/s (positiv = links
     herum), z = Höhe in m. Kommt 0,5 s kein Befehl, hält die Firmware sie
     nur noch waagerecht, nach 2 s schaltet sie die Motoren ab
     (supervisor.c). Deshalb sendet das Skript ohne Pause, auch beim
     Abheben und Landen.

Dateien (neben diesem Skript)
-----------------------------
  race_indoor_<Zeit>.txt    alles, was auf dem Bildschirm stand
  race_indoor_<Zeit>.csv    20 Zeilen pro Sekunde: Befehle, Abstände, Akku,
                            Position, Motoren

Aufbau dieser Datei
-------------------
  KONFIGURATION   alle Zahlen zum Einstellen, nach Themen
  HELFER          sag(), Umrechnungen, Takt
  DIE DROHNE      Klasse RaceDrohne: Log-Empfang, Messwerte, Schutz,
                  Controller, Wende, Bremslicht, Motoren, Vorbereitung,
                  Flug
  ABLAUF          fliegen(), Zusammenfassung, main()

Was gegenüber der Fassung von 02:22 Uhr neu ist
-----------------------------------------------
 1. Die Datei war nach Zeile 235 abgeschnitten (SyntaxError), die ganze
    Flugschleife fehlte.
 2. Start: Ein einziger Befehl und dann 2 s Pause lag genau an der Grenze,
    ab der die Firmware die Motoren abschaltet. Jetzt steigt sie mit
    20 Befehlen pro Sekunde auf die Starthöhe.
 3. Wende: Y wurde nie zurückgesetzt, sie hätte endlos gewendet. Jetzt
    gibt ein Druck genau eine Wende. Sie wird weich geregelt (langsamer
    kurz vor dem Ziel, kein Überschießen), hat eine Zeitgrenze, und der
    wirklich erreichte Winkel wird gemeldet.
 4. Wand: Statt Motoren aus (Absturz aus bis zu 1,8 m) bremst sie ab und
    bleibt stehen. Nur unter 5 cm landet sie, und zwar mit Sinken.
 5. Controller weg, Funk weg, Sensoren blind, Akku leer, Strg+C,
    Programmfehler: Sie landet. Vorher froren die Stick-Werte ein.
 6. Vor dem Start: Decks da? Akku voll genug? Sticks in der Mitte? Platz
    drumherum? Danach Kalman-Reset.
 7. Decke und Möbel wie in flow_ranger_recorder.py 3.2.
 8. pygame statt inputs, wie in allen anderen Flugskripten. Die Ruhelage
    der Sticks wird vor dem Start gemessen.
 9. Bremslicht nur beim Wechsel statt 25 Parameter pro Sekunde, und am
    Ende sicher aus.
10. Bericht und CSV neben dem Skript.
11. Funkadresse: erst die aus allen anderen Skripten, klappt das nicht,
    die aus der alten race_indoor.py. Mit der Umgebungsvariable
    CFLIB_URI gilt nur die dort eingetragene.
"""
import os

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
# Controller auch dann lesen, wenn das Konsolenfenster nicht vorne ist
os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')

import csv
import math
import sys
import time
import traceback
from datetime import datetime

import cflib.crtp
import pygame
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils import uri_helper

# =============================================================================
# KONFIGURATION
# =============================================================================
# ----------------------------------------------------------- Verbindung, Takt
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')
# Die alte race_indoor.py und race.py funkten auf einer anderen Adresse als
# alle anderen Skripte. Kommt über URI keine Verbindung zustande, wird die
# alte probiert. Ist CFLIB_URI gesetzt, gilt nur diese.
URI_ALT = 'radio://0/80/2M'
URIS = [URI] if os.environ.get('CFLIB_URI') else [URI, URI_ALT]
HIER = os.path.dirname(os.path.abspath(__file__))
VERSION = '1.0'

HZ_RATE = 20                # Befehle und CSV-Zeilen pro Sekunde
TAKT = 1.0 / HZ_RATE

# ----------------------------------------------------------- Steuerung
# Profil "Indoor Racing, Stick wird gern durchgedrückt" (16.09.2026).
# Bei Vollausschlag greift RAMPE nicht: Die Drohne beschleunigt höchstens mit
# 3,57 m/s² (Neigung 20 Grad). RAMPE 0.32 fordert mehr, sobald der Stick aus
# der Ruhe auf über 0,56 m/s springt - mit den Werten unten ab 76 % Stickweg.
# Wirksam sind deshalb EXPO, DEADZONE und MAX_SPEED.
DEADZONE = 0.16             # Stick kommt nach hartem Loslassen nicht genau
                            # in die Mitte zurück
EXPO = 2.00                 # 1 = linear, größer = feiner um die Mitte. Voll-
                            # ausschlag bleibt MAX_SPEED, halber Stick 0,18 m/s
RAMPE = 0.32                # Anteil pro Takt, mit dem der Stick nachgeführt wird
MAX_SPEED = 1.10            # m/s. Obergrenze fürs Zimmer: quer 2,70 m, zwei
                            # Bremszonen brauchen bei 1,10 m/s 2,54 m. 1,15
                            # bräuchte schon 2,72 m.
MAX_YAW = 140.0             # Grad/s mit dem Stick. Für 180 Grad gibt es Y.
STEIG_RATE = 0.40           # m/s mit gedrücktem Steuerkreuz

# ----------------------------------------------------------- Wende (Taste Y)
WENDE_WINKEL = 180.0        # Grad
WENDE_K = 5.0               # 1/s: noch 20 Grad übrig ergibt 100 Grad/s
WENDE_MAX = 180.0           # Grad/s, schneller dreht sie nicht. Bewusst
                            # höher als MAX_YAW: die Wende regelt selbst.
WENDE_MIN = 30.0            # Grad/s, damit sie am Ende nicht stehen bleibt
WENDE_ANSTIEG = 60.0        # Grad/s, um so viel steigt die Gierrate je Takt.
                            # Ohne das springt sie beim Druck auf Y in einem
                            # einzigen Takt von 0 auf WENDE_MAX.
WENDE_FERTIG = 4.0          # Grad vor dem Ziel: Wende fertig
WENDE_ZEIT = 2.5            # s, länger: Wende abbrechen (und melden)
WENDE_NACHLAUF = 0.4        # s nach der Wende: erst dann Winkel melden,
                            # weil sie noch etwas nachdreht

# ----------------------------------------------------------- Höhe
START_HOEHE = 0.55          # m. Flow-Deck misst höchstens 7,4 rad/s
                            # (PMW3901-Datenblatt), also v = 7,4 * Höhe.
                            # Mit Faktor 2 Reserve: 0,40 m -> 1,48 m/s,
                            # 0,55 m -> 2,04 m/s. Sackt sie beim harten
                            # Bremsen ab, reicht es trotzdem.
MIN_HOEHE = 0.17            # m
MAX_HOEHE = 1.70            # m (Decke 2,36 m)
DECKEN_ABSTAND = 0.30       # m, weniger frei nach oben: sinken
SPRUNG = 0.25               # m in einem Takt: Möbelkante unter ihr
VORLAUF = 0.15              # m, beim Steigen höchstens so weit über der Messung
HOEHE_VERLOREN = 0.10       # m, darunter obwohl sie höher soll: Fahrt stoppen

# ----------------------------------------------------------- Hindernisse
NOT_STOPP_ABSTAND = 0.05    # m, darunter: Notlandung
HALTE_ABSTAND = 0.22        # m, hier steht sie (Luft bis zur Notlandung).
                            # War 0,15. Mehr Puffer, weil beim Racing später
                            # gegengesteuert wird.

# BREMS_ABSTAND wird gerechnet, nicht eingetragen. bremsen() drosselt linear
# über der Strecke, also v = k * (Abstand - HALTE_ABSTAND). Daraus folgt eine
# nötige Verzögerung von v² / Bremszone: bei doppeltem Tempo braucht sie die
# VIERFACHE Zone, nicht die doppelte. Eine feste Zahl passt deshalb immer nur
# zu genau einem MAX_SPEED - wird MAX_SPEED geändert und die Zahl nicht, ist
# der Bremsweg zu kurz. Jetzt folgt sie von selbst.
TOT_ZEIT = 0.15             # s, bis eine Drosselung wirkt: Ranger messen mit
                            # 10 Hz, die Schleife läuft mit 20 Hz, dazu Funk.
                            # So weit fliegt sie ungebremst weiter.
BREMS_VERZOEG = 1.37        # m/s², so stark darf gebremst werden. Nicht
                            # geschätzt: zurückgerechnet aus dem geflogenen
                            # Fixpunkt 1,10 m/s mit 1,20 m Bremsabstand. Die
                            # Firmware ließe 3,57 zu (Neigung auf 20 Grad
                            # begrenzt), der Rest ist Sicherheitsabstand.
                            # Quelle: crazyflie-firmware,
                            # platform_defaults_cf2.h (PID_VEL_ROLL_MAX 20)
                            # und position_controller_pid.c (constrain rLimit)
BREMS_ABSTAND = round(HALTE_ABSTAND + MAX_SPEED * TOT_ZEIT
                      + MAX_SPEED ** 2 / BREMS_VERZOEG, 2)
ENG_FOLGE = 1               # so viele VERSCHIEDENE Messungen unter
                            # NOT_STOPP_ABSTAND: Notlandung
ENG_ZEIT = 0.12             # s unter NOT_STOPP_ABSTAND (Drohnenzeit): auch
                            # Notlandung. Eine Messung steht höchstens 0,10 s
                            # da, ab 0,12 s sind es zwei Messungen.

# ----------------------------------------------------------- Abstandsfilter
SENSOR_MIN = 0.03           # m, kleinere Werte: "ganz nah" oder Ausreißer
NAH_GRENZE = 0.30           # m, war der letzte Wert darunter, war etwas nah
HALTEN_MAX = 1.0            # s, so lange wird ein naher Wert höchstens gehalten
DATEN_ALT = 0.5             # s, älter = Sensoren blind
POS_ALT = 0.5               # s, ältere Richtungsdaten werden nicht benutzt

# ----------------------------------------------------------- Start und Landung
ABHEBE_TEMPO = 0.30         # m/s
SINK_TEMPO = 0.20           # m/s
SINK_TEMPO_NOT = 0.50       # m/s
BODEN = 0.07                # m, darunter gilt sie als gelandet
BODEN_NACHLAUF = 1.5        # s, danach Motoren aus, auch ohne Bodenmessung
COUNTDOWN = 3               # s

# ----------------------------------------------------------- Akku
# 350 mAh ohne Schutzschaltung. Beim Schweben bricht er nur um 0,16 bis
# 0,17 V ein (5 Flüge am 14.09.2026), beim schnellen Fliegen mehr.
# Die Firmware meldet "schwach" erst unter 3,2 V für 5 s.
AKKU_START = 3.80           # V in Ruhe, darunter Rückfrage
AKKU_MINIMUM = 3.60         # V in Ruhe, darunter kein Start
AKKU_KNAPP = 3.40           # V unter Last, 2 s darunter: Warnung
AKKU_LEER = 3.20            # V unter Last, 2 s darunter: landen
AKKU_TAKTE = 40             # so viele Messungen hintereinander (2 s)

# ----------------------------------------------------------- Gas
GAS_KNAPP = 90.0            # %, stärkster Motor beim Schweben: Warnung
GAS_ANSCHLAG = 99.0         # %, ein Motor hier: keine Reserve mehr
MOTOREN = ('motor.m1', 'motor.m2', 'motor.m3', 'motor.m4')

# ----------------------------------------------------------- Bremslicht
LED_BREMSLICHT = True       # False: LEDs bleiben bei der Firmware
LED_ALLE = 255              # led.bitmask: Bit 7 = selbst steuern, 0-6 = LEDs
LICHT_NACHLAUF = 0.3        # s ohne Bremsen, dann geht das Licht aus

# ----------------------------------------------------------- Controller
# Xbox-Controller unter pygame 2.6. Die Achsnummern sind dieselben wie in
# flow_ranger_recorder.py (dort geflogen), nur anders belegt:
#   0 = linker Stick seitlich   1 = linker Stick vor/zurück
#   2 = rechter Stick seitlich  3 = rechter Stick vor/zurück (hier frei)
KNOPF_B = 1
KNOPF_X = 2
KNOPF_Y = 3
KNOPF_START = 7
ACHSEN = {'seit': (0, -1), 'vor': (1, -1), 'drehen': (2, -1)}

# ----------------------------------------------------------- Sensoren
SEITEN = [('range.front', 'vorne'), ('range.back', 'hinten'),
          ('range.left', 'links'), ('range.right', 'rechts')]
ALLE_SENSOREN = SEITEN + [('range.up', 'oben'), ('range.zrange', 'unten')]
GEFILTERT = SEITEN + [('range.up', 'oben')]
POS_VARIABLEN = ('stateEstimate.x', 'stateEstimate.y', 'stateEstimate.yaw')

# ----------------------------------------------------------- CSV
# Abstände ROH (leer nur bei 8 m und mehr), damit man den Filter
# hinterher nachprüfen kann. z_soll_m ist die Höhe über dem Fußboden,
# z_gesendet_m das, was wirklich gesendet wurde (mit Möbel, Decke, Vorlauf).
CSV_KOPF = ['t_s', 'vx_ms', 'vy_ms', 'gier_grad_s', 'z_soll_m', 'z_ist_m',
            'vbat_v', 'vorne_m', 'hinten_m', 'links_m', 'rechts_m', 'oben_m',
            'unten_m', 'gebremst', 'wende', 'x_m', 'y_m', 'gier_ist_grad',
            'z_gesendet_m', 'moebel_m', 'm1_prozent', 'm2_prozent',
            'm3_prozent', 'm4_prozent', 'schub_prozent']


# =============================================================================
# HELFER
# =============================================================================
_zeilen = []


def sag(text=''):
    """Druckt auf den Bildschirm und merkt sich die Zeile für die Datei."""
    print(text, flush=True)
    _zeilen.append(text)


def zahl(wert, form='%.2f'):
    return '-' if wert is None else form % wert


def begrenzt(wert, grenze):
    return max(-grenze, min(grenze, wert))


def wrap(winkel):
    """Winkel in Grad auf -180 .. +180, damit 350 Grad als -10 zählt."""
    return ((winkel + 180.0) % 360.0) - 180.0


def roh_m(mm):
    """Rohwert des Multi-Rangers in m, None ab 8 m (32767 = nichts oder
    ungültig)."""
    if mm is None or mm >= 8000:
        return None
    return mm / 1000.0


def median(werte):
    """Mittlerer Wert, None bei leerer Liste."""
    werte = sorted(werte)
    return werte[len(werte) // 2] if werte else None


def arm(cf, an):
    """Wie in 30_fliegen.py. Die Firmware 2026.08 armt selbst, das hier
    schadet aber nicht. Der Armingstatus wird NIE als Startbedingung
    geprüft."""
    try:
        cf.supervisor.send_arming_request(an)
    except Exception:
        try:
            cf.platform.send_arming_request(an)
        except Exception:
            pass


class Abbruch(Exception):
    """Vor dem Abheben abgebrochen. Die Motoren liefen noch nicht."""


class Takt:
    """Hält die Schleife auf 20 Hz, ohne dass sich Verzögerungen addieren."""

    def __init__(self):
        self.naechster = time.time()

    def warte(self):
        self.naechster += TAKT
        rest = self.naechster - time.time()
        if rest > 0:
            time.sleep(rest)
        else:
            self.naechster = time.time()


# =============================================================================
# DIE DROHNE
# =============================================================================
class RaceDrohne:
    """Alles, was die Drohne betrifft: Messwerte, Schutz, Controller,
    Wende, Bremslicht, Start und Landung."""

    def __init__(self, pad):
        self.pad = pad
        self.cf = None
        self.lg = self.lg_pos = self.lg_gas = None
        # Messwerte aus den Logs
        self.d = {}                 # letztes Sensor-Log, Rohwerte
        self.d_zeit = 0.0           # wann es ankam (Zeit am PC)
        self.d_fw = 0.0             # wann es gemessen wurde (Drohnenzeit, s)
        self.roh = {}
        self.gef = {}               # gefilterte Abstände in m
        self.gef_zeit = {}
        self.nah = {name: 0 for name, _ in SEITEN}
        self.nah_seit = {name: None for name, _ in SEITEN}
        self.nah_wert = {name: None for name, _ in SEITEN}
        self.pos = None             # (x, y, Richtung)
        self.pos_zeit = 0.0
        self.gas = {}
        self.gas_zeit = 0.0
        self.funk_weg = False
        # Akku
        self.akku_leer = 0
        self.akku_knapp = 0
        self.akku_gewarnt = False
        self.akku_anfang = None
        self.akku_tief = None
        # Möbel unter ihr
        self.z_vorher = None
        self.sprung_summe = 0.0
        self.moebel_gemeldet = 0.0
        # Flug
        self.in_luft = False
        self.z_soll = 0.0           # Höhe über dem Fußboden
        self.z_gesendet = 0.0
        self.hoehe_weg = False
        self.nullpunkt = {}
        self.glatt = {'vor': 0.0, 'seit': 0.0, 'dreh': 0.0, 'hoch': 0.0}
        # Wende
        self.wende = None           # läuft gerade
        self.wende_nach = None      # fertig, Winkel wird noch gemessen
        # Bremslicht
        self.licht_an = False
        self.licht_geht = LED_BREMSLICHT
        self.licht_aus_ab = None
        # Zusammenfassung
        self.akku_schweben = []
        self.gas_schweben = []      # (Mittel, stärkster) in den ersten 2 s
        self.gas_gemeldet = False
        self.stat = {'takte': 0, 'gebremst': 0, 'decke': 0, 'vorlauf': 0,
                     'gas_max': None, 'gas_anschlag': 0, 'hoehe_weg': 0,
                     'moebel_max': 0.0, 'z_max': None, 'wenden': [],
                     'min': {name: None for name, _ in SEITEN},
                     'dauer': 0.0}

    # =========================================================================
    # Log-Empfang (läuft im Thread der cflib)
    # =========================================================================
    def _empfangen(self, zeitstempel, daten, konf):
        """Erstes Log: Abstände, Akku, Höhe. Kommt 50-mal pro Sekunde."""
        jetzt = time.time()
        # Die Zeit der Drohne selbst (ms): Funklöcher und verspätete Pakete
        # verschieben sie nicht, anders als die Zeit am PC.
        fw = zeitstempel / 1000.0
        for name, _ in GEFILTERT:
            mm = daten.get(name)
            if mm is not None:
                self._abstand_neu(name, mm, jetzt, fw)
        self.d.update(daten)
        self.d_zeit = jetzt
        self.d_fw = fw
        self._moebelkante(daten.get('stateEstimate.z'))
        self._akku_zaehlen(daten.get('pm.vbat'))

    def _abstand_neu(self, name, mm, jetzt, fw):
        """Filtert einen Abstand und zählt, wie lange er zu nah ist."""
        neu = mm != self.roh.get(name)
        self.roh[name] = mm
        m, gehalten = self._filtern(name, mm, jetzt)
        self.gef[name] = m
        if not gehalten:
            self.gef_zeit[name] = jetzt
        if name == 'range.up':
            return
        # Ein einzelner Wert unter NOT_STOPP_ABSTAND ist kein Befund. Die
        # Sensoren messen mit 10 Hz, das Log kommt öfter: Jede Messung
        # steht mehrmals da. Deshalb zählen nur NEUE Rohwerte. Bleibt der
        # Wert gleich (oder wird gehalten), greift die Zeit.
        if m is not None and m < NOT_STOPP_ABSTAND:
            seit = self.nah_seit[name]
            if seit is None or fw < seit:   # fw < seit: Zähler übergelaufen
                self.nah_seit[name] = fw
            if neu and not gehalten:
                self.nah[name] += 1
            self.nah_wert[name] = m
        else:
            self.nah[name] = 0
            self.nah_seit[name] = None

    def _filtern(self, name, mm, jetzt):
        """Gibt (Abstand in m oder None, gehalten) zurück.

        Der Multi-Ranger schickt jede ungültige Messung als 32767 mm, auch
        wenn etwas ZU NAH ist. Das sieht aus wie "nichts gesehen". War der
        letzte Wert nah, wird er deshalb gehalten, höchstens HALTEN_MAX.
        Werte unter 3 cm sind "ganz nah", wenn vorher etwas nah war (oder
        noch nie etwas kam), sonst ein Ausreißer."""
        nie = name not in self.gef
        alt = self.gef.get(name)
        nah = alt is not None and alt < NAH_GRENZE
        frisch = jetzt - self.gef_zeit.get(name, 0.0) < HALTEN_MAX
        if mm >= 8000:
            if nah and frisch:
                return alt, True
            return None, False
        m = mm / 1000.0
        if m < SENSOR_MIN:
            if nie or nah:
                return SENSOR_MIN, False
            if frisch:
                return alt, True
            return SENSOR_MIN, False    # bleibt es dabei, ist es echt
        return m, False

    def _moebelkante(self, z):
        """Die Höhe bezieht sich auf die Fläche direkt unter ihr. Springt
        sie in einem Takt um mehr als SPRUNG, war das kein Flug, sondern
        eine Kante. Aufsummieren, damit hin und zurück sich aufhebt."""
        if z is None:
            return
        if (self.in_luft and self.z_vorher is not None
                and abs(z - self.z_vorher) > SPRUNG):
            self.sprung_summe += z - self.z_vorher
        self.z_vorher = z

    def _akku_zaehlen(self, v):
        """Tiefster Wert im Flug, und wie lange schon unter den Grenzen."""
        gueltig = v is not None and v > 0.5
        if self.in_luft and gueltig:
            if self.akku_tief is None or v < self.akku_tief:
                self.akku_tief = v
        self.akku_leer = self.akku_leer + 1 if gueltig and v < AKKU_LEER else 0
        self.akku_knapp = (self.akku_knapp + 1
                           if self.in_luft and gueltig and v < AKKU_KNAPP
                           else 0)

    def _pos_empfangen(self, zeitstempel, daten, konf):
        """Zweites Log: Position und Richtung, die Wende braucht sie."""
        try:
            self.pos = (daten['stateEstimate.x'], daten['stateEstimate.y'],
                        daten['stateEstimate.yaw'])
            self.pos_zeit = time.time()
        except KeyError:
            pass

    def _gas_empfangen(self, zeitstempel, daten, konf):
        """Drittes Log: Gas der vier Motoren und Schub-Sollwert."""
        self.gas = {name: 100.0 * wert / 65535.0
                    for name, wert in daten.items() if wert is not None}
        self.gas_zeit = time.time()

    def _funk_weg(self, uri, meldung):
        self.funk_weg = True
        print('\n  !!! FUNKVERBINDUNG VERLOREN: %s' % meldung, flush=True)

    # =========================================================================
    # Messwerte abfragen
    # =========================================================================
    def abstand(self, name):
        """Gefilterter Abstand in m, oder None bei 'nichts gesehen'."""
        return self.gef.get(name)

    def unten(self):
        return roh_m(self.d.get('range.zrange'))

    def position(self):
        """(x, y, Richtung) oder None, wenn die Daten fehlen oder zu alt
        sind."""
        if self.pos is None or time.time() - self.pos_zeit > POS_ALT:
            return None
        return self.pos

    def motoren(self):
        """(Mittel, stärkster Motor) in %, oder None ohne frische Daten."""
        werte = [self.gas[n] for n in MOTOREN if n in self.gas]
        if len(werte) < 4 or time.time() - self.gas_zeit > 0.5:
            return None
        return sum(werte) / 4.0, max(werte)

    def schwebegas(self):
        """(Mittel, stärkster Motor) über die ersten 2 s Schweben."""
        if not self.gas_schweben:
            return None
        n = len(self.gas_schweben)
        return (sum(g[0] for g in self.gas_schweben) / n,
                sum(g[1] for g in self.gas_schweben) / n)

    def versatz(self):
        """Wie viel die Fläche unter ihr höher liegt als der Fußboden beim
        Start, negativ gezählt. Nur Möbel (nach oben) werden
        herausgerechnet. Geht es tiefer als beim Start, sinkt sie mit,
        das ist die sichere Richtung."""
        return min(0.0, self.sprung_summe)

    def decke_frei(self):
        oben = self.abstand('range.up')
        return oben is None or oben > DECKEN_ABSTAND

    def abstaende_text(self):
        teile = []
        for name, wo in ALLE_SENSOREN:
            m = self.unten() if name == 'range.zrange' else self.abstand(name)
            teile.append('%s %s' % (wo, zahl(m)))
        return '   '.join(teile)

    # =========================================================================
    # Schutz: Gefahr, Bremsen, Höhe
    # =========================================================================
    def gefahr(self):
        """(Grund, schnell) oder None."""
        if self.funk_weg:
            return 'Funkverbindung verloren', True
        alt = time.time() - self.d_zeit
        if alt > DATEN_ALT:
            return 'seit %.1f s keine Sensordaten' % alt, True
        for name, wo in SEITEN:
            seit = self.nah_seit[name]
            # Dauer in Drohnenzeit, damit ein Funkloch nicht als Hindernis
            # zählt und ein verspätetes Paket keine Messung verlängert
            lange = seit is not None and self.d_fw - seit >= ENG_ZEIT
            if self.nah[name] >= ENG_FOLGE or lange:
                return ('Hindernis %s bei %s m'
                        % (wo, zahl(self.nah_wert[name])), True)
        if self.akku_leer >= AKKU_TAKTE:
            return 'Akku leer (%.2f V unter Last)' % self.d.get('pm.vbat',
                                                               0.0), False
        return None

    def bremsen(self, vx, vy):
        """Drosselt nur die Fahrt AUF ein Hindernis zu. Wegfliegen geht
        immer. Zwischen BREMS_ABSTAND und HALTE_ABSTAND fällt die erlaubte
        Geschwindigkeit gleichmäßig von MAX_SPEED auf null.

        Nicht bis NOT_STOPP_ABSTAND bremsen: Dann kriecht sie genau an die
        Grenze der Notlandung heran, und in echt schiebt die Verzögerung
        sie darüber."""
        def grenze(name):
            m = self.abstand(name)
            if m is None or m >= BREMS_ABSTAND:
                return MAX_SPEED
            if m <= HALTE_ABSTAND:
                return 0.0
            return MAX_SPEED * ((m - HALTE_ABSTAND)
                                / (BREMS_ABSTAND - HALTE_ABSTAND))

        if vx > 0:
            vx2 = min(vx, grenze('range.front'))
        else:
            vx2 = max(vx, -grenze('range.back'))
        if vy > 0:                      # positiv = links
            vy2 = min(vy, grenze('range.left'))
        else:
            vy2 = max(vy, -grenze('range.right'))
        return vx2, vy2, (abs(vx2 - vx) > 1e-6 or abs(vy2 - vy) > 1e-6)

    def z_senden(self, z_wunsch, vorlauf=True, boden=MIN_HOEHE):
        """Macht aus der Wunschhöhe über dem Fußboden die Höhe, die
        gesendet wird. Gibt (z_gesendet, grund, versatz) zurück, grund ist
        'decke', 'vorlauf' oder None. Die Mindesthöhe hat Vorrang vor
        allem anderen."""
        versatz = self.versatz()
        z = z_wunsch + versatz
        grund = None
        z_ist = self.d.get('stateEstimate.z')
        oben = self.abstand('range.up')
        if z_ist is not None:
            # Decke: z_ist + oben ist die Decke im selben Bezug wie z.
            if oben is not None:
                deckel = z_ist + oben - DECKEN_ABSTAND
                if z > deckel:
                    z, grund = deckel, 'decke'
            # Vorlauf nur beim Steigen. Hängt sie weit hinterher, wickelt
            # der Höhenregler auf und schießt danach über.
            if (vorlauf and z_wunsch > self.z_soll + 1e-6
                    and z > z_ist + VORLAUF):
                z = z_ist + VORLAUF
                grund = grund or 'vorlauf'
        return max(boden, z), grund, versatz

    # =========================================================================
    # Controller
    # =========================================================================
    def nullpunkt_messen(self):
        """Ruhelage der Sticks, wie in 30_fliegen.py. Der Xbox-Nullpunkt
        springt bei jedem Einschalten des Controllers."""
        sag('  Messe die Ruhelage der Sticks, bitte NICHT anfassen ...')
        proben = {}
        for _ in range(30):
            pygame.event.pump()
            for nr, _r in ACHSEN.values():
                if nr < self.pad.get_numaxes():
                    proben.setdefault(nr, []).append(self.pad.get_axis(nr))
            time.sleep(0.02)
        schief = False
        for nr, werte in proben.items():
            mittel = sum(werte) / len(werte)
            if abs(mittel) > 0.25:
                # Wahrscheinlich angefasst. Diesen Wert NICHT übernehmen,
                # sonst fährt sie beim Loslassen in die Gegenrichtung.
                self.nullpunkt[nr] = 0.0
                schief = True
            else:
                self.nullpunkt[nr] = mittel
        if schief:
            sag('  ACHTUNG: Ein Stick stand weit aus der Mitte und wurde '
                'nicht übernommen.')
        else:
            sag('  Sticks gemessen.')

    def stick(self, name):
        """Stick mit Nullpunkt, Totzone und Expo, -1 .. +1."""
        nr, richtung = ACHSEN[name]
        if nr >= self.pad.get_numaxes():
            return 0.0
        x = (self.pad.get_axis(nr) - self.nullpunkt.get(nr, 0.0)) * richtung
        x = max(-1.0, min(1.0, x))
        if abs(x) < DEADZONE:
            return 0.0
        rest = (abs(x) - DEADZONE) / (1.0 - DEADZONE)
        return math.copysign(rest ** EXPO, x)

    def steuerkreuz(self):
        """Steuerkreuz hoch = +1, runter = -1, sonst 0."""
        if self.pad.get_numhats() < 1:
            return 0.0
        return float(self.pad.get_hat(0)[1])

    def glaette(self, name, ziel):
        self.glatt[name] += (ziel - self.glatt[name]) * RAMPE
        if abs(self.glatt[name]) < 0.005:
            self.glatt[name] = 0.0
        return self.glatt[name]

    def befehl_sticks(self):
        """(vx, vy, gier, z) aus Sticks und Steuerkreuz. Während der Wende
        läuft die Fahrt weich auf null, gedreht wird von der Wende."""
        steht = self.wende is not None
        dreh = self.glaette('dreh',
                            0.0 if steht else self.stick('drehen') * MAX_YAW)
        vor = self.glaette('vor',
                           0.0 if steht else self.stick('vor') * MAX_SPEED)
        seit = self.glaette('seit',
                            0.0 if steht else self.stick('seit') * MAX_SPEED)
        steig = self.glaette('hoch', self.steuerkreuz() * STEIG_RATE)
        return vor, seit, dreh, self.z_soll + steig * TAKT

    def tasten(self):
        """Liest ALLE Controller-Ereignisse seit dem letzten Aufruf.
        Gibt 'weg', 'start', 'landen', 'wende' oder None zurück. Ein Druck
        zählt genau einmal, es gibt also nichts zu entprellen und nichts
        hängt fest. Wichtigeres gewinnt: weg vor start vor landen vor
        wende."""
        rang = {None: 0, 'wende': 1, 'landen': 2, 'start': 3, 'weg': 4}
        was = None
        for e in pygame.event.get():
            neu = None
            if e.type == pygame.JOYDEVICEREMOVED:
                neu = 'weg'
            elif e.type == pygame.JOYBUTTONDOWN:
                if e.button == KNOPF_START:
                    neu = 'start'
                elif e.button in (KNOPF_B, KNOPF_X):
                    neu = 'landen'
                elif e.button == KNOPF_Y:
                    neu = 'wende'
            if rang[neu] > rang[was]:
                was = neu
        return was

    def warten(self, sekunden):
        """Wartezeit am Boden, in der die Tasten trotzdem abbrechen."""
        ende = time.time() + sekunden
        while time.time() < ende:
            taste = self.tasten()
            if taste in ('start', 'landen'):
                raise Abbruch('Taste gedrückt')
            if taste == 'weg':
                raise Abbruch('Controller getrennt')
            if self.funk_weg:
                raise Abbruch('Funkverbindung verloren')
            time.sleep(0.01)

    # =========================================================================
    # Wende (Taste Y)
    # =========================================================================
    def wende_starten(self):
        """Merkt sich die Richtung. Gezählt wird der gedrehte Winkel Takt
        für Takt, nicht ein Zielwinkel: Bei genau 180 Grad wäre sonst
        nicht klar, ob links oder rechts herum."""
        if self.wende is not None:
            return                      # läuft schon, zweiter Druck zählt nicht
        if self.wende_nach is not None:
            self.wende_nach['nach_bis'] = 0.0
            self.wende_nachlauf()
        pos = self.position()
        if pos is None:
            sag('  Wende geht nicht: keine Richtungsdaten von der Drohne.')
            return
        richtung = -1.0 if self.stick('drehen') < 0 else 1.0
        self.wende = {'richtung': richtung, 'yaw': pos[2], 'gedreht': 0.0,
                      'start': time.time(), 'grund': None, 'rate': 0.0}

    def wende_gier(self):
        """Gierrate für diesen Takt, oder None, wenn keine Wende läuft.
        Proportional zum Rest: weit weg schnell, kurz vor dem Ziel
        langsam. So schießt sie nicht über (die alte Fassung drehte mit
        400 Grad/s bis zum Ziel und schaltete dann hart ab)."""
        w = self.wende
        if w is None:
            return None
        pos = self.position()
        if pos is not None:
            w['gedreht'] += wrap(pos[2] - w['yaw'])
            w['yaw'] = pos[2]
        rest = WENDE_WINKEL - w['richtung'] * w['gedreht']
        if rest <= WENDE_FERTIG:
            self._wende_ende(None)
            return 0.0
        if pos is None:
            self._wende_ende('keine Richtungsdaten mehr')
            return 0.0
        if time.time() - w['start'] > WENDE_ZEIT:
            self._wende_ende('nach %.1f s nicht fertig' % WENDE_ZEIT)
            return 0.0
        ziel = w['richtung'] * min(WENDE_MAX, max(WENDE_MIN, WENDE_K * rest))
        # Nicht in einem Takt auf die volle Rate springen. Das Ende der Wende
        # ist durch WENDE_K sanft, der Anfang war es nicht.
        sprung = WENDE_ANSTIEG * TAKT
        w['rate'] += max(-sprung, min(sprung, ziel - w['rate']))
        return w['rate']

    def _wende_ende(self, grund):
        w = self.wende
        self.wende = None
        w['dauer'] = time.time() - w['start']
        w['grund'] = grund
        w['nach_bis'] = time.time() + WENDE_NACHLAUF
        self.wende_nach = w
        self.glatt['dreh'] = 0.0

    def wende_nachlauf(self):
        """Nach der Wende noch WENDE_NACHLAUF weiterzählen, dann den
        wirklich erreichten Winkel melden. Sie dreht etwas nach."""
        w = self.wende_nach
        if w is None:
            return
        pos = self.position()
        if pos is not None:
            w['gedreht'] += wrap(pos[2] - w['yaw'])
            w['yaw'] = pos[2]
        if time.time() < w['nach_bis']:
            return
        self.wende_nach = None
        winkel = w['richtung'] * w['gedreht']
        w['winkel'] = winkel
        self.stat['wenden'].append(w)
        sag('  Wende %s herum: %.0f Grad in %.1f s%s'
            % ('links' if w['richtung'] > 0 else 'rechts', winkel,
               w['dauer'], ', abgebrochen: %s' % w['grund']
               if w['grund'] else ''))

    def wende_abschliessen(self):
        """Am Flugende: Eine laufende Wende noch in den Bericht bringen."""
        if self.wende is not None:
            self._wende_ende('Flug endete')
        if self.wende_nach is not None:
            self.wende_nach['nach_bis'] = 0.0
            self.wende_nachlauf()

    # =========================================================================
    # Bremslicht
    # =========================================================================
    def licht(self, bremst):
        """Alle LEDs an, solange sie bremst. Geschrieben wird nur beim
        Wechsel, aus erst nach LICHT_NACHLAUF ohne Bremsen. Sonst füllt
        eine flackernde Bremse den Funk mit Parametern."""
        if not self.licht_geht:
            return
        if bremst:
            self.licht_aus_ab = None
            if not self.licht_an:
                self._licht_setzen(True)
        elif self.licht_an:
            if self.licht_aus_ab is None:
                self.licht_aus_ab = time.time() + LICHT_NACHLAUF
            elif time.time() >= self.licht_aus_ab:
                self._licht_setzen(False)

    def _licht_setzen(self, an):
        try:
            self.cf.param.set_value('led.bitmask', str(LED_ALLE if an else 0))
            self.licht_an = an
        except Exception as e:
            self.licht_geht = False
            sag('  Bremslicht abgeschaltet, led.bitmask geht nicht: %s' % e)

    # =========================================================================
    # Motoren
    # =========================================================================
    def senden(self, vx, vy, gier, z):
        self.cf.commander.send_hover_setpoint(vx, vy, gier, z)

    def motoren_aus(self, not_aus=False):
        for _ in range(3):
            try:
                self.cf.commander.send_stop_setpoint()
            except Exception:
                pass
            if not_aus:
                try:
                    self.cf.supervisor.send_emergency_stop()
                except Exception:
                    pass
            time.sleep(0.05)
        try:
            self.cf.commander.send_notify_setpoint_stop()
        except Exception:
            pass
        arm(self.cf, False)
        self.in_luft = False

    # =========================================================================
    # Vorbereitung am Boden
    # =========================================================================
    def verbinden(self, cf):
        """Decks prüfen, die drei Logs starten, Akku prüfen."""
        self.cf = cf
        cf.connection_lost.add_callback(self._funk_weg)
        self._decks_pruefen()
        self._log_sensoren()
        self._log_position()
        self._log_gas()

        time.sleep(0.6)
        if time.time() - self.d_zeit > DATEN_ALT:
            raise Abbruch('es kommen keine Sensordaten an')
        if self.position() is None:
            sag('  Richtungsdaten kommen nicht an, die Wende geht nicht.')
        self._akku_pruefen()

    def _decks_pruefen(self):
        def deck(name):
            try:
                return int(float(self.cf.param.get_value(name)))
            except Exception:
                return 0

        flow = deck('deck.bcFlow2')
        ranger = deck('deck.bcMultiranger')
        sag('  Flow Deck: %s   Multi-Ranger: %s'
            % ('da' if flow else 'FEHLT', 'da' if ranger else 'FEHLT'))
        if not flow:
            raise Abbruch('ohne Flow Deck kann sie die Höhe nicht halten')
        if not ranger:
            raise Abbruch('ohne Multi-Ranger gibt es keinen Wandschutz')
        # BREMS_ABSTAND steht nicht mehr als Zahl im Code, also hier zeigen.
        # Der Raum muss zweimal so breit sein, sonst bremst sie durchgehend.
        sag('  Tempo %.2f m/s, Bremszone %.2f m (Raum ab %.2f m frei befahrbar)'
            % (MAX_SPEED, BREMS_ABSTAND, 2 * BREMS_ABSTAND))

    def _log_sensoren(self):
        """Erstes Log mit 20 ms: 6 x 2 + 2 x 4 = 20 Byte, passt in ein
        Paket. Kein eigener Thread, der Callback schreibt direkt."""
        cf = self.cf
        lg = LogConfig(name='RaceSensoren', period_in_ms=20)
        for name, _ in ALLE_SENSOREN:
            lg.add_variable(name, 'uint16_t')
        for name in ('pm.vbat', 'stateEstimate.z'):
            try:
                if cf.log.toc.get_element_by_complete_name(name) is not None:
                    lg.add_variable(name, 'float')
            except Exception:
                pass
        cf.log.add_config(lg)
        lg.data_received_cb.add_callback(self._empfangen)
        lg.start()
        self.lg = lg

    def _log_position(self):
        """Zweites Log für Position und Richtung: 3 x 4 = 12 Byte. In das
        erste passt es nicht mehr (höchstens 26 Byte pro Paket)."""
        cf = self.cf
        try:
            for name in POS_VARIABLEN:
                if cf.log.toc.get_element_by_complete_name(name) is None:
                    raise KeyError(name)
            lp = LogConfig(name='RacePosition', period_in_ms=50)
            for name in POS_VARIABLEN:
                lp.add_variable(name, 'float')
            cf.log.add_config(lp)
            lp.data_received_cb.add_callback(self._pos_empfangen)
            lp.start()
            self.lg_pos = lp
        except Exception as e:
            self.lg_pos = None
            sag('  Position und Richtung nicht verfügbar: %s' % e)

    def _log_gas(self):
        """Drittes Log für das Gas: 4 x 2 + 4 = 12 Byte, 10-mal pro Sekunde
        reicht. Fehlt es, fliegt sie trotzdem, nur ohne Gasmeldung."""
        cf = self.cf
        try:
            lgg = LogConfig(name='RaceGas', period_in_ms=100)
            for name in MOTOREN:
                if cf.log.toc.get_element_by_complete_name(name) is None:
                    raise KeyError(name)
                lgg.add_variable(name, 'uint16_t')
            if cf.log.toc.get_element_by_complete_name(
                    'stabilizer.thrust') is not None:
                lgg.add_variable('stabilizer.thrust', 'float')
            cf.log.add_config(lgg)
            lgg.data_received_cb.add_callback(self._gas_empfangen)
            lgg.start()
            self.lg_gas = lgg
        except Exception as e:
            self.lg_gas = None
            sag('  Gas der Motoren nicht verfügbar: %s' % e)

    def _akku_pruefen(self):
        """Voll genug zum Starten? Gemessen in Ruhe, vor dem Abheben."""
        volt = self.d.get('pm.vbat')
        self.akku_anfang = volt
        if volt is None or volt <= 0.5:
            sag('  Akku: kein Messwert.')
        elif volt < AKKU_MINIMUM:
            raise Abbruch('Akku %.2f V, zu leer zum Abheben. Erst laden.'
                          % volt)
        elif volt < AKKU_START:
            sag('  Akku %.2f V, unter %.2f V wird es knapp.'
                % (volt, AKKU_START))
            antwort = input('  Trotzdem fliegen? (j/n): ').strip().lower()
            sag('  Antwort: %s' % (antwort or '-'))
            if antwort != 'j':
                raise Abbruch('Akku zu schwach, nicht gestartet')
        else:
            sag('  Akku %.2f V, gut.' % volt)

    def startklar_machen(self):
        """Countdown, Sticks in der Mitte, Platz prüfen, Kalman-Reset."""
        self._countdown()
        self._sticks_mitte()
        self._platz_pruefen()
        self._kalman_zuruecksetzen()

    def _countdown(self):
        pygame.event.clear()        # alte Tastendrücke verwerfen
        sag()
        sag('  Drohne jetzt frei hinstellen. X, B oder START bricht ab.')
        for i in range(COUNTDOWN, 0, -1):
            sag('  Start in %2d s   %s' % (i, self.abstaende_text()))
            self.warten(1.0)

    def _sticks_mitte(self):
        """Sticks und Steuerkreuz müssen in Ruhe sein, sonst fährt sie
        sofort los."""
        t0 = time.time()
        gemeldet = False
        while (any(self.stick(n) != 0.0 for n in ACHSEN)
               or self.steuerkreuz() != 0.0):
            if not gemeldet:
                sag('  Sticks und Steuerkreuz loslassen.')
                gemeldet = True
            if time.time() - t0 > 10.0:
                raise Abbruch('Sticks stehen nicht in der Mitte')
            self.warten(0.05)

    def _platz_pruefen(self):
        """2 s Umgebung prüfen. Der Median, kein Einzelwert."""
        sag('  Prüfe den Platz drumherum (2 s) ...')
        proben = {name: [] for name, _ in ALLE_SENSOREN}
        ende = time.time() + 2.0
        while time.time() < ende:
            for name, _ in ALLE_SENSOREN:
                m = self.unten() if name == 'range.zrange' \
                    else self.abstand(name)
                if m is not None:
                    proben[name].append(m)
            self.warten(0.05)
        if time.time() - self.d_zeit > DATEN_ALT:
            raise Abbruch('Sensordaten sind abgerissen')

        teile = []
        for name, wo in ALLE_SENSOREN:
            teile.append('%s %s' % (wo, zahl(median(proben[name]))))
        sag('  Abstände: %s' % '   '.join(teile))
        for name, wo in SEITEN:
            m = median(proben[name])
            if m is not None and m < NOT_STOPP_ABSTAND:
                raise Abbruch('%s nur %.2f m frei, sie würde sofort wieder '
                              'landen' % (wo, m))
            # Am Boden sieht der vordere Sensor oft den Boden selbst (in
            # den Flügen 0,20 bis 0,21 m, in der Luft dann 1,75 m und
            # mehr). Deshalb nur ein Hinweis.
            if m is not None and m < BREMS_ABSTAND:
                sag('  Hinweis: %s %.2f m. Das kann der Boden selbst sein, '
                    'in der Luft wird neu gemessen.' % (wo, m))
        oben = median(proben['range.up'])
        if oben is not None and oben < MIN_HOEHE + DECKEN_ABSTAND:
            raise Abbruch('oben nur %.2f m frei, zu wenig zum Fliegen' % oben)
        if oben is not None and oben < START_HOEHE + DECKEN_ABSTAND:
            sag('  Hinweis: oben nur %.2f m frei, sie steigt kaum.' % oben)

    def _kalman_zuruecksetzen(self):
        """Kalman zurücksetzen und armen, genau wie in 30_fliegen.py."""
        sag('  Kalman zurücksetzen ...')
        self.cf.commander.send_stop_setpoint()
        self.warten(0.1)
        self.cf.commander.send_setpoint(0, 0, 0, 0)
        self.warten(0.1)
        self.cf.param.set_value('kalman.resetEstimation', '1')
        self.warten(0.2)
        self.cf.param.set_value('kalman.resetEstimation', '0')
        self.warten(1.5)
        arm(self.cf, True)
        self.warten(0.3)

    # =========================================================================
    # Flug: abheben, fliegen, landen
    # =========================================================================
    def abheben(self, ziel):
        """Steigt mit 20 Befehlen pro Sekunde auf die Zielhöhe. Schutz und
        Tasten sind dabei aktiv. Gibt (Grund, schnell) zurück, wenn
        abgebrochen wurde, sonst None."""
        ziel = max(MIN_HOEHE, min(MAX_HOEHE, ziel))
        sag('  Abheben auf %.2f m ...' % ziel)
        # Nach dem Kalman-Reset neu anfangen: Die Möbelsumme gilt ab hier
        self.z_vorher = None
        self.sprung_summe = 0.0
        self.in_luft = True
        self.z_soll = 0.05
        takt = Takt()
        halten_bis = None
        while True:
            taste = self.tasten()
            if taste in ('start', 'landen'):
                return 'Taste beim Abheben', False
            if taste == 'weg':
                return 'Controller getrennt', False
            g = self.gefahr()
            if g:
                return g
            if self.z_soll < ziel:
                if self.decke_frei():
                    self.z_soll = min(ziel, self.z_soll + ABHEBE_TEMPO * TAKT)
                else:
                    if self.z_soll < MIN_HOEHE:
                        return 'oben zu wenig Platz zum Abheben', False
                    sag('  Decke nah, Aufstieg endet bei %.2f m.'
                        % self.z_soll)
                    ziel = self.z_soll
            elif halten_bis is None:
                halten_bis = time.time() + 0.5
            elif time.time() > halten_bis:
                break
            # Ohne Vorlauf: Sonst ist das Ziel am Boden nur VORLAUF hoch,
            # und ein schwacher Akku hebt womöglich nicht rechtzeitig ab.
            z, _grund, _v = self.z_senden(self.z_soll, vorlauf=False,
                                          boden=0.0)
            self.z_gesendet = z
            self.senden(0.0, 0.0, 0.0, z)
            takt.warte()

        # Hebt sie überhaupt ab? (aus 30_fliegen.py übernommen)
        unten = self.unten()
        if unten is not None and unten < 0.10:
            self.motoren_aus()
            volt = self.d.get('pm.vbat') or 0.0
            sag('  SIE HEBT NICHT AB (gemessen %.2f m). Motoren aus.' % unten)
            if volt and volt < AKKU_MINIMUM:
                sag('  Der Akku ist leer (%.2f V). Laden.' % volt)
            else:
                sag('  Akku %.2f V. Propeller prüfen: verbogen, lose, '
                    'falsch herum?' % volt)
            return 'hebt nicht ab', False
        return None

    def luft_melden(self):
        """Nach dem Abheben die Abstände neu melden. Am Boden sehen die
        Seitensensoren oft den Boden selbst."""
        sag('  In der Luft: %s' % self.abstaende_text())
        for name, wo in SEITEN:
            m = self.abstand(name)
            if m is not None and m <= HALTE_ABSTAND:
                sag('  Hinweis: %s %.2f m, dorthin fährt sie gar nicht.'
                    % (wo, m))
            elif m is not None and m < BREMS_ABSTAND:
                sag('  Hinweis: %s %.2f m, dorthin fährt sie nur gebremst.'
                    % (wo, m))

    def schleife(self, schreiber):
        """Die Flugschleife, 20-mal pro Sekunde.
        Gibt (Grund, schnell) zurück, warum sie endet."""
        takt = Takt()
        t0 = time.time()
        naechste_anzeige = t0 + 1.0
        gebremst_zuletzt = False
        while True:
            # 1. Tasten und Gefahr
            taste = self.tasten()
            if taste in ('start', 'landen'):
                return 'Taste gedrückt', False
            if taste == 'weg':
                return 'Controller getrennt', False
            if taste == 'wende':
                self.wende_starten()
            g = self.gefahr()
            if g:
                return g
            t = time.time() - t0

            # 2. Befehl aus den Sticks, während der Wende dreht die Wende
            vx, vy, gier, z = self.befehl_sticks()
            wende_gier = self.wende_gier()
            if wende_gier is not None:
                gier = wende_gier
            self.wende_nachlauf()

            # 3. Höhe: Möbel, Decke, Vorlauf, Höhe verloren
            self._moebel_melden()
            z_send, versatz = self._hoehe_festlegen(z)
            z_ist = self.d.get('stateEstimate.z')
            if self._hoehe_verloren(z_ist):
                vx = vy = gier = 0.0

            # 4. Bremsen NACH dem Glätten, und zurückschreiben. Sonst holt
            # die Glättung beim nächsten Takt die alte Fahrt wieder hervor.
            vx, vy, gebremst = self.bremsen(vx, vy)
            self.glatt['vor'], self.glatt['seit'] = vx, vy

            # 5. Senden
            self.senden(vx, vy, gier, z_send)

            # 6. Licht, Akku, Statistik, CSV, Anzeige einmal pro Sekunde
            self.licht(gebremst)
            self._akku_warnen()
            vbat = self.d.get('pm.vbat')
            gas = self.motoren()
            self._statistik(t, vbat, gas, gebremst, z_ist, versatz)
            if gebremst:
                gebremst_zuletzt = True
            schreiber.writerow(self._csv_zeile(
                t, vx, vy, gier, z_ist, vbat, gebremst, z_send, versatz,
                gas))
            if time.time() >= naechste_anzeige:
                naechste_anzeige += 1.0
                self._anzeige(t, gas, gebremst_zuletzt)
                gebremst_zuletzt = False
            takt.warte()

    def _akku_warnen(self):
        """Einmal melden, wenn der Akku unter Last knapp wird."""
        if self.akku_knapp >= AKKU_TAKTE and not self.akku_gewarnt:
            self.akku_gewarnt = True
            sag('  AKKU KNAPP: %.2f V unter Last. Bald landen, bei %.2f V '
                'landet sie selbst.' % (self.d.get('pm.vbat', 0.0),
                                        AKKU_LEER))

    def _moebel_melden(self):
        """Möbel melden (hier im Hauptthread, nicht im Callback)."""
        moebel = -self.versatz()
        if abs(moebel - self.moebel_gemeldet) > 0.05:
            if moebel > 0.005:
                sag('  Möbel unter ihr: %.2f m hoch, Höhe angepasst.'
                    % moebel)
            else:
                sag('  Wieder über dem Boden.')
            self.moebel_gemeldet = moebel
        self.stat['moebel_max'] = max(self.stat['moebel_max'], moebel)

    def _hoehe_festlegen(self, z):
        """Wunschhöhe über dem Fußboden, gesendet mit Möbel, Decke und
        Vorlauf. Das Gesendete wird zurückgeschrieben, damit das
        Steuerkreuz nicht gegen die Decke "anspart" und die Landung dort
        beginnt, wo sie wirklich ist. Gibt (z_gesendet, versatz) zurück."""
        z_wunsch = max(MIN_HOEHE, min(MAX_HOEHE, z))
        z_send, grund, versatz = self.z_senden(z_wunsch)
        if grund == 'decke':
            self.glatt['hoch'] = 0.0
            self.stat['decke'] += 1
        elif grund == 'vorlauf':
            self.stat['vorlauf'] += 1
        self.z_soll = z_send - versatz
        self.z_gesendet = z_send
        return z_send, versatz

    def _hoehe_verloren(self, z_ist):
        """Sie soll mindestens MIN_HOEHE hoch, ist aber fast am Boden
        (schwacher Akku). Gibt True zurück, dann nicht weiterfahren."""
        if z_ist is not None and z_ist < HOEHE_VERLOREN:
            if not self.hoehe_weg:
                sag('  Höhe verloren (%.2f m, Akku %s V), Fahrt gestoppt.'
                    % (z_ist, zahl(self.d.get('pm.vbat'))))
                self.hoehe_weg = True
            self.stat['hoehe_weg'] += 1
            return True
        if self.hoehe_weg and z_ist is not None \
                and z_ist > HOEHE_VERLOREN + 0.05:
            sag('  Wieder auf %.2f m, Fahrt geht weiter.' % z_ist)
            self.hoehe_weg = False
        return False

    def _statistik(self, t, vbat, gas, gebremst, z_ist, versatz):
        """Zahlen für die Zusammenfassung sammeln, nach 2 s das Gas melden."""
        s = self.stat
        if t < 2.0 and vbat is not None and vbat > 0.5:
            self.akku_schweben.append(vbat)
        if gas is not None:
            if t < 2.0:
                self.gas_schweben.append(gas)
            if s['gas_max'] is None or gas[1] > s['gas_max']:
                s['gas_max'] = gas[1]
            if gas[1] >= GAS_ANSCHLAG:
                s['gas_anschlag'] += 1
        if t >= 2.0 and not self.gas_gemeldet:
            self.gas_gemeldet = True
            self.gas_melden()
        if z_ist is not None:
            hoehe = z_ist - versatz
            if s['z_max'] is None or hoehe > s['z_max']:
                s['z_max'] = hoehe
        s['takte'] += 1
        s['dauer'] = t
        if gebremst:
            s['gebremst'] += 1
        for name, _ in SEITEN:
            m = self.abstand(name)
            alt = s['min'][name]
            if m is not None and (alt is None or m < alt):
                s['min'][name] = m

    def gas_melden(self):
        g = self.schwebegas()
        if g is None:
            sag('  Schwebegas: keine Daten.')
            return
        sag('  Schwebegas: im Mittel %.0f %%, stärkster Motor %.0f %% '
            '(350er am 14.09.: 65-70 %%, stärkster 72-76 %%).' % g)
        if g[1] > GAS_KNAPP:
            sag('  ACHTUNG: wenig Reserve. Tief bleiben, sanft fliegen.')

    def _csv_zeile(self, t, vx, vy, gier, z_ist, vbat, gebremst, z_send,
                   versatz, gas):
        """Eine Zeile passend zu CSV_KOPF."""
        zeile = ['%.2f' % t, '%.3f' % vx, '%.3f' % vy, '%.1f' % gier,
                 '%.3f' % self.z_soll]
        zeile.append('' if z_ist is None else '%.3f' % z_ist)
        zeile.append('' if vbat is None else '%.2f' % vbat)
        for name in ('range.front', 'range.back', 'range.left',
                     'range.right', 'range.up'):
            m = roh_m(self.d.get(name))
            zeile.append('' if m is None else '%.3f' % m)
        m = self.unten()
        zeile.append('' if m is None else '%.3f' % m)
        zeile.append('1' if gebremst else '0')
        zeile.append('1' if self.wende is not None else '0')
        pos = self.position()
        if pos is None:
            zeile += ['', '', '']
        else:
            zeile += ['%.3f' % pos[0], '%.3f' % pos[1], '%.1f' % pos[2]]
        zeile.append('%.3f' % z_send)
        zeile.append('%.3f' % max(0.0, -versatz))
        frisch = gas is not None
        for name in MOTOREN + ('stabilizer.thrust',):
            wert = self.gas.get(name) if frisch else None
            zeile.append('' if wert is None else '%.1f' % wert)
        return zeile

    def _anzeige(self, t, gas, gebremst_zuletzt):
        """Eine Zeile pro Sekunde auf den Bildschirm. Die Höhe über dem
        Fußboden, also mit herausgerechnetem Möbel."""
        z_ist = self.d.get('stateEstimate.z')
        v = self.versatz()
        extra = ''
        if v < -0.005:
            extra += '   Möbel %.2f m' % -v
        if self.wende is not None:
            extra += '   WENDE'
        if gebremst_zuletzt:
            extra += '   BREMST'
        sag('  %5.1f s  Höhe %s m (soll %.2f)  Akku %s V  Motor max %s   %s%s'
            % (t, zahl(None if z_ist is None else z_ist - v),
               self.z_soll, zahl(self.d.get('pm.vbat')),
               '-' if gas is None else '%.0f %%' % gas[1],
               '  '.join('%s %s' % (wo[0], zahl(self.abstand(n)))
                         for n, wo in SEITEN + [('range.up', 'oben')]),
               extra))

    def landen(self, schnell=False):
        """Sinkt gleichmäßig bis zum Boden, dann Motoren aus. Ein zweiter
        Druck auf START schaltet sofort ab (Not-Aus)."""
        tempo = SINK_TEMPO_NOT if schnell else SINK_TEMPO
        z = max(self.z_soll, 0.0)           # über dem Fußboden
        sag('  %sLandung aus %.2f m mit %.1f m/s ...'
            % ('NOT-' if schnell else '', z, tempo))
        takt = Takt()
        boden_seit = None
        # Über einem Möbel landet sie darauf, gesendet wird also mit Versatz
        ende = (time.time() + max(0.0, z + self.versatz()) / tempo
                + BODEN_NACHLAUF + 2.0)
        while time.time() < ende:
            if self.tasten() == 'start':
                sag('  START während der Landung: NOT-AUS, Motoren aus.')
                sag('  Sie ist jetzt gesperrt: einmal aus- und einschalten.')
                self.motoren_aus(not_aus=True)
                return
            z = max(0.0, z - tempo * TAKT)
            self.z_soll = z
            z_send = max(0.0, z + self.versatz())
            self.z_gesendet = z_send
            self.senden(0.0, 0.0, 0.0, z_send)
            unten = self.unten()
            if unten is not None and unten < BODEN and z_send < 0.15:
                break
            if z_send <= 0.0:
                if boden_seit is None:
                    boden_seit = time.time()
                elif time.time() - boden_seit > BODEN_NACHLAUF:
                    break
            takt.warte()
        self.motoren_aus()
        sag('  Gelandet, Motoren aus.')


# =============================================================================
# ABLAUF
# =============================================================================
def fliegen(pad, stempel):
    """Ein ganzer Flug: verbinden, startklar, abheben, Schleife, landen,
    Zusammenfassung. Gibt 0 zurück, 1 ohne Verbindung."""
    r = RaceDrohne(pad)
    r.nullpunkt_messen()
    csv_pfad = os.path.join(HIER, 'race_indoor_%s.csv' % stempel)

    cflib.crtp.init_drivers()
    grund = None
    datei = None
    verbunden = False
    for uri in URIS:
        sag('  Verbinde mit %s ...' % uri)
        try:
            with SyncCrazyflie(uri, cf=Crazyflie(
                    rw_cache=os.path.join(HIER, 'cache'))) as scf:
                verbunden = True
                try:
                    r.verbinden(scf.cf)
                    r.startklar_machen()
                    datei = open(csv_pfad, 'w', encoding='utf-8',
                                 newline='')
                    schreiber = csv.writer(datei, delimiter=';')
                    schreiber.writerow(CSV_KOPF)

                    grund = r.abheben(START_HOEHE)
                    if grund is None:
                        r.luft_melden()
                        sag()
                        sag('  Los! Y = Wende, X/B/START = landen.')
                        grund = r.schleife(schreiber)
                except Abbruch as e:
                    grund = 'vor dem Start abgebrochen: %s' % e, False
                except KeyboardInterrupt:
                    grund = 'Strg+C', False
                except Exception as e:
                    grund = 'Programmfehler: %s' % e, False
                    for zeile in traceback.format_exc().splitlines():
                        sag('    ' + zeile)
                finally:
                    aufraeumen(r, grund, datei)
        except Exception as e:
            if not verbunden:
                sag('  Keine Verbindung: %s' % e)
                continue
            # Die Verbindung stand, der Fehler kam erst beim Trennen
            sag('  Fehler beim Trennen der Verbindung: %s' % e)
        break
    if not verbunden:
        sag('  Ist sie eingeschaltet, steckt der Funkstick, ist der '
            'cfclient zu?')
        return 1

    zusammenfassung(r, grund)
    csv_abschliessen(datei, csv_pfad, r.stat['takte'])
    return 0


def aufraeumen(r, grund, datei):
    """Egal wie der Flug endete: Ist sie in der Luft, wird gelandet.
    Klappt nicht einmal das (zweites Strg+C, Funk weg), gehen die
    Motoren aus. Danach Licht aus, Datei zu, Logs stoppen."""
    if grund:
        sag()
        sag('  Grund: %s' % grund[0])
        if 'Hindernis' in grund[0] or 'Start' in grund[0]:
            sag('  Alle Abstände: %s' % r.abstaende_text())
    r.wende_abschliessen()
    try:
        if r.in_luft:
            r.landen(schnell=bool(grund and grund[1]))
        elif r.cf is not None:
            r.motoren_aus()
    except BaseException as e:
        sag('  Landung unterbrochen (%s), Motoren aus.'
            % (type(e).__name__))
        r.motoren_aus()
    if r.licht_an:
        r._licht_setzen(False)
    if datei is not None:
        datei.close()
    for lg in (r.lg, r.lg_pos, r.lg_gas):
        if lg is not None:
            try:
                lg.stop()
            except Exception:
                pass


def zusammenfassung(r, grund):
    """Die Zahlen am Ende, auf den Bildschirm und in den Bericht."""
    s = r.stat
    sag()
    sag('  ---------------- Zusammenfassung ----------------')
    sag('  Beendet weil:      %s' % (grund[0] if grund else '-'))
    sag('  Geflogen:          %.1f s (%d Takte)' % (s['dauer'], s['takte']))
    if s['takte']:
        sag('  Gebremst:          %d Takte (%.0f %%)'
            % (s['gebremst'], 100.0 * s['gebremst'] / s['takte']))
        sag('  Höchste Höhe:      %s m' % zahl(s['z_max']))
        sag('  An der Decke:      %d Takte' % s['decke'])
        sag('  Steigen gebremst:  %d Takte (Vorlauf %.2f m)'
            % (s['vorlauf'], VORLAUF))
        sag('  Möbel darunter:    %s'
            % ('max. %.2f m' % s['moebel_max'] if s['moebel_max'] > 0.005
               else 'keine erkannt'))
        if s['hoehe_weg']:
            sag('  Höhe verloren:     %d Takte, Fahrt dabei gestoppt'
                % s['hoehe_weg'])
        sag('  Kleinster Abstand: %s'
            % '   '.join('%s %s' % (wo, zahl(s['min'][n]))
                         for n, wo in SEITEN))
    wenden = s['wenden']
    if wenden:
        fertig = [w for w in wenden if not w['grund']]
        sag('  Wenden:            %d, davon %d fertig' % (len(wenden),
                                                         len(fertig)))
        if fertig:
            sag('  Wende im Mittel:   %.0f Grad in %.1f s (Ziel %.0f Grad)'
                % (sum(w['winkel'] for w in fertig) / len(fertig),
                   sum(w['dauer'] for w in fertig) / len(fertig),
                   WENDE_WINKEL))
    else:
        sag('  Wenden:            keine')
    sag('  Akku:              %s V vor dem Start, %s V danach'
        % (zahl(r.akku_anfang), zahl(r.d.get('pm.vbat'))))
    if r.akku_tief is not None:
        sag('  Akku im Flug:      tiefster Wert %.2f V' % r.akku_tief)
    if r.akku_anfang and r.akku_schweben:
        mittel = sum(r.akku_schweben) / len(r.akku_schweben)
        sag('  Einbruch beim Schweben: %.2f V (%.2f V in Ruhe, %.2f V in den '
            'ersten 2 s)' % (r.akku_anfang - mittel, r.akku_anfang, mittel))
    g = r.schwebegas()
    if g is not None:
        sag('  Schwebegas:        im Mittel %.0f %%, stärkster Motor %.0f %%'
            % g)
    if s['gas_max'] is not None:
        sag('  Gas im Flug:       stärkster Motor höchstens %.0f %%, '
            '%d Takte am Anschlag (ab %.0f %%)'
            % (s['gas_max'], s['gas_anschlag'], GAS_ANSCHLAG))


def csv_abschliessen(datei, csv_pfad, takte):
    """Pfad der CSV melden. Nichts geflogen: leere Datei nicht liegen
    lassen."""
    if datei is not None and takte:
        sag('  Messwerte: %s' % csv_pfad)
    elif datei is not None:
        try:
            os.remove(csv_pfad)
        except OSError:
            pass


def controller_suchen():
    """Gibt den Controller zurück oder None. Ohne ihn wird nicht
    geflogen."""
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() < 1:
        sag('  Kein Controller gefunden. Einschalten und neu starten.')
        return None
    pad = pygame.joystick.Joystick(0)
    pad.init()
    sag('  Controller: %s' % pad.get_name())
    if pad.get_numaxes() < 3:
        sag('  Er hat nur %d Achsen, gebraucht werden 3.' % pad.get_numaxes())
        return None
    if pad.get_numhats() < 1:
        sag('  Hinweis: kein Steuerkreuz gefunden, die Höhe bleibt fest.')
    return pad


def main():
    stempel = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    bericht = os.path.join(HIER, 'race_indoor_%s.txt' % stempel)
    sag()
    sag('  Crazyflie Race Indoor (Version %s)' % VERSION)
    sag('  %s' % datetime.now().strftime('%d.%m.%Y %H:%M'))
    sag()
    try:
        for arg in sys.argv[1:]:
            sag('  Unbekannte Angabe "%s" wird ignoriert.' % arg)
        pad = controller_suchen()
        if pad is None:
            return 1
        return fliegen(pad, stempel)
    finally:
        sag('  Bericht:   %s' % bericht)
        with open(bericht, 'w', encoding='utf-8') as f:
            f.write('\n'.join(_zeilen) + '\n')
        pygame.quit()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('  Abgebrochen.')
        sys.exit(1)
