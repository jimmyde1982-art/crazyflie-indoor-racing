#!/usr/bin/env python3
"""
flow_ranger_recorder.py  --  Fliegen, aufzeichnen, nachfliegen
==============================================================
Version 3.1 vom 13.09.2026. Die Vorgängerversion 2.1 liegt unverändert
als flow_ranger_recorder_v2_1.py daneben.

Start
-----
  py flow_ranger_recorder.py            normal, mit Akkuschutz
  py flow_ranger_recorder.py maxakku    ohne jede Akkuprüfung

Mit maxakku fliegt sie, bis der Akku sie nicht mehr trägt. Das Ende
kommt auf eine von zwei Arten:
  - Sie sackt auf den Boden und kommt nicht mehr hoch. Nach 3 s gehen
    die Motoren aus ("Akku am Ende").
  - Die Firmware schaltet die Drohne ab, wenn der Akku 5 s unter 3,0 V
    liegt (pm_stm32f4.c, pmSystemShutdown). Dann FÄLLT sie aus der
    aktuellen Höhe. Deshalb in diesem Modus tief fliegen.
Alle anderen Schutzfunktionen (Hindernisse, Decke, Tasten, Funk) bleiben.

Was neu ist gegenüber 2.1
-------------------------
 1. START hängt nicht mehr fest. Die alte Entprell-Schleife las den
    Controller nicht neu und lief endlos. Die Drohne bekam dann keine
    Befehle mehr, und die Firmware schaltete nach 2 s die Motoren ab.
 2. Der Schutz ist schon beim Abheben aktiv, nicht erst danach.
 3. Bremszone: Ab 50 cm wird die Fahrt auf ein Hindernis zu gedrosselt,
    bei 10 cm ist Schluss. 10 cm allein reichen nicht, weil die
    Propeller über den Sensor hinausragen und die Drohne bei 0,5 m/s
    schneller dort ist, als die Meldung ankommt. Die Bremse lässt sie
    bei 15 cm stehen, die 10 cm sind nur noch für Überraschungen da
    (etwas kommt plötzlich von der Seite).
 4. Echte Landung: Sie sinkt mit 0,3 m/s bis zum Boden. Vorher fiel sie
    aus 30 cm in unter einer Sekunde.
 5. Egal was passiert (Strg+C, Programmfehler, Controller abgezogen),
    sie landet. Bei Akku unter 3,20 V (2 s lang) landet sie auch.
 6. Vor dem Start wird geprüft: Decks da? Akku voll genug? Sticks in
    der Mitte? Platz drumherum? Der Kalman wird zurückgesetzt wie in
    30_fliegen.py.

Tasten
------
  B oder START    landen (in beiden Modi)
  START nochmal   während der Landung: Motoren sofort aus (Not-Aus)
  Strg+C          landen, ein zweites Strg+C: Motoren aus

Achsen wie in 2.1 und 30_fliegen.py:
  linker Stick    hoch/runter und drehen
  rechter Stick   vor/zurück und seitlich

Dateien (alle neben diesem Skript)
----------------------------------
  aufnahme_<Zeit>.csv        was geflogen wurde, Grundlage fürs Replay
  replay_<Zeit>.csv          was beim Nachfliegen wirklich gesendet wurde
  flug_<Modus>_<Zeit>.txt    alles, was auf dem Bildschirm stand
"""
import os

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
# Controller auch dann lesen, wenn das Konsolenfenster nicht vorne ist
os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')

import csv
import glob
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

# -----------------------------------------------------------------------------
# KONFIGURATION
# -----------------------------------------------------------------------------
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')
HIER = os.path.dirname(os.path.abspath(__file__))

HZ_RATE = 20                # Regel- und Aufzeichnungsrate
TAKT = 1.0 / HZ_RATE

# Steuerung (unverändert aus 2.1)
DEADZONE = 0.12
EXPO = 1.80
RAMPE = 0.25
MAX_SPEED = 0.50            # m/s
MAX_YAW = 90.0              # Grad/s
STEIG_RATE = 0.45           # m/s

START_HOEHE = 0.30
MIN_HOEHE = 0.20
MAX_HOEHE = 1.30

# Schutz
NOT_STOPP_ABSTAND = 0.10    # m, darunter: Notlandung
BREMS_ABSTAND = 0.50        # m, ab hier wird gedrosselt
HALTE_ABSTAND = 0.15        # m, hier steht sie (Luft bis zur Notlandung)
ENG_FOLGE = 2               # so viele Messungen HINTEREINANDER unter 10 cm
SENSOR_MIN = 0.03           # m, kleinere Werte sind keine Messung
DECKEN_ABSTAND = 0.40       # m, weniger frei nach oben: nicht mehr steigen
DATEN_ALT = 0.5             # s, älter = Sensoren blind

# Akku (die Akkus sind verbraucht, siehe Memory "Akkus sind durch")
AKKU_START = 3.80           # V, darunter Rückfrage
AKKU_MINIMUM = 3.60         # V, darunter kein Start
# Im Flug zählt die Spannung UNTER LAST. Am 13.09.2026 brach ein Akku mit
# 4,05 V in Ruhe beim Schweben sofort auf 3,38 V ein und fiel beim Steigen
# auf 3,27 V. Nach der Landung stand er wieder bei 3,97 V, war also nicht
# leer, sondern verbraucht. Die alte Grenze von 3,30 V für 0,5 s hat
# deshalb nach 4 s gelandet. Die Firmware selbst meldet "Akku schwach"
# erst unter 3,2 V für 5 s, "kritisch" unter 3,0 V
# (platform_defaults_cf2.h). Wir landen bei 3,2 V für 2 s, also früher
# als die Firmware warnt.
AKKU_LEER = 3.20            # V unter Last, im Flug darunter: landen
AKKU_TAKTE = 40             # so viele Messungen hintereinander (2 s)

# Wird mit "maxakku" beim Start eingeschaltet (siehe main). Dann gibt es
# keine Akkuprüfung, weder vor dem Start noch im Flug.
MAX_AKKU = False
AKKU_AM_ENDE = 3.0          # s am Boden, obwohl sie fliegen soll: Motoren aus

# Start und Landung
ABHEBE_TEMPO = 0.30         # m/s
SINK_TEMPO = 0.30           # m/s
SINK_TEMPO_NOT = 0.50       # m/s
BODEN = 0.07                # m, darunter gilt sie als gelandet
BODEN_NACHLAUF = 1.5        # s, danach Motoren aus, auch ohne Bodenmessung

COUNTDOWN_AUFNAHME = 10
COUNTDOWN_REPLAY = 5

# Xbox-Controller unter pygame 2.6 (wie 30_fliegen.py)
KNOPF_B = 1
KNOPF_START = 7
ACHSEN = {'drehen': (0, -1), 'hoehe': (1, -1),
          'seit': (2, -1), 'vor': (3, -1)}

SEITEN = [('range.front', 'vorne'), ('range.back', 'hinten'),
          ('range.left', 'links'), ('range.right', 'rechts')]
ALLE_SENSOREN = SEITEN + [('range.up', 'oben'), ('range.zrange', 'unten')]

CSV_KOPF = ['t_s', 'vx_ms', 'vy_ms', 'gier_grad_s', 'z_soll_m', 'z_ist_m',
            'vbat_v', 'vorne_m', 'hinten_m', 'links_m', 'rechts_m', 'oben_m',
            'gebremst']


# -----------------------------------------------------------------------------
# AUSGABE
# -----------------------------------------------------------------------------
_zeilen: list[str] = []


def sag(text=''):
    """Druckt auf den Bildschirm und merkt sich die Zeile für die Datei."""
    print(text, flush=True)
    _zeilen.append(text)


def zahl(wert, form='%.2f'):
    return '-' if wert is None else form % wert


def begrenzt(wert, grenze):
    return max(-grenze, min(grenze, wert))


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


# -----------------------------------------------------------------------------
# DIE DROHNE
# -----------------------------------------------------------------------------
class FlowRanger:
    def __init__(self, pad):
        self.pad = pad
        self.cf = None
        self.lg = None
        self.nullpunkt = {}
        self.glatt = {'vor': 0.0, 'seit': 0.0, 'dreh': 0.0, 'hoch': 0.0}

        # Wird vom Log-Callback (eigener Thread der cflib) beschrieben
        self.d = {}
        self.d_zeit = 0.0
        self.nah = {name: 0 for name, _ in SEITEN}
        self.nah_wert = {name: None for name, _ in SEITEN}
        self.akku_leer = 0
        self.funk_weg = False

        self.in_luft = False
        self.z_soll = 0.0
        self.akku_anfang = None
        self.akku_tief = None
        self.stat = {'takte': 0, 'gebremst': 0, 'decke': 0,
                     'min': {name: None for name, _ in SEITEN},
                     'dauer': 0.0}

    # ------------------------------------------------------------ Sensoren
    def _empfangen(self, zeitstempel, daten, konf):
        self.d.update(daten)
        self.d_zeit = time.time()
        # Ein einzelner Wert unter 10 cm ist kein Befund. Erst ENG_FOLGE
        # Messungen hintereinander zählen.
        for name, _ in SEITEN:
            m = self.abstand(name)
            if m is not None and m < NOT_STOPP_ABSTAND:
                self.nah[name] += 1
                self.nah_wert[name] = m
            else:
                self.nah[name] = 0
        v = daten.get('pm.vbat')
        if self.in_luft and v is not None and v > 0.5:
            if self.akku_tief is None or v < self.akku_tief:
                self.akku_tief = v
        if v is not None and 0.5 < v < AKKU_LEER:
            self.akku_leer += 1
        else:
            self.akku_leer = 0

    def _funk_weg(self, uri, meldung):
        self.funk_weg = True
        print('\n  !!! FUNKVERBINDUNG VERLOREN: %s' % meldung, flush=True)

    def abstand(self, name):
        """Abstand in m, oder None bei 'nichts gesehen' / 'ungültig'."""
        mm = self.d.get(name)
        if mm is None or mm >= 8000:
            return None
        m = mm / 1000.0
        if m < SENSOR_MIN:
            return None
        return m

    def unten(self):
        mm = self.d.get('range.zrange')
        if mm is None or mm >= 8000:
            return None
        return mm / 1000.0

    def abstaende_text(self):
        teile = []
        for name, wo in ALLE_SENSOREN:
            m = self.unten() if name == 'range.zrange' else self.abstand(name)
            teile.append('%s %s' % (wo, zahl(m)))
        return '   '.join(teile)

    def decke_frei(self):
        oben = self.abstand('range.up')
        return oben is None or oben > DECKEN_ABSTAND

    def gefahr(self):
        """(Grund, schnell) oder None."""
        if self.funk_weg:
            return 'Funkverbindung verloren', True
        alt = time.time() - self.d_zeit
        if alt > DATEN_ALT:
            return 'seit %.1f s keine Sensordaten' % alt, False
        for name, wo in SEITEN:
            if self.nah[name] >= ENG_FOLGE:
                return ('Hindernis %s bei %s m'
                        % (wo, zahl(self.nah_wert[name])), True)
        if not MAX_AKKU and self.akku_leer >= AKKU_TAKTE:
            return 'Akku leer (%.2f V)' % self.d.get('pm.vbat', 0.0), False
        return None

    def bremsen(self, vx, vy):
        """Drosselt nur die Fahrt AUF ein Hindernis zu. Wegfliegen geht
        immer. Zwischen 50 und 15 cm fällt die erlaubte Geschwindigkeit
        gleichmäßig von 0,5 m/s auf null.

        Nicht bis 10 cm bremsen: Dann kriecht sie genau an die Grenze
        der Notlandung heran (in der Simulation bis 11 cm), und in echt
        schiebt die Verzögerung sie darüber."""
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

    # ------------------------------------------------------------ Controller
    def nullpunkt_messen(self):
        """Ruhelage der Sticks, wie in 30_fliegen.py. Der Xbox-Nullpunkt
        springt bei jedem Einschalten des Controllers."""
        if self.pad is None:
            return
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
        if self.pad is None:
            return 0.0
        nr, richtung = ACHSEN[name]
        if nr >= self.pad.get_numaxes():
            return 0.0
        x = (self.pad.get_axis(nr) - self.nullpunkt.get(nr, 0.0)) * richtung
        x = max(-1.0, min(1.0, x))
        if abs(x) < DEADZONE:
            return 0.0
        rest = (abs(x) - DEADZONE) / (1.0 - DEADZONE)
        return math.copysign(rest ** EXPO, x)

    def glaette(self, name, ziel):
        self.glatt[name] += (ziel - self.glatt[name]) * RAMPE
        if abs(self.glatt[name]) < 0.005:
            self.glatt[name] = 0.0
        return self.glatt[name]

    def tasten(self):
        """Liest ALLE Controller-Ereignisse seit dem letzten Aufruf.
        Gibt 'weg', 'start', 'b' oder None zurück. Ein Druck zählt genau
        einmal, es gibt also nichts zu entprellen und nichts hängt fest."""
        was = None
        for e in pygame.event.get():
            if e.type == pygame.JOYDEVICEREMOVED:
                was = 'weg'
            elif e.type == pygame.JOYBUTTONDOWN and was != 'weg':
                if e.button == KNOPF_START:
                    was = 'start'
                elif e.button == KNOPF_B and was is None:
                    was = 'b'
        return was

    def warten(self, sekunden):
        """Wartezeit am Boden, in der B/START trotzdem abbrechen."""
        ende = time.time() + sekunden
        while time.time() < ende:
            taste = self.tasten()
            if taste in ('start', 'b'):
                raise Abbruch('Taste gedrückt')
            if taste == 'weg':
                raise Abbruch('Controller getrennt')
            if self.funk_weg:
                raise Abbruch('Funkverbindung verloren')
            time.sleep(0.01)

    # ------------------------------------------------------------ Motoren
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

    # ------------------------------------------------------------ Vorbereitung
    def verbinden(self, cf):
        self.cf = cf
        cf.connection_lost.add_callback(self._funk_weg)

        def deck(name):
            try:
                return int(float(cf.param.get_value(name)))
            except Exception:
                return 0

        flow = deck('deck.bcFlow2')
        ranger = deck('deck.bcMultiranger')
        sag('  Flow Deck: %s   Multi-Ranger: %s'
            % ('da' if flow else 'FEHLT', 'da' if ranger else 'FEHLT'))
        if not flow:
            raise Abbruch('ohne Flow Deck kann sie die Höhe nicht halten')
        if not ranger:
            raise Abbruch('ohne Multi-Ranger gibt es keinen Hindernisschutz')

        # Ein einziges Log mit 50 ms: 6 x 2 + 2 x 4 = 20 Byte, passt in
        # ein Paket. Kein eigener Thread, der Callback schreibt direkt.
        lg = LogConfig(name='FlowRanger', period_in_ms=50)
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

        time.sleep(0.6)
        if time.time() - self.d_zeit > DATEN_ALT:
            raise Abbruch('es kommen keine Sensordaten an')

        volt = self.d.get('pm.vbat')
        self.akku_anfang = volt
        if volt is None or volt <= 0.5:
            sag('  Akku: kein Messwert.')
        elif MAX_AKKU:
            sag('  Akku %.2f V. MAXAKKU: keine Akkuprüfung.' % volt)
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

    def startklar_machen(self, countdown):
        pygame.event.clear()        # alte Tastendrücke verwerfen
        sag()
        sag('  Drohne jetzt frei hinstellen. B oder START bricht ab.')
        for i in range(countdown, 0, -1):
            sag('  Start in %2d s   %s' % (i, self.abstaende_text()))
            self.warten(1.0)

        # Sticks müssen in der Mitte stehen, sonst fährt sie sofort los
        if self.pad is not None:
            t0 = time.time()
            gemeldet = False
            while any(self.stick(n) != 0.0 for n in ACHSEN):
                if not gemeldet:
                    sag('  Sticks loslassen, sie müssen in der Mitte stehen.')
                    gemeldet = True
                if time.time() - t0 > 10.0:
                    raise Abbruch('Sticks stehen nicht in der Mitte')
                self.warten(0.05)

        # 2 s Umgebung prüfen. Der Median, kein Einzelwert.
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

        def median(w):
            w = sorted(w)
            return w[len(w) // 2] if w else None

        teile = []
        for name, wo in ALLE_SENSOREN:
            teile.append('%s %s' % (wo, zahl(median(proben[name]))))
        sag('  Abstände: %s' % '   '.join(teile))
        for name, wo in SEITEN:
            m = median(proben[name])
            if m is not None and m < NOT_STOPP_ABSTAND:
                raise Abbruch('%s nur %.2f m frei, sie würde sofort wieder '
                              'landen' % (wo, m))
            if m is not None and m <= HALTE_ABSTAND:
                sag('  Hinweis: %s %.2f m, dorthin fährt sie gar nicht.'
                    % (wo, m))
            elif m is not None and m < BREMS_ABSTAND:
                sag('  Hinweis: %s %.2f m, dorthin fährt sie nur gebremst.'
                    % (wo, m))
        oben = median(proben['range.up'])
        if oben is not None and oben < MIN_HOEHE + DECKEN_ABSTAND:
            raise Abbruch('oben nur %.2f m frei, zu wenig zum Fliegen' % oben)
        if oben is not None and oben < START_HOEHE + DECKEN_ABSTAND:
            sag('  Hinweis: oben nur %.2f m frei, sie steigt kaum.' % oben)

        # Kalman zurücksetzen und armen, genau wie in 30_fliegen.py
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

    # ------------------------------------------------------------ Flug
    def abheben(self, ziel):
        """Steigt auf die Zielhöhe. Schutz und Tasten sind dabei aktiv.
        Gibt (Grund, schnell) zurück, wenn abgebrochen wurde, sonst None."""
        ziel = max(MIN_HOEHE, min(MAX_HOEHE, ziel))
        sag('  Abheben auf %.2f m ...' % ziel)
        self.in_luft = True
        self.z_soll = 0.05
        takt = Takt()
        halten_bis = None
        while True:
            taste = self.tasten()
            if taste in ('start', 'b'):
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
            self.senden(0.0, 0.0, 0.0, self.z_soll)
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

    def schleife(self, befehl, schreiber):
        """Die eigentliche Flugschleife, gleich für Aufnahme und Replay.
        befehl() liefert (vx, vy, gier, z) oder None am Ende."""
        takt = Takt()
        t0 = time.time()
        naechste_anzeige = t0 + 1.0
        gebremst_zuletzt = False
        boden_seit = None
        while True:
            taste = self.tasten()
            if taste in ('start', 'b'):
                return 'Taste %s gedrückt' % taste.upper(), False
            if taste == 'weg':
                return 'Controller getrennt', False
            g = self.gefahr()
            if g:
                return g

            # MAXAKKU: Sitzt sie am Boden, obwohl sie mindestens 20 cm
            # hoch soll, trägt der Akku sie nicht mehr. Dann nicht mit
            # Vollgas am Boden weiterlaufen lassen, sondern abschalten.
            if MAX_AKKU:
                unten = self.unten()
                if unten is not None and unten < BODEN:
                    if boden_seit is None:
                        boden_seit = time.time()
                    elif time.time() - boden_seit > AKKU_AM_ENDE:
                        self.motoren_aus()
                        return ('Akku am Ende: sie kommt nicht mehr hoch '
                                '(%s V)' % zahl(self.d.get('pm.vbat')),
                                False)
                else:
                    boden_seit = None

            soll = befehl()
            if soll is None:
                return 'Replay zu Ende', False
            vx, vy, gier, z = soll

            # Nicht in die Decke steigen
            if z > self.z_soll and not self.decke_frei():
                z = self.z_soll
                self.glatt['hoch'] = 0.0
                self.stat['decke'] += 1
            self.z_soll = max(MIN_HOEHE, min(MAX_HOEHE, z))

            # Bremsen NACH dem Glätten, und zurückschreiben. Sonst holt
            # die Glättung beim nächsten Takt die alte Fahrt wieder hervor.
            vx, vy, gebremst = self.bremsen(vx, vy)
            self.glatt['vor'], self.glatt['seit'] = vx, vy

            self.senden(vx, vy, gier, self.z_soll)

            t = time.time() - t0
            self.stat['takte'] += 1
            self.stat['dauer'] = t
            if gebremst:
                self.stat['gebremst'] += 1
                gebremst_zuletzt = True
            for name, _ in SEITEN:
                m = self.abstand(name)
                alt = self.stat['min'][name]
                if m is not None and (alt is None or m < alt):
                    self.stat['min'][name] = m

            if schreiber is not None:
                zeile = ['%.2f' % t, '%.3f' % vx, '%.3f' % vy, '%.1f' % gier,
                         '%.3f' % self.z_soll]
                z_ist = self.d.get('stateEstimate.z')
                vbat = self.d.get('pm.vbat')
                zeile.append('' if z_ist is None else '%.3f' % z_ist)
                zeile.append('' if vbat is None else '%.2f' % vbat)
                for name in ('range.front', 'range.back', 'range.left',
                             'range.right', 'range.up'):
                    m = self.abstand(name)
                    zeile.append('' if m is None else '%.3f' % m)
                zeile.append('1' if gebremst else '0')
                schreiber.writerow(zeile)

            if time.time() >= naechste_anzeige:
                naechste_anzeige += 1.0
                sag('  %5.1f s  Höhe %s m (soll %.2f)  Akku %s V   %s%s'
                    % (t, zahl(self.d.get('stateEstimate.z')), self.z_soll,
                       zahl(self.d.get('pm.vbat')),
                       '  '.join('%s %s' % (wo[0], zahl(self.abstand(n)))
                                 for n, wo in SEITEN + [('range.up', 'oben')]),
                       '   BREMST' if gebremst_zuletzt else ''))
                gebremst_zuletzt = False
            takt.warte()

    def befehl_sticks(self):
        dreh = self.glaette('dreh', self.stick('drehen') * MAX_YAW)
        vor = self.glaette('vor', self.stick('vor') * MAX_SPEED)
        seit = self.glaette('seit', self.stick('seit') * MAX_SPEED)
        steig = self.glaette('hoch', self.stick('hoehe') * STEIG_RATE)
        return vor, seit, dreh, self.z_soll + steig * TAKT

    def landen(self, schnell=False):
        """Sinkt gleichmäßig bis zum Boden, dann Motoren aus. Ein zweiter
        Druck auf START schaltet sofort ab (Not-Aus)."""
        tempo = SINK_TEMPO_NOT if schnell else SINK_TEMPO
        z = max(self.z_soll, 0.0)
        sag('  %sLandung aus %.2f m mit %.1f m/s ...'
            % ('NOT-' if schnell else '', z, tempo))
        takt = Takt()
        boden_seit = None
        ende = time.time() + z / tempo + BODEN_NACHLAUF + 2.0
        while time.time() < ende:
            if self.tasten() == 'start':
                sag('  START während der Landung: NOT-AUS, Motoren aus.')
                sag('  Sie ist jetzt gesperrt: einmal aus- und einschalten.')
                self.motoren_aus(not_aus=True)
                return
            z = max(0.0, z - tempo * TAKT)
            self.z_soll = z
            self.senden(0.0, 0.0, 0.0, z)
            unten = self.unten()
            if unten is not None and unten < BODEN and z < 0.15:
                break
            if z <= 0.0:
                if boden_seit is None:
                    boden_seit = time.time()
                elif time.time() - boden_seit > BODEN_NACHLAUF:
                    break
            takt.warte()
        self.motoren_aus()
        sag('  Gelandet, Motoren aus.')


# -----------------------------------------------------------------------------
# AUFNAHMEN
# -----------------------------------------------------------------------------
def aufnahme_laden(pfad):
    """Liest eine Aufnahme. Werte werden auf die Grenzen dieses Skripts
    geklemmt, auch wenn jemand die Datei von Hand geändert hat."""
    frames = []
    try:
        with open(pfad, encoding='utf-8', newline='') as f:
            for zeile in csv.DictReader(f, delimiter=';'):
                try:
                    vx = begrenzt(float(zeile['vx_ms']), MAX_SPEED)
                    vy = begrenzt(float(zeile['vy_ms']), MAX_SPEED)
                    gier = begrenzt(float(zeile['gier_grad_s']), MAX_YAW)
                    z = max(MIN_HOEHE, min(MAX_HOEHE,
                                           float(zeile['z_soll_m'])))
                except (KeyError, ValueError, TypeError):
                    continue
                frames.append((vx, vy, gier, z))
    except OSError:
        pass
    return frames


def aufnahme_waehlen():
    dateien = sorted(glob.glob(os.path.join(HIER, 'aufnahme_*.csv')),
                     key=os.path.getmtime, reverse=True)[:5]
    if not dateien:
        sag('  Keine Aufnahme gefunden (aufnahme_*.csv in %s).' % HIER)
        sag('  Erst mit [1] einen Flug aufzeichnen.')
        return None, None
    sag()
    sag('  Die neuesten Aufnahmen:')
    geladen = []
    for i, pfad in enumerate(dateien, 1):
        frames = aufnahme_laden(pfad)
        geladen.append(frames)
        if frames:
            sag('  [%d] %s   %5.1f s, bis %.2f m hoch'
                % (i, os.path.basename(pfad), len(frames) * TAKT,
                   max(f[3] for f in frames)))
        else:
            sag('  [%d] %s   leer' % (i, os.path.basename(pfad)))
    wahl = input('  Welche? (Enter = 1): ').strip() or '1'
    sag('  Gewählt: %s' % wahl)
    try:
        nr = int(wahl) - 1
        pfad, frames = dateien[nr], geladen[nr]
    except (ValueError, IndexError):
        sag('  Ungültige Wahl.')
        return None, None
    if not frames:
        sag('  Diese Aufnahme enthält keine Flugdaten.')
        return None, None
    return pfad, frames


# -----------------------------------------------------------------------------
# ABLAUF
# -----------------------------------------------------------------------------
def fliegen(pad, modus, stempel, frames=None):
    r = FlowRanger(pad)
    r.nullpunkt_messen()

    if modus == 'aufnahme':
        csv_pfad = os.path.join(HIER, 'aufnahme_%s.csv' % stempel)
        countdown = COUNTDOWN_AUFNAHME
        start_hoehe = START_HOEHE
        befehl = r.befehl_sticks
    else:
        csv_pfad = os.path.join(HIER, 'replay_%s.csv' % stempel)
        countdown = COUNTDOWN_REPLAY
        start_hoehe = frames[0][3]
        vorrat = iter(frames)
        befehl = lambda: next(vorrat, None)     # noqa: E731

    cflib.crtp.init_drivers()
    sag('  Verbinde mit %s ...' % URI)
    grund = None
    datei = None
    try:
        with SyncCrazyflie(URI, cf=Crazyflie(
                rw_cache=os.path.join(HIER, 'cache'))) as scf:
            try:
                r.verbinden(scf.cf)
                r.startklar_machen(countdown)
                datei = open(csv_pfad, 'w', encoding='utf-8', newline='')
                schreiber = csv.writer(datei, delimiter=';')
                schreiber.writerow(CSV_KOPF)

                grund = r.abheben(start_hoehe)
                if grund is None:
                    sag()
                    if modus == 'aufnahme':
                        sag('  Du steuerst. Alles wird aufgezeichnet. '
                            'B oder START = landen.')
                    else:
                        sag('  Replay läuft (%d Takte, %.1f s). '
                            'B oder START = landen.'
                            % (len(frames), len(frames) * TAKT))
                    grund = r.schleife(befehl, schreiber)
            except Abbruch as e:
                grund = 'vor dem Start abgebrochen: %s' % e, False
            except KeyboardInterrupt:
                grund = 'Strg+C', False
            except Exception as e:
                grund = 'Programmfehler: %s' % e, False
                for zeile in traceback.format_exc().splitlines():
                    sag('    ' + zeile)
            finally:
                # Egal wie die Schleife verlassen wurde: Ist sie in der
                # Luft, wird gelandet. Klappt nicht einmal das (zweites
                # Strg+C, Funk weg), gehen die Motoren aus.
                if grund:
                    sag()
                    sag('  Grund: %s' % grund[0])
                    if 'Hindernis' in grund[0] or 'Start' in grund[0]:
                        sag('  Alle Abstände: %s' % r.abstaende_text())
                try:
                    if r.in_luft:
                        r.landen(schnell=bool(grund and grund[1]))
                    elif r.cf is not None:
                        r.motoren_aus()
                except BaseException as e:
                    sag('  Landung unterbrochen (%s), Motoren aus.'
                        % (type(e).__name__))
                    r.motoren_aus()
                if datei is not None:
                    datei.close()
                if r.lg is not None:
                    try:
                        r.lg.stop()
                    except Exception:
                        pass
    except Exception as e:
        sag('  Keine Verbindung zur Drohne: %s' % e)
        sag('  Ist sie eingeschaltet, steckt der Funkstick, ist der '
            'cfclient zu?')
        return 1

    # ------------------------------------------------ Zusammenfassung
    s = r.stat
    sag()
    sag('  ---------------- Zusammenfassung ----------------')
    sag('  Modus:             %s%s' % (modus, ' (MAXAKKU)' if MAX_AKKU else ''))
    sag('  Beendet weil:      %s' % (grund[0] if grund else '-'))
    sag('  Geflogen:          %.1f s (%d Takte)' % (s['dauer'], s['takte']))
    if s['takte']:
        sag('  Gebremst:          %d Takte (%.0f %%)'
            % (s['gebremst'], 100.0 * s['gebremst'] / s['takte']))
        sag('  An der Decke:      %d Takte' % s['decke'])
        sag('  Kleinster Abstand: %s'
            % '   '.join('%s %s' % (wo, zahl(s['min'][n]))
                         for n, wo in SEITEN))
    sag('  Akku:              %s V vor dem Start, %s V danach'
        % (zahl(r.akku_anfang), zahl(r.d.get('pm.vbat'))))
    if r.akku_tief is not None:
        einbruch = ''
        if r.akku_anfang:
            einbruch = ' (Einbruch unter Last %.2f V)' % (r.akku_anfang
                                                          - r.akku_tief)
        sag('  Akku im Flug:      tiefster Wert %.2f V%s'
            % (r.akku_tief, einbruch))
    if datei is not None and s['takte']:
        sag('  %s %s' % ('Aufnahme:' if modus == 'aufnahme' else 'Protokoll:',
                         csv_pfad))
    elif datei is not None:
        # Nichts geflogen: leere Datei nicht liegen lassen, sonst taucht
        # sie beim Replay als "leer" in der Liste auf.
        try:
            os.remove(csv_pfad)
        except OSError:
            pass
    return 0


def main():
    global MAX_AKKU
    stempel = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    sag()
    sag('  Crazyflie Flow-Ranger: Aufnahme und Replay (Version 3.1)')
    sag('  %s' % datetime.now().strftime('%d.%m.%Y %H:%M'))
    sag()

    for arg in sys.argv[1:]:
        if arg.lower().strip('-()') == 'maxakku':
            MAX_AKKU = True
        else:
            sag('  Unbekannte Angabe "%s" wird ignoriert (erlaubt: maxakku).'
                % arg)
    if MAX_AKKU:
        sag('  *** MAXAKKU: keine Akkuprüfung. Sie fliegt, bis der Akku')
        sag('  *** sie nicht mehr trägt. Die Firmware schaltet unter 3,0 V')
        sag('  *** ab, dann FÄLLT sie. Tief fliegen!')
        sag()

    sag('  [1] Flug aufzeichnen (du steuerst, alles wird mitgeschrieben)')
    sag('  [2] Aufnahme nachfliegen')
    sag('  [3] Beenden')
    wahl = input('\n  Modus (1-3): ').strip()
    sag('  Gewählt: %s' % wahl)
    if wahl not in ('1', '2'):
        return 0
    modus = 'aufnahme' if wahl == '1' else 'replay'

    pygame.init()
    pygame.joystick.init()
    pad = None
    if pygame.joystick.get_count() > 0:
        pad = pygame.joystick.Joystick(0)
        pad.init()
        sag('  Controller: %s' % pad.get_name())
    elif modus == 'aufnahme':
        sag('  Kein Controller gefunden. Zum Aufzeichnen wird er gebraucht.')
        return 1
    else:
        sag('  Kein Controller. Abbrechen geht nur mit Strg+C.')

    frames = None
    if modus == 'replay':
        quelle, frames = aufnahme_waehlen()
        if not frames:
            return 1
        sag('  Quelle: %s' % quelle)

    bericht = os.path.join(HIER, 'flug_%s_%s.txt' % (modus, stempel))
    try:
        return fliegen(pad, modus, stempel, frames)
    finally:
        sag('  Bericht:  %s' % bericht)
        with open(bericht, 'w', encoding='utf-8') as f:
            f.write('\n'.join(_zeilen) + '\n')
        pygame.quit()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('  Abgebrochen.')
        sys.exit(1)
