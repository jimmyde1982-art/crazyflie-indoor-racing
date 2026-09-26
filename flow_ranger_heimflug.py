#!/usr/bin/env python3
"""
flow_ranger_heimflug.py  --  Hinfliegen, landen, allein zurückfliegen
====================================================================
Version 4.1 vom 20.09.2026. Grundlage ist flow_ranger_recorder.py 3.2
(Ordner test): Sensorfilter, Hindernisschutz, Deckenschutz, Möbel,
Abheben und Landung sind von dort übernommen.

Neu in 2.7
----------
1. Hebt sie gar nicht ab, bleibt die alte Landestelle in
   heim_lande_<Zeit>.csv stehen. Vorher schrieb das Skript schon beim
   Abheben "unbekannt" hinein. Scheiterte der Start danach (Flug
   20.09. 12:12: "SIE HEBT NICHT AB"), war die Landestelle weg und
   Menü [3] ging für diesen Flug nicht mehr. "Unbekannt" wird jetzt
   erst geschrieben, wenn sie wirklich vom Boden weg ist.
2. Der Stick übernimmt den Rückflug erst, wenn er STICK_FREI_ZEIT am
   Stück in der Mitte war (0,5 s). Vorher reichte ein einziger Takt
   Mittelstellung: Beim Loslassen schwingt der Stick durch die Mitte,
   und 0,5 s nach dem Umkehren steuerte plötzlich die Hand
   (Flug 19.09. 21:26).

Neu in 2.8: Akku wie in der Firmware
------------------------------------
Die Crazyflie-Firmware kennt zwei Schwellen: 3,20 V ist "leer"
(Warnung, LED blinkt), 3,00 V ist "kritisch". Bis 2.7 landete das
Skript schon bei 3,20 V. Jetzt:
  - unter 3,20 V (2 s am Stück): nur eine Meldung, sie fliegt weiter
  - unter 3,00 V (0,5 s am Stück): NOTLANDUNG, sofort und schnell
Die Umkehr im Hinflug rechnet mit 3,25 V statt 3,35 V, sie fliegt
also etwas weiter, bevor sie von selbst zurückkehrt.

ACHTUNG: Unter 3,0 V unter Last bricht der Schub weg. Die Notlandung
braucht selbst noch Strom. Das ist die letzte Reißleine, kein
Arbeitsbereich. Wer tief fliegt, fliegt mit einem geladenen Akku.

Neu in 2.9: mittig durch die Tür
--------------------------------
Die Tür ist die engste Stelle des Flugbereichs (90 cm offen, die
Drohne ist mit Propellern etwa 13 cm breit). Zwei Dinge gingen dort
bisher schief:
  - Flug 19.09. 21:28 endete mit "Hindernis links bei 0.08 m": Der
    Hindernisschutz hielt den Türrahmen für ein Hindernis und hat
    sie mitten im Durchgang gelandet.
  - Flug 19.09. 22:31 kam auf dem Rückweg 30 cm versetzt durch die
    Tür, Reserve links nur noch 19 cm.

Jetzt erkennt das Skript eine Öffnung daran, dass auf BEIDEN Seiten
gleichzeitig eine Wand in Reichweite ist (ein Hindernis hat nur auf
einer Seite eine). In einer Öffnung:
  - schiebt sie sich im Alleinflug aktiv in die Mitte, gemessen an
    den Seitenabständen statt an der Positionsschätzung. Das wirkt
    auch dann, wenn das Flow Deck auf dem Teppich gedriftet ist.
  - landet sie nicht mehr wegen der Seitenwände. Erst unter
    TUER_RAND (6 cm) am Rahmen greift der Schutz doch.
Vorne, hinten und oben bleibt der Hindernisschutz unverändert scharf.

Neu in 3.0: die Bodenkamera misst sich selbst
---------------------------------------------
Zweimal wurde geraten, warum ein Rückflug scheiterte (Licht,
Untergrund), zweimal war es falsch. Darum schreibt das Skript jetzt
die Qualitätswerte des Flow Decks mit:
  shutter  Belichtungszeit. Steigt, wenn es dunkel oder kontrastarm
           ist. Ein Sprung nach oben heißt: sie sieht schlechter.
  squal    Zahl der verfolgten Merkmale im Bild. Je höher, desto
           sicherer die Bewegungsmessung. Unter etwa 30 wird es dünn.
  maxRaw   hellstes Pixel. Sehr hoch bei gleichzeitig niedrigem squal
           heißt: Spiegelung. Genau das droht auf glänzendem Boden,
           wenn eine Lampe sich darin spiegelt.
Die Werte stehen in den drei letzten Spalten der Flug-CSV und am Ende
noch einmal als Zusammenfassung.

WICHTIG: Das ist reine Diagnose. Die Werte werden NIE zum Steuern
benutzt, sie ändern am Flugverhalten nichts. Fehlen sie (andere
Firmware, kein Flow Deck), fliegt sie genauso, nur ohne Aufzeichnung.
Der Log läuft mit 5 Hz statt 20 Hz, damit die Funkstrecke frei bleibt.

Neu in 3.2: das Wippen im Alleinflug
------------------------------------
Zwei Stellen ließen den Drehbefehl ruckeln, und beim Gieren kippt sie
sichtbar mit. Erstens begrenzte das Replay auf MAX_YAW (90 Grad/s, die
Grenze für den Stick in der Hand) statt auf RUECK_YAW (60 Grad/s).
Zweitens ging der Drehbefehl des Reglers ungefiltert raus, während
der Stick von Hand durch glaette() läuft. Im Flug vom 20.09. 14:49
sprang der Wert dadurch um bis zu 67 Grad/s von Takt zu Takt; seit 3.2
sind es höchstens 15.

Neu in 3.3: schneller, ohne weniger Abstand
-------------------------------------------
MAX_SPEED steigt von 0,50 auf 0,65 m/s. Die Grenze nach oben setzt
nicht dieses Skript, sondern die Firmware: ihr Geschwindigkeitsregler
verlangt 25 Grad Neigung je 1 m/s (PID_VEL_X_KP = 25.0) und darf dabei
höchstens 20 Grad kippen (PID_VEL_ROLL_MAX = 20.0). Ab 20/25 = 0,80
m/s steht er am Anschlag, hat keine Reserve mehr und schießt über
das Soll hinaus -- also genau das Wippen, das 3.2 gerade beseitigt
hat. 0,65 lässt 19 Prozent Luft. Wer den Wert hochdreht, bekommt beim
Start einen Fehler statt eines Absturzes.

Weil der Bremsweg mit dem Tempo wächst, ist BREMS_ABSTAND jetzt aus
MAX_SPEED gerechnet (HALTE_ABSTAND + MAX_SPEED * REAKTION_S) und keine
feste Zahl mehr. Das hält die Drosselkennlinie unterhalb von 0,50 m
Abstand exakt so, wie sie bis 3.2 war: an einem Hindernis in 0,23 m
darf sie weiter nur 0,11 m/s. Schneller ist sie allein dort, wo mehr
als 0,60 m frei sind.

Neu in 3.4: 0,72 m/s, und der Rückflug bleibt beim Tempo der Aufnahme
---------------------------------------------------------------------
MAX_SPEED steigt von 0,65 auf 0,72 m/s. Das ist der größte Wert, der
die 10 Prozent Reserve unter dem Anschlag von 0,80 noch einhält: sie
neigt sich dann 18 der erlaubten 20 Grad. Mehr geht nicht, darüber
regelt die Firmware die Geschwindigkeit nicht mehr, sondern kippt nur
noch voll.

Wichtiger als das Tempo ist die zweite Änderung. Der Rückflug spielt
die Aufnahme ab und zieht sich nebenher auf den Weg zurück; die Summe
aus beidem wurde bis 3.3 auf MAX_SPEED gedeckelt. Das war falsch, denn
MAX_SPEED ist die Grenze für den Stick in deiner Hand. Wer sie
hochdrehte, machte damit auch den Rückflug schneller, als der Hinflug
je war. Im Flug vom 20.09. 15:49 fuhr sie zurück bis 0,65 m/s, obwohl
die Aufnahme nur 0,51 m/s enthielt -- bei einer Bodenkamera, die durch
die Sonne im Fenster schon am Belichtungsanschlag stand.

Seit 3.4 richtet sich der Deckel im Replay nach der Aufnahme selbst:
schneller als ihr schnellster Takt wird der Rückflug nicht, egal was
MAX_SPEED sagt. Bist du langsam hingeflogen, kommt sie auch langsam
zurück. Für die Aufnahme vom 20.09. 15:41 heißt das 0,51 statt 0,65
m/s. Die Wegkorrektur wird dabei mitskaliert, ihre Richtung bleibt
also erhalten.

Neu in 3.5: der Hinflug kann einen Namen bekommen
-------------------------------------------------
Nach der Landung, wenn die Motoren aus sind und der Funk zu ist, fragt
das Skript: "Strecke behalten?" Tippst du einen Namen, wandert eine
Kopie der Aufnahme nach strecken/ und bekommt eine kleine Textdatei
mit Kennzahlen daneben. Leer lassen heißt: nicht behalten.

Am Flug ändert das nichts. Die Frage kommt erst, wenn alles vorbei
ist -- von dort aus kann kein Motor mehr anlaufen. Die Aufnahme selbst
bleibt in jedem Fall liegen, gespeichert wird nur eine Kopie, und eine
vorhandene Strecke wird nie ohne Rückfrage ersetzt.

Die Arbeit macht strecken.py nebenan. Fehlt die Datei, läuft alles
wie bisher, nur ohne die Frage.

Neu in 4.0: alles in einer Datei
--------------------------------
Aus dem Namen wird eine Streckenverwaltung. Drei Menüpunkte kamen dazu:

  [4] Strecke abfliegen. Du wählst eine benannte Strecke oder mehrere
      hintereinander ("1,2,1") und sagst, wie oft das Ganze laufen
      soll. Das Skript setzt die Teile zusammen, zeigt Takte, Weg,
      Spannweite und Umkehrpunkt und fragt, ob es losgehen soll.
  [5] Nur aufzeichnen. Du fliegst, sie schreibt mit und landet am
      Ende, statt zurückzufliegen. Das ist der Aufnahmemodus aus dem
      Recorder. Zurück holst du sie danach mit [3].
  [6] Strecken verwalten. Ansehen, umbenennen, aussortieren. Es wird
      dabei weder gefunkt noch geflogen, und gelöscht wird nichts:
      Aussortiertes landet in strecken/ausrangiert/.

Zum Zusammensetzen: vx, vy, Gierrate und Höhe gelten im Rahmen der
Drohne und bleiben unangetastet. Nur die Position und die
Blickrichtung werden gedreht und verschoben, damit Teil 2 dort
anfängt, wo Teil 1 aufgehört hat. Ohne das führte der Weg an jeder
Naht zum Nullpunkt zurück.

Gewarnt wird, wenn der zusammengesetzte Weg weiter reicht als jedes
Einzelteil für sich -- denn jedes Teil ist einmal wirklich geflogen
worden und passt also in den Raum, der Zusammenbau aber nicht
unbedingt. Sinnvoll ist Verketten vor allem bei einer Runde, die dort
endet, wo sie anfängt.

Start
-----
  python flow_ranger_heimflug.py

Menü (wie im Recorder)
----------------------
  [1] Hin und zurück fliegen, mit Aufnahme (Ablauf unten). Der Hinflug
      wird als heim_hin_<Zeit>.csv gespeichert.
  [2] Aufnahme nachfliegen, hin und zurück (neu in 2.5): Einen der
      letzten Hinflüge (heim_hin_*.csv) wählen. Sie fliegt ihn allein
      VORWÄRTS nach, vom Startpunkt aus, mit Wegkorrektur wie das Replay
      im Recorder. Am Ende der Aufnahme kehrt sie in der Luft um und
      fliegt gespiegelt zurück zum Startpunkt, wie bei [1].
      Es gilt alles wie bei [1]: A = sofort umkehren, Akku reicht nicht
      mehr = sie kehrt von selbst um, Stick bewegen = du übernimmst,
      B = landen (am Boden dann A = zurückfliegen).
      Die Drohne muss an DENSELBEN Startpunkt und in DIESELBE Richtung
      gestellt werden wie beim Hinflug. Sonst fliegt sie den Weg
      verschoben oder verdreht.
  [3] Nur zurückfliegen (neu in 2.6): Sie fliegt ab der Stelle, an der
      sie zuletzt gelandet ist, allein zum Startpunkt, auf dem Weg des
      letzten Flugs. Auch nach einem Neustart des Skripts oder der
      Drohne. Die Landeposition steht in heim_lande_<Zeit>.csv. Sie muss
      GENAU dort liegen, wo sie gelandet ist: nicht angehoben, nicht
      verschoben, nicht gedreht. Sonst fliegt sie einen falschen Weg.
      Endete der letzte Flug mit Not-Aus oder Funkabbruch in der Luft,
      ist die Lage unbekannt, dann geht es nicht.
  [4] Strecke abfliegen (neu in 4.0): Eine benannte Strecke aus
      strecken/ oder mehrere hintereinander, wahlweise mehrfach. Sie
      fliegt den Weg vorwärts ab und kehrt am Ende um, wie bei [2].
      Auch hier gilt: derselbe Startpunkt, dieselbe Richtung.
  [5] Nur aufzeichnen (neu in 4.0): Du fliegst, sie schreibt mit und
      landet am Ende. Kein Rückflug -- A und B landen beide. Danach
      holt [3] sie zurück, solange sie unberührt liegen bleibt.
  [6] Strecken verwalten (neu in 4.0): Ansehen, umbenennen,
      aussortieren. Fliegt nicht und braucht keinen Controller.
  [7] Beenden

Auf dem Rückweg gelandet (neu in 2.6)
-------------------------------------
Landest du sie auf dem Rückweg mit B, wartet das Skript: A = ab hier
weiter zum Startpunkt, B = beenden. Sie sucht sich auf dem gespiegelten
Weg die Stelle, die ihr am nächsten ist (höchstens 0,5 m daneben), und
fliegt von dort weiter.

Ablauf
------
 1. Hinflug: Du steuerst wie im Recorder. Der Weg wird mitgeschrieben.
 2. Umkehren, auf eine von drei Arten:
      a) A in der Luft: Sie kehrt sofort um, ohne Landung.
      b) Automatisch: Reicht der Akku nur noch für den Rückweg (plus
         Reserve), kehrt sie von selbst um. Vorher kommt eine Warnung.
         Die Anzeige "zurück xx s" zeigt, wie lang der Rückweg gerade ist.
      c) B landen, dann am Boden A (wie Version 1).
 3. Beim Umkehren die Sticks LOSLASSEN. Erst danach gilt: Stick bewegen
    = du übernimmst.
 4. Rückflug (neu in 2.1) wie das Replay im Recorder, nur gespiegelt:
    Jeder Takt des Hinflugs wurde aufgezeichnet (Befehle und Position).
    Sie dreht sich auf der Stelle um 180 Grad und spielt die Aufnahme
    RÜCKWÄRTS ab: gleiche Fahrt, Drehrichtung umgekehrt. Wie im Replay
    zieht die Wegkorrektur sie jeden Takt sanft auf den aufgezeichneten
    Weg (höchstens 0,2 m/s und 30 Grad/s). Takte, in denen du nur
    gestanden hast, fallen weg. Am Ende schiebt sie sich zum Startpunkt,
    dreht sich in die Startrichtung und landet.
    Wichtig: Bist du vorwärts geflogen, fliegt sie vorwärts zurück. Bist
    du seitwärts geflogen, fliegt sie auch seitwärts zurück. Schleifen
    fliegt sie mit, genau wie du.
    RUECKWEG_ART = 'weg' schaltet zurück auf Version 2.0 (eigener Weg,
    Nase immer voraus, Schleifen weggelassen).

Funk (neu in 2.2)
-----------------
Am Boden liegt die Antenne der Drohne tief, der Funk reißt dort leichter
ab (Tests 18.09.: zweimal am Boden, nie in der Luft). Reißt er AM BODEN
ab, während die Motoren aus sind, verbindet das Skript von selbst neu
(bis zu 10 Versuche, B = aufgeben) und macht dann weiter: beim Warten auf
A genauso wie beim Start. Die Position für den Rückflug merkt sich das
Skript auf dem PC, sie geht dabei nicht verloren.
Reißt der Funk IN DER LUFT ab, kann kein Programm etwas tun: Die Drohne
schaltet nach etwa 2 s selbst die Motoren aus. Deshalb zeigt die Anzeige
jede Sekunde "Funk xx %". Fällt der Wert unter 70 %, kommt eine Warnung.
Dann näher ran oder den Funkstick höher legen (USB-Verlängerung).

Wie sie den Weg findet
----------------------
Nach dem Kalman-Reset beim Start ist der Startpunkt x = y = 0, Richtung
0 Grad. Zwischen Hin- und Rückflug wird NICHT zurückgesetzt, sonst wäre
der Startpunkt vergessen. Die Position kommt allein vom Flow Deck
(Boden-Kamera). Die rechnet mit jedem Meter ein wenig daneben. Erwartung:
Sie landet im Umkreis von etwa 10 bis 30 cm um den echten Startpunkt,
je länger der Flug, desto weiter daneben.

Am Boden läuft die Schätzung der Drohne weg, obwohl sie still liegt
(Test 18.09.2026: 39 Grad). Darum merkt sich das Skript die Position kurz
VOR dem Aufsetzen und setzt den Kalman vor dem Rückflug genau darauf.
Folge: Das Skript merkt NICHT, wenn du sie am Boden verschiebst. Dann
fliegt sie einen falschen Weg. Also zwischen Landung und Rückflug die
Drohne NICHT anfassen.

Sicherheit beim Rückflug
------------------------
  - Hindernisschutz, Deckenschutz und Akku-Überwachung wie beim Hinflug.
  - Stick bewegen (nachdem er 0,5 s in der Mitte war): Du übernimmst,
    das Skript steuert nicht mehr.
  - B oder START: landen. START während der Landung: Motoren aus.
  - Steht 3 s lang etwas vorne im Weg: Sie landet dort.
  - In einer Öffnung (beide Seiten nah) schiebt sie sich mittig
    durch, statt dort zu landen (Version 2.9).
  - Mehr als 0,8 m neben dem Weg oder 1 s ohne Positionsdaten: landen.

Tasten
------
  A               in der Luft: sofort umkehren, ohne Landung
                  nach der Landung: Rückflug starten
  B oder START    landen (Hin- und Rückflug), am Boden: beenden
  START nochmal   während der Landung: Motoren sofort aus (Not-Aus)
  Strg+C          landen, ein zweites Strg+C: Motoren aus

Achsen wie im Recorder:
  linker Stick    hoch/runter und drehen
  rechter Stick   vor/zurück und seitlich

Dateien (alle neben diesem Skript)
----------------------------------
  heim_hin_<Zeit>.csv       Hinflug, jede 50 ms
  heim_rueck_<Zeit>.csv     Rückflug, jede 50 ms
  heim_pfad_<Zeit>.csv      der Weg, den sie zurückfliegt
  heim_nach_<Zeit>.csv      Nachflug (Menü 2, hinwärts), jede 50 ms
  heim_lande_<Zeit>.csv     wo sie zuletzt gelandet ist (für Menü 3)
  heim_rest_<Zeit>.csv      Rückflug ab einer Landestelle unterwegs
  flug_heim_<Zeit>.txt      alles, was auf dem Bildschirm stand
"""
import os

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
# Controller auch dann lesen, wenn das Konsolenfenster nicht vorne ist
os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')

import csv
import glob
import math
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime

import cflib.crtp
import pygame
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils import uri_helper

# strecken.py liegt daneben und fliegt nicht -- es benennt und verwaltet
# fertige Aufnahmen. Fehlt es, läuft das Flugskript trotzdem, dann wird
# nach der Landung nur nicht nach einem Namen gefragt.
try:
    import strecken
except ImportError:
    # Der Vermerk unten schweigt mypy: es sieht hier ein Modul, das
    # None wird. Absicht -- so bleiben alle strecken.* Zugriffe weiter
    # geprüft, statt hinter einem ModuleType zu verschwinden.
    strecken = None     # type: ignore[assignment]

# -----------------------------------------------------------------------------
# KONFIGURATION
# -----------------------------------------------------------------------------
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')
HIER = os.path.dirname(os.path.abspath(__file__))

HZ_RATE = 20                # Regel- und Aufzeichnungsrate
TAKT = 1.0 / HZ_RATE

# Steuerung von Hand (wie Recorder 3.2)
DEADZONE = 0.12
EXPO = 1.80
RAMPE = 0.25
# Tempo (3.3). Der Geschwindigkeitsregler der Crazyflie-Firmware
# verlangt 25 Grad Neigung je 1 m/s (PID_VEL_X_KP = 25.0) und darf
# dabei höchstens 20 Grad kippen (PID_VEL_ROLL_MAX = 20.0). Ab
# 20/25 = 0,80 m/s steht er am Anschlag: dann bleibt ihm keine
# Reserve mehr, er schießt über das Soll hinaus und die Drohne
# wippt. 0,80 ist damit die harte Grenze, 0,65 der Arbeitswert mit
# 19 Prozent Luft. Früher stand hier 0,50.
SPEED_SAETTIGUNG = 0.80     # m/s, Firmware-Anschlag: 20 Grad / 25
# 3.4: 0,72 statt 0,65. Mehr ist nicht drin. 0,72 ist genau die 10
# Prozent Reserve unter dem Anschlag, auf die 3.3 sich festgelegt hat:
# sie neigt sich 18 der erlaubten 20 Grad, und die letzten 2 Grad
# braucht der Regler, um bei Bodeneffekt oder Luftzug gegenzuhalten.
# Bei den gewünschten 0,845 (0,65 plus 30 Prozent) läge sie über dem
# Anschlag und würde wippen statt regeln.
MAX_SPEED = 0.72            # m/s
MAX_YAW = 90.0              # Grad/s
STEIG_RATE = 0.45           # m/s
STICK_FREI_ZEIT = 0.50      # s in der Mitte, erst dann gilt Übernahme

START_HOEHE = 0.30
MIN_HOEHE = 0.20
MAX_HOEHE = 1.30

# Rückflug (neu)
RUECK_TEMPO = 0.30          # m/s geradeaus, langsamer als von Hand
RUECK_YAW = 60.0            # Grad/s, höchstens so schnell dreht sie sich
GIER_K = 2.0                # 1/s: 10 Grad daneben ergibt 20 Grad/s
WENDE_WINKEL = 35.0         # Grad daneben: anhalten und erst drehen
WENDE_FERTIG = 15.0         # Grad: fertig gedreht, weiterfahren
VORAUS = 0.30               # m, auf diesen Punkt des Weges zielt die Nase
PFAD_ABSTAND = 0.10         # m zwischen zwei Wegpunkten
SUCH_FENSTER = 15           # Wegpunkte (1,5 m): so weit voraus wird gesucht
QUER_K = 1.0                # 1/s, seitliche Korrektur zum Weg hin
QUER_MAX = 0.08             # m/s
ANKUNFT = 0.25              # m vor dem Startpunkt: nicht mehr drehen, schieben
ENDE_PUNKTE = 3             # so viele Wegpunkte vor dem Ende gilt "am Ende"
FEIN_K = 1.0                # 1/s beim Heranschieben
FEIN_MAX = 0.15             # m/s beim Heranschieben
ZIEL_RADIUS = 0.10          # m, so nah ist "am Startpunkt"
ZIEL_GIER = 8.0             # Grad, so genau ist "in Startrichtung"
FEIN_ZEIT = 15.0            # s für Heranschieben und Drehen, dann landet sie
VERIRRT = 0.80              # m neben dem Weg: landen
VERSPERRT_ZEIT = 3.0        # s vorne blockiert: landen
POS_WEG_ZEIT = 1.0          # s ohne Positionsdaten: landen
LUFT_GRENZE = 0.10          # m, darüber misst das Flow Deck noch sicher
KALMAN_WEG = 0.10           # m, so genau muss der Kalman-Reset sitzen
KALMAN_DREH = 10.0          # Grad, ebenso
KALMAN_ZEIT = 2.0           # s nach dem Reset, so lange wird geprüft
KALMAN_RUHIG = 0.30         # s am Stück am Soll: Reset hat gegriffen
KALMAN_VERSUCHE = 3
PARAM_ACK = 1.0             # s auf die Bestätigung eines Parameters warten
MIN_WEG = 0.30              # m, näher am Start: kein Rückflug nötig
REST_ABSTAND = 0.50         # m, weiter neben dem Weg: kein Weiterfliegen
WENDE_MAX = 8.0             # s am Stück auf der Stelle drehen: landen
ZEIT_PUFFER = 30.0          # s: Rückflug darf Weg/Tempo * 2 + so lange dauern
SCHLEIFE_RADIUS = 0.20      # m: kommt der Weg so nah an sich selbst vorbei,
                            # wird die Schleife dazwischen weggelassen

# Automatisch umkehren (Version 2.0)
UMKEHR_AKKU = 3.25          # V unter Last, so viel soll am Start noch da sein
                            # (2.8: war 3.35, Puffer über AKKU_KRITISCH)
AKKU_RATE_MIN = 0.20 / 60   # V/s, mindestens so schnell fällt der Akku
AKKU_FAKTOR = 1.5           # Reserve: gegen Ende fällt die Spannung schneller
RUECK_EXTRA = 20.0          # s für Wenden, Heranschieben und Landen
UMKEHREN = 'umkehren'       # Grund, mit dem der Hinflug in den Rückflug geht

# Rückflug als gespiegeltes Replay (Version 2.1, nach Recorder 3.2)
# 'spiegel' = deine Aufnahme rückwärts abspielen, 'weg' = Version 2.0
RUECKWEG_ART = 'spiegel'
KORR_K = 1.0                # 1/s: 10 cm daneben ergibt 0,1 m/s zurück
KORR_MAX = 0.20             # m/s, mehr Korrektur gibt es nicht
# Version 4.1: Der Nachfuehrregler schwang. Im Flug 20.09. 19:36 wechselte
# die Drehrichtung im Rueckflug 22 mal in 44 s (Hinflug: 2 mal in 50 s),
# und 21 % der Takte lagen am Anschlag. Ursache: reines P-Glied ohne
# Totzone. Schon 15 Grad Abweichung trieben die Korrektur auf die alten
# 30 Grad/s. Jede dieser Drehungen kostet Position, weil das Flow Deck
# Drehung nicht von Seitwaertsfahrt unterscheiden kann.
GIER_TOT = 8.0              # Grad, darunter wird die Nase nicht korrigiert
GIER_KORR_MAX = 15.0        # Grad/s
STILL_TEMPO = 0.02          # m/s: darunter (und kaum Drehen) stand sie still
STILL_GIER = 2.0            # Grad/s, solche Takte werden übersprungen

# Schutz (wie Recorder 3.2)
NOT_STOPP_ABSTAND = 0.10    # m, darunter: Notlandung
HALTE_ABSTAND = 0.15        # m, hier steht sie
# Der Bremsweg wächst mit dem Tempo, darum ist BREMS_ABSTAND seit 3.3
# aus MAX_SPEED gerechnet statt eine feste Zahl. REAKTION_S deckt
# zweierlei ab: die Trägheit des Befehls (RAMPE = 0.25 bei 20 Hz
# heißt 0,4 s, bis der Bremsbefehl voll anliegt) und das Ausrollen
# danach. Mit MAX_SPEED = 0,50 kommt hier 0,50 m heraus, also genau
# der Wert, der bis Version 3.2 von Hand dastand.
REAKTION_S = 0.70           # s Vorlauf, den sie zum Anhalten braucht
BREMS_ABSTAND = HALTE_ABSTAND + MAX_SPEED * REAKTION_S
if MAX_SPEED > SPEED_SAETTIGUNG:
    raise ValueError(
        'MAX_SPEED = %.2f m/s liegt über dem Anschlag der Firmware '
        '(%.2f m/s). Darüber regelt die Crazyflie die Geschwindigkeit '
        'nicht mehr sauber: sie kippt voll, schießt über das Soll '
        'hinaus und wippt. Nimm einen kleineren Wert.'
        % (MAX_SPEED, SPEED_SAETTIGUNG))
ENG_FOLGE = 2               # so viele VERSCHIEDENE Messungen unter 10 cm

# Türfahrt (Version 2.9). Eine Öffnung hat auf BEIDEN Seiten eine
# Wand, ein Hindernis nur auf einer. Darum sind beide Bedingungen
# nötig, sonst hielte sie jede Zimmerecke für eine Tür.
TUER_SEITEN = ("range.left", "range.right")
TUER_SEITE = 0.90           # m, beide Seiten näher: das ist eine Öffnung
TUER_SUMME = 1.10           # m, links + rechts zusammen höchstens
                            # (Tür 90 cm: die Summe liegt bei etwa 0,90 m)
TUER_REGLER = 0.60          # 1/s, so hart zieht sie zur Mitte
TUER_TEMPO = 0.20           # m/s, mehr nicht zur Seite
TUER_RAND = 0.06            # m, näher am Rahmen: doch Notlandung
ENG_ZEIT = 0.12             # s unter 10 cm (Drohnenzeit): auch Notlandung
SENSOR_MIN = 0.03           # m, kleinere Werte: "ganz nah" oder Ausreißer
NAH_GRENZE = 0.30           # m, war der letzte Wert darunter, war etwas nah
HALTEN_MAX = 1.0            # s, so lange wird ein naher Wert höchstens gehalten
DECKEN_ABSTAND = 0.40       # m, weniger frei nach oben: sinken
DATEN_ALT = 0.5             # s, älter = Sensoren blind
POS_ALT = 0.5               # s, ältere Positionsdaten werden nicht benutzt

# Höhe (wie Recorder 3.2)
SPRUNG = 0.12               # m in einem Takt: Möbelkante unter ihr
VORLAUF = 0.15              # m, beim Steigen höchstens so weit über der Messung
HOEHE_VERLOREN = 0.10       # m, darunter obwohl sie höher soll: Fahrt stoppen

# Akku (wie Recorder 3.2)
# 4.1: AKKU_START von 3,80 auf 4,00 herauf. 3,80 war zu niedrig -- am
# 20.09. startete sie mit 3,95 V ohne jede Warnung und war am Ende des
# Rueckflugs bei 3,60 V, also am Anschlag. Voll sind 4,15 V nach dem
# Abziehen. Es bleibt eine Rueckfrage, kein Verbot: mit 'j' fliegt sie
# trotzdem. Der harte Stopp AKKU_MINIMUM bleibt unveraendert.
AKKU_START = 4.00           # V, darunter Rückfrage
AKKU_MINIMUM = 3.60         # V, darunter kein Start (auch kein Rückflug)
# Im Flug die zwei Schwellen der Firmware (Version 2.8):
AKKU_LEER = 3.20            # V unter Last, Firmware "low": nur Meldung
AKKU_TAKTE = 40             # so viele Messungen hintereinander (2 s)
AKKU_KRITISCH = 3.00        # V unter Last, Firmware "critical":
                            # sofort Notlandung
AKKU_KRITISCH_TAKTE = 10    # so viele hintereinander (0,5 s)

# Start und Landung
ABHEBE_TEMPO = 0.30         # m/s
SINK_TEMPO = 0.30           # m/s
SINK_TEMPO_NOT = 0.50       # m/s
BODEN = 0.07                # m, darunter gilt sie als gelandet
LAGE_HOCH = 0.10            # m, darüber gilt sie als vom Boden weg
BODEN_NACHLAUF = 1.5        # s, danach Motoren aus, auch ohne Bodenmessung
COUNTDOWN_HIN = 3
COUNTDOWN_RUECK = 3

# Funk (Version 2.2)
NEU_VERSUCHE = 10           # so oft neu verbinden, wenn am Boden der Funk reißt
NEU_PAUSE = 2.0             # s zwischen zwei Versuchen
START_VERSUCHE = 3          # so oft den Start nach Funkabbruch wiederholen
PARAM_WARTEN = 10.0         # s, so lange nach dem Verbinden auf Parameter warten
FUNK_SCHWACH = 70.0         # %, darunter Warnung

# Xbox-Controller unter pygame 2.6
KNOPF_A = 0
KNOPF_B = 1
KNOPF_START = 7
ACHSEN = {'drehen': (0, -1), 'hoehe': (1, -1),
          'seit': (2, -1), 'vor': (3, -1)}

SEITEN = [('range.front', 'vorne'), ('range.back', 'hinten'),
          ('range.left', 'links'), ('range.right', 'rechts')]
ALLE_SENSOREN = SEITEN + [('range.up', 'oben'), ('range.zrange', 'unten')]
GEFILTERT = SEITEN + [('range.up', 'oben')]
POS_VARIABLEN = ('stateEstimate.x', 'stateEstimate.y', 'stateEstimate.yaw')

# Qualität der Bodenkamera (Version 3.0). NUR zum Mitschreiben, nie
# zum Steuern. Die Reihenfolge muss zu den letzten drei Spalten in
# CSV_KOPF passen.
FLOW_VARIABLEN = ('motion.shutter', 'motion.squal', 'motion.maxRaw')
FLOW_TAKT = 200             # ms, langsam: die Funkstrecke bleibt frei
FLOW_SQUAL_SCHWACH = 30     # darunter arbeitet die Kamera dünn
FLOW_SQUAL_BLIND = 5        # darunter sieht sie überhaupt nichts

CSV_KOPF = ['t_s', 'phase', 'vx_ms', 'vy_ms', 'gier_grad_s', 'z_soll_m',
            'z_ist_m', 'z_gesendet_m', 'x_m', 'y_m', 'gier_ist_grad',
            'vbat_v', 'vorne_m', 'hinten_m', 'links_m', 'rechts_m', 'oben_m',
            'unten_m', 'gebremst', 'moebel_m', 'neben_weg_m', 'rest_m',
            'shutter', 'squal', 'max_raw']


# -----------------------------------------------------------------------------
# AUSGABE UND KLEINKRAM
# -----------------------------------------------------------------------------
_zeilen: list[str] = []


def sag(text=''):
    """Druckt auf den Bildschirm und merkt sich die Zeile für die Datei."""
    print(text, flush=True)
    _zeilen.append(text)


def zahl(wert, form='%.2f'):
    return '-' if wert is None else form % wert


def begrenzt(wert: float, grenze: float) -> float:
    return max(-grenze, min(grenze, wert))


def wrap(winkel: float) -> float:
    """Winkel in Grad auf -180 .. +180, damit 350 Grad als -10 zählt."""
    return ((winkel + 180.0) % 360.0) - 180.0


def roh_m(mm):
    """Rohwert des Multi-Rangers in m, None ab 8 m (32767 = nichts oder
    ungültig)."""
    if mm is None or mm >= 8000:
        return None
    return mm / 1000.0


def arm(cf, an):
    """Wie im Recorder. Der Armingstatus wird NIE als Startbedingung
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


class Ende(Exception):
    """Der Rückflug ist zu Ende (angekommen oder aufgegeben). Sie landet."""


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
# DER RÜCKWEG (reine Rechnerei, ohne Drohne prüfbar: tests/test_heimweg.py)
# -----------------------------------------------------------------------------
Punkt = tuple[float, float, float]      # x, y, Höhe über dem Fußboden


def rueckweg_bauen(spur: list[tuple[float, float, float, float]],
                   abstand: float = PFAD_ABSTAND) -> list[Punkt]:
    """Macht aus der Spur des Hinflugs (x, y, z, yaw je Takt) den Rückweg.

    Ein Wegpunkt alle `abstand` Meter, dann umgedreht. Der letzte Punkt
    ist genau der Startpunkt (0, 0), nicht der erste Spurpunkt: Beim
    Abheben verrutscht sie oft ein paar Zentimeter."""
    if not spur:
        return []
    z_start = max(MIN_HOEHE, spur[0][2])
    punkte: list[Punkt] = [(0.0, 0.0, z_start)]
    for x, y, z, _yaw in spur:
        lx, ly, _lz = punkte[-1]
        if math.hypot(x - lx, y - ly) >= abstand:
            punkte.append((x, y, max(MIN_HOEHE, min(MAX_HOEHE, z))))
    # Der Landepunkt selbst gehört dazu, auch wenn er nah am letzten liegt
    x, y, z, _yaw = spur[-1]
    if (x, y) != punkte[-1][:2]:
        punkte.append((x, y, max(MIN_HOEHE, min(MAX_HOEHE, z))))
    punkte.reverse()
    return punkte


def weglaenge(punkte: list[Punkt]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(punkte, punkte[1:], strict=False))


def schleifen_kuerzen(punkte: list[Punkt],
                      radius: float = SCHLEIFE_RADIUS) -> list[Punkt]:
    """Lässt Schleifen und Umwege weg. Von jedem Punkt springt der Weg zum
    SPÄTESTEN Punkt, der näher als `radius` liegt. Sie fliegt also nur über
    Stellen, an denen du schon warst, aber jede nur einmal. Erster und
    letzter Punkt (Landepunkt und Start) bleiben immer."""
    n = len(punkte)
    if n < 3:
        return list(punkte)
    aus = [punkte[0]]
    i = 0
    while i < n - 1:
        j = i + 1
        for k in range(n - 1, i + 1, -1):
            if math.hypot(punkte[k][0] - punkte[i][0],
                          punkte[k][1] - punkte[i][1]) < radius:
                j = k
                break
        aus.append(punkte[j])
        i = j
    return aus


def rueckzeit(punkte: list[Punkt]) -> float:
    """So lange dauert der Rückflug ungefähr, in s."""
    return weglaenge(punkte) / RUECK_TEMPO + RUECK_EXTRA


def umkehren_noetig(v_jetzt: float, rate: float, t_rueck: float) -> bool:
    """True, wenn der Akku nach dem Rückflug unter UMKEHR_AKKU fiele.
    rate = gemessener Spannungsabfall in V/s (unter Last)."""
    rate = max(rate, AKKU_RATE_MIN)
    return v_jetzt - AKKU_FAKTOR * rate * t_rueck < UMKEHR_AKKU


class Heimweg:
    """Führt die Drohne den Rückweg entlang, Nase in Fahrtrichtung.

    Jeden Takt: schritt(x, y, yaw) mit der Position aus dem Kalman.
    Heraus kommt (vx, vy, gier, z, neben_weg) im Körper der Drohne, so
    wie send_hover_setpoint es will. vx ist nie negativ: Sie fährt nie
    rückwärts, sie dreht sich lieber erst.

    Phasen:
      fahrt       dem Weg folgen. Die Nase zeigt auf einen Punkt VORAUS
                  Meter weiter vorn. Ist die Nase mehr als WENDE_WINKEL
                  daneben (Ecke), bleibt sie stehen und dreht sich erst.
      ankommen    die letzten ANKUNFT Meter: nicht mehr drehen, nur zum
                  Startpunkt schieben (sonst dreht sie sich über dem
                  Ziel im Kreis).
      ausrichten  über dem Startpunkt in die Startrichtung drehen.
      fertig      landen."""

    def __init__(self, punkte: list[Punkt], start_gier: float = 0.0):
        self.p = punkte
        self.start_gier = start_gier
        self.i = 0                  # nächster Wegpunkt, läuft nur vorwärts
        self.phase = 'fahrt'
        self.wendet = False
        self.fein_takte = 0
        self.zeit_um = False        # Heranschieben hat zu lange gedauert

    def _naechster(self, x: float, y: float) -> float:
        """Sucht den nächsten Wegpunkt, aber nur ab dem letzten und
        höchstens SUCH_FENSTER weiter. So nimmt sie keine Abkürzung,
        wenn der Weg sich selbst kreuzt."""
        ende = min(len(self.p), self.i + SUCH_FENSTER + 1)
        bester = min(range(self.i, ende),
                     key=lambda k: math.hypot(self.p[k][0] - x, self.p[k][1] - y))
        self.i = bester
        return math.hypot(self.p[bester][0] - x, self.p[bester][1] - y)

    def _voraus(self, x: float, y: float) -> Punkt:
        for k in range(self.i, len(self.p)):
            if math.hypot(self.p[k][0] - x, self.p[k][1] - y) >= VORAUS:
                return self.p[k]
        return self.p[-1]

    def rest(self, x: float, y: float) -> float:
        """Wie viel Weg noch vor ihr liegt, in m."""
        return (math.hypot(self.p[self.i][0] - x, self.p[self.i][1] - y)
                + weglaenge(self.p[self.i:]))

    def schritt(self, x: float, y: float, yaw: float
                ) -> tuple[float, float, float, float, float]:
        neben = self._naechster(x, y)
        zx, zy, zz = self.p[-1]
        ex, ey = zx - x, zy - y
        bis_ziel = math.hypot(ex, ey)
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

        if self.phase == 'fahrt':
            am_ende = len(self.p) - 1 - self.i <= ENDE_PUNKTE
            if am_ende and bis_ziel < ANKUNFT:
                self.phase = 'ankommen'

        if self.phase == 'fahrt':
            z = self.p[self.i][2]
            vx_p, vy_p, _vz = self._voraus(x, y)
            dx, dy = vx_p - x, vy_p - y
            fehler = wrap(math.degrees(math.atan2(dy, dx)) - yaw)
            # Positive Gierrate = gegen den Uhrzeigersinn = yaw steigt
            # (an den Aufnahmen vom 14.09.2026 nachgeprüft)
            gier = begrenzt(GIER_K * fehler, RUECK_YAW)
            if abs(fehler) > WENDE_WINKEL:
                self.wendet = True
            elif abs(fehler) < WENDE_FERTIG:
                self.wendet = False
            if self.wendet:
                return 0.0, 0.0, gier, z, neben
            vx = RUECK_TEMPO * math.cos(math.radians(fehler))
            # Punkt voraus aus dem Raum in den Körper der Drohne drehen,
            # der seitliche Anteil zieht sie sanft auf den Weg
            quer = -s * dx + c * dy
            vy = begrenzt(QUER_K * quer, QUER_MAX)
            return vx, vy, gier, z, neben

        # ankommen und ausrichten: zum Startpunkt schieben, im Körper
        self.fein_takte += 1
        vx = begrenzt(FEIN_K * (c * ex + s * ey), FEIN_MAX)
        vy = begrenzt(FEIN_K * (-s * ex + c * ey), FEIN_MAX)
        gier = 0.0
        if self.phase == 'ankommen' and bis_ziel < ZIEL_RADIUS:
            self.phase = 'ausrichten'
        if self.phase == 'ausrichten':
            fehler = wrap(self.start_gier - yaw)
            gier = begrenzt(GIER_K * fehler, RUECK_YAW)
            if abs(fehler) < ZIEL_GIER and bis_ziel < 1.5 * ZIEL_RADIUS:
                self.phase = 'fertig'
        if self.phase != 'fertig' and self.fein_takte * TAKT > FEIN_ZEIT:
            self.phase = 'fertig'
            self.zeit_um = True
        return vx, vy, gier, zz, neben

    def zeitgrenze(self) -> float:
        """So lange darf der Rückflug höchstens dauern, in s."""
        return 2.0 * weglaenge(self.p) / RUECK_TEMPO + ZEIT_PUFFER


# -----------------------------------------------------------------------------
# Phasen, in denen das Skript selbst fliegt (Rückflug und Nachflug)
AUTO_PHASEN = ('rueck', 'nach')
# Phasen, die aufgezeichnet werden und aus denen der Rückflug entsteht
HIN_PHASEN = ('hin', 'nach')


# -----------------------------------------------------------------------------
# RÜCKFLUG ALS GESPIEGELTES REPLAY (Version 2.1)
# -----------------------------------------------------------------------------
# Ein Bild je Takt des Hinflugs: gesendete Befehle und gemessene Lage,
# genau wie eine Zeile der Aufnahme im Recorder 3.2.
Bild = tuple[float, float, float, float,            # vx, vy, gier, z_soll
             float | None, float | None, float | None]  # x, y, yaw


def spiegel_bauen(bilder: list[Bild]) -> list[Bild]:
    """Dreht die Aufnahme des Hinflugs um: letzter Takt zuerst.

    Warum das mit der Nase voraus geht: Zeigt die Nase um 180 Grad
    gedreht, bringt DIESELBE Fahrt (vx, vy im Körper) sie genau in die
    Gegenrichtung. Nur die Drehrichtung muss umgedreht werden. Wer beim
    Hinflug vorwärts geflogen ist, fliegt also auch zurück vorwärts.

    Takte, in denen sie nur stand, fallen weg (spart Akku)."""
    aus: list[Bild] = []
    z_vorher: float | None = None
    for vx, vy, gier, z, x, y, yaw in reversed(bilder):
        still = (abs(vx) < STILL_TEMPO and abs(vy) < STILL_TEMPO
                 and abs(gier) < STILL_GIER)
        if still and z_vorher is not None and abs(z - z_vorher) < 0.005:
            continue
        z_vorher = z
        aus.append((vx, vy, -gier, z, x, y,
                    None if yaw is None else wrap(yaw + 180.0)))
    return aus


def vorwaerts_bauen(bilder: list[Bild]) -> list[Bild]:
    """Die Aufnahme zum Nachfliegen: gleiche Reihenfolge, gleiche Fahrt,
    gleiche Richtung. Nur Takte, in denen sie stand, fallen weg."""
    aus: list[Bild] = []
    z_vorher: float | None = None
    for bild in bilder:
        vx, vy, gier, z = bild[0], bild[1], bild[2], bild[3]
        still = (abs(vx) < STILL_TEMPO and abs(vy) < STILL_TEMPO
                 and abs(gier) < STILL_GIER)
        if still and z_vorher is not None and abs(z - z_vorher) < 0.005:
            continue
        z_vorher = z
        aus.append(bild)
    return aus


def bilder_versetzen(bilder: list[Bild], dx: float, dy: float,
                     dreh_grad: float) -> list[Bild]:
    """Legt eine Aufnahme an eine andere Stelle im Raum: erst um
    dreh_grad um den Nullpunkt gedreht, dann um (dx, dy) geschoben.

    Gedreht und geschoben werden nur die aufgezeichneten Positionen
    x, y und die Blickrichtung. Die Fahrbefehle vx, vy und die Drehrate
    bleiben unangetastet: die gelten im Rahmen der Drohne selbst.
    Fliegt sie dieselbe Folge von Befehlen aus einer anderen Richtung
    los, kommt dieselbe Figur heraus, nur gedreht -- genau das wollen
    wir hier."""
    s = math.sin(math.radians(dreh_grad))
    c = math.cos(math.radians(dreh_grad))
    aus: list[Bild] = []
    for vx, vy, gier, z, x, y, yaw in bilder:
        neu_yaw = None if yaw is None else wrap(yaw + dreh_grad)
        if x is None or y is None:
            aus.append((vx, vy, gier, z, None, None, neu_yaw))
        else:
            aus.append((vx, vy, gier, z,
                        dx + c * x - s * y,
                        dy + s * x + c * y,
                        neu_yaw))
    return aus


def bilder_ketten(teile: list[list[Bild]]) -> list[Bild]:
    """Hängt mehrere Aufnahmen zu einem Weg zusammen.

    Jede Aufnahme fängt in ihrer eigenen Datei bei x = y = 0 an. Die
    zweite wird deshalb dorthin versetzt, wo die erste aufgehört hat,
    und so gedreht, dass sie in die Richtung weiterläuft, in die die
    Drohne am Ende der ersten schaut. Ohne das führe der Weg an der
    Nahtstelle zurück zum Nullpunkt, und die Wegkorrektur zöge die
    Drohne quer durch den Raum.

    Teile ohne Wegdaten werden angehängt, wie sie sind -- versetzen
    lässt sich nur, was Positionen hat."""
    aus: list[Bild] = []
    for teil in teile:
        if not teil:
            continue
        if not aus:
            aus.extend(teil)
            continue
        ende, anfang = letzte_lage(aus), erste_lage(teil)
        if ende is None or anfang is None:
            aus.extend(teil)
            continue
        dreh = wrap(ende[2] - anfang[2])
        s = math.sin(math.radians(dreh))
        c = math.cos(math.radians(dreh))
        aus.extend(bilder_versetzen(
            teil,
            ende[0] - (c * anfang[0] - s * anfang[1]),
            ende[1] - (s * anfang[0] + c * anfang[1]),
            dreh))
    return aus


def spannweite(bilder: list[Bild]) -> tuple[float, float]:
    """Wie weit der Weg in x und y auseinanderläuft, in Metern. Für die
    Frage, ob ein mehrfach gefahrener Weg noch in den Raum passt."""
    punkte = [(b[4], b[5]) for b in bilder
              if b[4] is not None and b[5] is not None]
    if not punkte:
        return 0.0, 0.0
    xs = [p[0] for p in punkte]
    ys = [p[1] for p in punkte]
    return max(xs) - min(xs), max(ys) - min(ys)


def _feld(zeile: dict, name: str) -> float | None:
    wert = (zeile.get(name) or '').strip()
    return float(wert) if wert else None


def hinflug_laden(pfad: str, phasen: tuple[str, ...] = ('hin',)
                  ) -> list[Bild]:
    """Liest die Hinflug-Zeilen aus heim_hin_*.csv als Bilder (oder die
    Zeilen der `phasen`). Werte werden auf die Grenzen dieses Skripts
    geklemmt."""
    bilder: list[Bild] = []
    try:
        with open(pfad, newline='', encoding='utf-8') as f:
            for zeile in csv.DictReader(f, delimiter=';'):
                if zeile.get('phase') not in phasen:
                    continue
                try:
                    bilder.append((
                        begrenzt(float(zeile['vx_ms']), MAX_SPEED),
                        begrenzt(float(zeile['vy_ms']), MAX_SPEED),
                        begrenzt(float(zeile['gier_grad_s']), MAX_YAW),
                        max(MIN_HOEHE, min(MAX_HOEHE,
                                           float(zeile['z_soll_m']))),
                        _feld(zeile, 'x_m'), _feld(zeile, 'y_m'),
                        _feld(zeile, 'gier_ist_grad')))
                except (KeyError, TypeError, ValueError):
                    continue
    except OSError:
        return []
    return bilder


def letzte_lage(bilder: list[Bild]) -> tuple[float, float, float] | None:
    """Letzte aufgezeichnete Position (x, y, yaw) oder None."""
    for b in reversed(bilder):
        if b[4] is not None and b[5] is not None and b[6] is not None:
            return b[4], b[5], b[6]
    return None


def erste_lage(bilder: list[Bild]) -> tuple[float, float, float] | None:
    """Erste aufgezeichnete Position (x, y, Blickrichtung) oder None."""
    for b in bilder:
        if b[4] is not None and b[5] is not None and b[6] is not None:
            return b[4], b[5], b[6]
    return None


def start_richtung(bilder: list[Bild]) -> float | None:
    """Richtung am Startpunkt: die erste aufgezeichnete."""
    return next((b[6] for b in bilder if b[6] is not None), None)


def rest_rueckweg(bilder: list[Bild], x: float, y: float
                  ) -> tuple[list[Bild], float]:
    """Rückweg ab der Stelle (x, y), an der sie gelandet ist (Version
    2.6): der gespiegelte Hinflug ab dem Bild, das (x, y) am nächsten
    liegt. Gibt (Bilder, Abstand zu diesem Bild in m) zurück."""
    gespiegelt = spiegel_bauen(bilder)
    beste, abstand = 0, math.inf
    for i, b in enumerate(gespiegelt):
        if b[4] is None or b[5] is None:
            continue
        d = math.hypot(b[4] - x, b[5] - y)
        if d < abstand:
            beste, abstand = i, d
    return gespiegelt[beste:], abstand


LAGE_KOPF = ['x_m', 'y_m', 'gier_grad']


def lage_speichern(pfad: str,
                   pos: tuple[float, float, float] | None) -> None:
    """Merkt sich, wo sie gelandet ist (für Menü 3, Version 2.6).
    pos = None: in der Luft, Lage unbekannt. Das wird geschrieben, sobald
    sie vom Boden weg ist (seit 2.7 nicht mehr schon beim Abheben), und
    bleibt stehen, wenn sie nicht sauber landet (Not-Aus, Funkabbruch in
    der Luft)."""
    try:
        with open(pfad, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(LAGE_KOPF)
            if pos is None:
                w.writerow(['', '', ''])
            else:
                w.writerow(['%.3f' % pos[0], '%.3f' % pos[1],
                            '%.2f' % pos[2]])
    except OSError as e:
        sag('  Landeposition nicht gespeichert: %s' % e)


def lage_lesen(pfad: str) -> tuple[float, float, float] | None:
    """Landeposition (x, y, Grad) aus heim_lande_*.csv, None =
    unbekannt."""
    try:
        with open(pfad, newline='', encoding='utf-8') as f:
            zeile = list(csv.DictReader(f, delimiter=';'))[-1]
        x = _feld(zeile, 'x_m')
        y = _feld(zeile, 'y_m')
        g = _feld(zeile, 'gier_grad')
    except (OSError, IndexError, ValueError):
        return None
    if x is None or y is None or g is None:
        return None
    return x, y, g


def letzter_flug(ordner: str) -> str | None:
    """Der neueste Hin- oder Nachflug (heim_hin_*.csv, heim_nach_*.csv)."""
    dateien = (glob.glob(os.path.join(ordner, 'heim_hin_*.csv'))
               + glob.glob(os.path.join(ordner, 'heim_nach_*.csv')))
    return max(dateien, key=os.path.getmtime, default=None)


def spiegel_zeit(bilder: list[Bild]) -> float:
    """So lange dauert der gespiegelte Rückflug ungefähr, in s."""
    return len(spiegel_bauen(bilder)) * TAKT + RUECK_EXTRA


class Spiegel:
    """Spielt die gespiegelte Aufnahme ab, mit Wegkorrektur wie im Replay
    des Recorders 3.2. Gleiche Schnittstelle wie Heimweg.

    Phasen:
      wenden       auf der Stelle um 180 Grad drehen (Nase Richtung Heimweg)
      nachfliegen  die Aufnahme rückwärts abspielen, jeden Takt sanft auf
                   den aufgezeichneten Weg zurückziehen
      ankommen     zum Startpunkt schieben (was die Korrektur nicht ganz
                   geschafft hat)
      ausrichten   über dem Startpunkt in die Startrichtung drehen
      fertig       landen

    ziel: Endpunkt (x, y). Rückflug: der Startpunkt (0, 0). Nachflug:
    der letzte Punkt der Aufnahme. start_gier ist die Richtung dort."""

    def __init__(self, bilder: list[Bild], start_gier: float = 0.0,
                 ziel: tuple[float, float] = (0.0, 0.0)):
        self.b = bilder
        self.start_gier = start_gier
        self.ziel = ziel
        self.k = 0                  # nächstes Bild
        self.fein_takte = 0
        self.zeit_um = False

        # Lage je Bild (fehlt sie, gilt die davor), daraus der Restweg
        lagen: list[tuple[float, float]] = []
        for _vx, _vy, _g, _z, x, y, _yaw in bilder:
            if x is not None and y is not None:
                lagen.append((x, y))
            else:
                lagen.append(lagen[-1] if lagen else (0.0, 0.0))
        self.z_ende = bilder[-1][3] if bilder else MIN_HOEHE
        self.p: list[Punkt] = [(x, y, b[3]) for (x, y), b in zip(
            lagen, bilder, strict=True)] + [(ziel[0], ziel[1], self.z_ende)]
        self.rest_ab = [0.0] * (len(self.p))
        for i in range(len(self.p) - 2, -1, -1):
            a, b2 = self.p[i], self.p[i + 1]
            self.rest_ab[i] = (self.rest_ab[i + 1]
                               + math.hypot(b2[0] - a[0], b2[1] - a[1]))

        self.halt = lagen[0] if lagen else (0.0, 0.0)
        # Tempogrenze fürs Abspielen (3.4). Bis 3.3 stand hier MAX_SPEED.
        # Das war falsch: MAX_SPEED gilt für den Stick in deiner Hand, im
        # Replay deckelte es die Summe aus abgespielter Fahrt UND
        # Wegkorrektur. Zog MAX_SPEED hoch, wurde der Rückflug schneller,
        # als der Hinflug je war — am 20.09. flog sie zurück 0,65, obwohl
        # die Aufnahme nur 0,51 enthielt. Jetzt richtet sich der Deckel
        # nach der Aufnahme: schneller als ihr schnellster Takt wird der
        # Rückflug nicht. Die Wegkorrektur wird dann mitskaliert -- ihre
        # Richtung bleibt erhalten, nur der Betrag sinkt. Genau so hat es
        # 3.2 gemacht (Deckel 0,50 bei einer Aufnahme mit 0,51), und der
        # Flug vom 20.09. 15:15 landete damit 8 cm neben dem Start.
        # Die Untergrenze KORR_MAX + 0,10 gilt nur für sehr langsame
        # Aufnahmen, damit die Korrektur dort nicht erstickt.
        auf_max = max((math.hypot(b[0], b[1]) for b in bilder), default=0.0)
        self.deckel = min(max(auf_max, KORR_MAX + 0.10), MAX_SPEED)
        self.ziel_gier = next((b[6] for b in bilder if b[6] is not None), None)
        self.phase = 'wenden' if self.ziel_gier is not None else 'nachfliegen'
        self.wendet = self.phase == 'wenden'
        if not bilder:
            self.phase = 'ankommen'
            self.wendet = False

    def rest(self, x: float, y: float) -> float:
        if self.phase in ('wenden', 'nachfliegen'):
            return self.rest_ab[min(self.k, len(self.rest_ab) - 1)]
        return math.hypot(self.ziel[0] - x, self.ziel[1] - y)

    def zeitgrenze(self) -> float:
        return 1.5 * len(self.b) * TAKT + ZEIT_PUFFER + FEIN_ZEIT

    def schritt(self, x: float, y: float, yaw: float
                ) -> tuple[float, float, float, float, float]:
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

        if self.phase == 'wenden' and self.ziel_gier is not None:
            hx, hy = self.halt
            ex, ey = hx - x, hy - y
            fehler = wrap(self.ziel_gier - yaw)
            if abs(fehler) >= WENDE_FERTIG:
                vx = begrenzt(FEIN_K * (c * ex + s * ey), FEIN_MAX)
                vy = begrenzt(FEIN_K * (-s * ex + c * ey), FEIN_MAX)
                # Positive Gierrate = gegen den Uhrzeigersinn = yaw steigt
                gier = begrenzt(GIER_K * fehler, RUECK_YAW)
                return vx, vy, gier, self.b[0][3], math.hypot(ex, ey)
            self.phase = 'nachfliegen'
            self.wendet = False

        if self.phase == 'nachfliegen':
            if self.k < len(self.b):
                return self._abspielen(x, y, yaw, c, s)
            self.phase = 'ankommen'

        # ankommen und ausrichten: zum Ziel schieben, im Körper
        self.fein_takte += 1
        ex, ey = self.ziel[0] - x, self.ziel[1] - y
        bis_ziel = math.hypot(ex, ey)
        vx = begrenzt(FEIN_K * (c * ex + s * ey), FEIN_MAX)
        vy = begrenzt(FEIN_K * (-s * ex + c * ey), FEIN_MAX)
        gier = 0.0
        if self.phase == 'ankommen' and bis_ziel < ZIEL_RADIUS:
            self.phase = 'ausrichten'
        if self.phase == 'ausrichten':
            fehler = wrap(self.start_gier - yaw)
            gier = begrenzt(GIER_K * fehler, RUECK_YAW)
            if abs(fehler) < ZIEL_GIER and bis_ziel < 1.5 * ZIEL_RADIUS:
                self.phase = 'fertig'
        if self.phase != 'fertig' and self.fein_takte * TAKT > FEIN_ZEIT:
            self.phase = 'fertig'
            self.zeit_um = True
        return vx, vy, gier, self.z_ende, bis_ziel

    def _abspielen(self, x: float, y: float, yaw: float, c: float, s: float
                   ) -> tuple[float, float, float, float, float]:
        """Ein Takt Replay mit Wegkorrektur (wie wegkorrektur() im
        Recorder 3.2). Soll-Lage ist die zu BEGINN dieses Takts, also
        die des Bildes davor."""
        vx, vy, gier, z, _x, _y, _yaw = self.b[self.k]
        _v1, _v2, _g, _z, xa, ya, yawa = self.b[max(0, self.k - 1)]
        self.k += 1
        if xa is None or ya is None or yawa is None:
            return vx, vy, gier, z, 0.0
        d_gier = wrap(yawa - yaw)
        ex, ey = xa - x, ya - y
        # Zeigt sie um d_gier anders als geplant: Fahrt mitdrehen, damit
        # sie im Raum dieselbe Richtung nimmt
        cd, sd = math.cos(math.radians(d_gier)), math.sin(math.radians(d_gier))
        vx2 = cd * vx - sd * vy
        vy2 = sd * vx + cd * vy
        # Wegfehler aus dem Raum in den Körper drehen
        vx2 += begrenzt(KORR_K * (c * ex + s * ey), KORR_MAX)
        vy2 += begrenzt(KORR_K * (-s * ex + c * ey), KORR_MAX)
        betrag = math.hypot(vx2, vy2)
        if betrag > self.deckel:
            vx2 *= self.deckel / betrag
            vy2 *= self.deckel / betrag
        # Grenze ist RUECK_YAW, nicht MAX_YAW (3.2). MAX_YAW = 90 Grad/s
        # ist die Grenze fuer den Stick in deiner Hand. Im Alleinflug
        # gilt ueberall sonst RUECK_YAW = 60 Grad/s; nur hier stand die
        # Handgrenze. Im Flug 20.09. 14:49 drehte sie deshalb in 14 %
        # der Takte mit 85 bis 90 Grad/s.
        # Totzone (4.1): unter GIER_TOT gar nicht korrigieren. Abgezogen
        # statt hart abgeschnitten, damit die Korrektur an der Kante bei
        # null anfaengt und nicht springt -- ein Sprung waere genau das
        # Zappeln, das hier weg soll. Bei 8 Grad also 0, bei 9 Grad 2 Grad/s.
        if abs(d_gier) < GIER_TOT:
            korr = 0.0
        else:
            korr = begrenzt(
                GIER_K * (d_gier - math.copysign(GIER_TOT, d_gier)),
                GIER_KORR_MAX)
        gier2 = begrenzt(gier + korr, RUECK_YAW)
        return vx2, vy2, gier2, z, math.hypot(ex, ey)


# -----------------------------------------------------------------------------
# DIE DROHNE
# -----------------------------------------------------------------------------
class FlowRanger:
    def __init__(self, pad):
        self.pad = pad
        self.cf = None
        self.lg = None
        self.lg_pos = None
        self.lg_flow = None         # Qualität der Bodenkamera (3.0)
        self.nullpunkt = {}
        self.glatt = {'vor': 0.0, 'seit': 0.0, 'dreh': 0.0, 'hoch': 0.0}

        # Wird von den Log-Callbacks (eigener Thread der cflib) beschrieben
        self.d = {}                 # Rohwerte
        self.flow = {}              # letzte Kamerawerte (3.0)
        self.flow_squal = []        # squal im Flug, für den Bericht
        self.flow_shutter = []      # shutter im Flug
        self.flow_gemeldet = False  # Warnung "sieht schlecht" kam schon
        self.d_zeit = 0.0
        self.d_fw = 0.0             # Zeitstempel der Drohne in s
        self.roh = {}
        self.gef = {}               # gefilterter Abstand in m oder None
        self.gef_zeit = {}
        self.nah = {name: 0 for name, _ in SEITEN}
        self.nah_seit = {name: None for name, _ in SEITEN}
        self.nah_wert = {name: None for name, _ in SEITEN}
        self.akku_leer = 0
        self.akku_kritisch = 0      # Takte unter AKKU_KRITISCH (2.8)
        self.tuer_gemeldet = False  # Meldung "in der Tür" kam schon
        self.akku_leer_gewarnt = False  # Meldung bei 3,20 V kam schon
        self.funk_weg = False
        self.funk_weg_in_luft = False   # beim Abbruch in der Luft?
        self.funk_q = None              # Funkqualität in %
        self.funk_neu = 0               # so oft neu verbunden
        self.scf = None
        self.z_vorher = None
        self.sprung_summe = 0.0
        self.pos = None             # (x, y, yaw)
        self.pos_zeit = 0.0

        self.in_luft = False
        self.gesperrt = False       # Not-Aus: erst aus- und einschalten
        self.z_soll = 0.0           # Höhe über dem Fußboden
        self.z_gesendet = 0.0
        self.moebel_gemeldet = 0.0
        self.hoehe_weg = False
        self.akku_anfang = None

        # Hinflug-Spur und Rückflug
        self.spur = []              # (x, y, z_soll, yaw) je Takt im Hinflug
        self.bilder = []            # Bild je Takt im Hinflug (für Spiegel)
        self.heim = None            # Heimweg während des Rückflugs
        self.ziel_name = 'Startpunkt'   # für die Ende-Meldung
        self.uebernommen = False    # Stick bewegt: Du steuerst
        self.pos_weg_seit = None
        self.luft_pos = None        # Position kurz vor dem Aufsetzen
        self.lande_datei = None     # heim_lande_<Zeit>.csv (Version 2.6)
        self.lage_offen = False     # abgehoben, aber noch nicht als
                                    # unbekannt vermerkt (2.7)
        self.start_gier = None      # Richtung am Startpunkt (Grad)
        self.stick_frei = False     # erst nach dem Loslassen gilt Übernahme
        self.stick_mitte_seit = None    # seit wann in der Mitte (2.7)
        self.rueck_in_luft = False  # in der Luft umgekehrt, ohne Landung
        # Menü 5: nur aufzeichnen. Dann landet sie am Ende, statt
        # zurückzufliegen -- auch bei Taste A und bei knappem Akku.
        self.ohne_rueckflug = False
        self.vbat_letzte = deque(maxlen=40)     # 2 s Akkuwerte
        self.akku_kurve = []        # (t, Mittelwert) je Sekunde im Hinflug
        self.rueck_info = None      # (Volt, V/s, Rückflugzeit s)
        self.akku_gewarnt = False
        self.heim_start = None
        self.wende_seit = None
        self.neben_jetzt = None
        self.rest_jetzt = None
        self.stat = {}
        self.stat_neu()

    def stat_neu(self):
        self.stat = {'takte': 0, 'gebremst': 0, 'decke': 0,
                     'hoehe_weg': 0, 'moebel_max': 0.0,
                     'neben_max': 0.0, 'wenden': 0,
                     'min': {name: None for name, _ in SEITEN},
                     'dauer': 0.0}
        # Die Kamerawerte gehören zum Abschnitt, nicht zum ganzen
        # Flug (3.1). Ohne das stand im Rückflugbericht der Hinflug
        # mit drin.
        self.flow_squal = []
        self.flow_shutter = []
        self.flow_gemeldet = False

    # ------------------------------------------------------------ Sensoren
    def _filtern(self, name, mm, jetzt):
        """Wie Recorder 3.2: Gibt (Abstand in m oder None, gehalten) zurück.
        32767 mm heißt "nichts" ODER "zu nah". War der letzte Wert nah,
        wird er deshalb bis HALTEN_MAX gehalten."""
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
            return SENSOR_MIN, False
        return m, False

    def _empfangen(self, zeitstempel, daten, konf):
        jetzt = time.time()
        fw = zeitstempel / 1000.0
        for name, _ in GEFILTERT:
            mm = daten.get(name)
            if mm is None:
                continue
            neu = mm != self.roh.get(name)
            self.roh[name] = mm
            m, gehalten = self._filtern(name, mm, jetzt)
            self.gef[name] = m
            if not gehalten:
                self.gef_zeit[name] = jetzt
            if name == 'range.up':
                continue
            if m is not None and m < NOT_STOPP_ABSTAND:
                seit = self.nah_seit[name]
                if seit is None or fw < seit:
                    self.nah_seit[name] = fw
                if neu and not gehalten:
                    self.nah[name] += 1
                self.nah_wert[name] = m
            else:
                self.nah[name] = 0
                self.nah_seit[name] = None
        self.d.update(daten)
        self.d_zeit = jetzt
        self.d_fw = fw

        z = daten.get('stateEstimate.z')
        if z is not None:
            if (self.in_luft and self.z_vorher is not None
                    and abs(z - self.z_vorher) > SPRUNG):
                self.sprung_summe += z - self.z_vorher
            self.z_vorher = z

        v = daten.get('pm.vbat')
        if v is not None and v > 0.5 and self.in_luft:
            self.vbat_letzte.append(v)
        if v is not None and 0.5 < v < AKKU_LEER:
            self.akku_leer += 1
        else:
            self.akku_leer = 0
        if v is not None and 0.5 < v < AKKU_KRITISCH:
            self.akku_kritisch += 1
        else:
            self.akku_kritisch = 0

    def _flow_empfangen(self, zeitstempel, daten, konf):
        """Qualität der Bodenkamera. Nur merken, sonst nichts: Diese
        Werte greifen nirgends ins Fliegen ein. Gesammelt wird in
        der Flugschleife (3.1), damit der Bericht genau die Takte
        zählt, die auch in der CSV stehen."""
        self.flow.update(daten)

    def _funk_weg(self, uri, meldung):
        self.funk_weg_in_luft = self.in_luft
        self.funk_weg = True
        print('\n  !!! FUNKVERBINDUNG VERLOREN: %s' % meldung, flush=True)

    def _funk_qualitaet(self, prozent):
        self.funk_q = prozent

    def funk_text(self):
        if self.funk_q is None:
            return ''
        text = '   Funk %.0f %%' % self.funk_q
        if self.funk_q < FUNK_SCHWACH:
            text += ' SCHWACH'
        return text

    def _pos_empfangen(self, zeitstempel, daten, konf):
        try:
            self.pos = (daten['stateEstimate.x'], daten['stateEstimate.y'],
                        daten['stateEstimate.yaw'])
            self.pos_zeit = time.time()
        except KeyError:
            pass

    def position(self):
        """(x, y, yaw) oder None, wenn die Daten fehlen oder zu alt sind."""
        if self.pos is None or time.time() - self.pos_zeit > POS_ALT:
            return None
        return self.pos

    def abstand(self, name):
        return self.gef.get(name)

    def unten(self):
        return roh_m(self.d.get('range.zrange'))

    def versatz(self):
        """Möbel unter ihr, negativ gezählt (wie Recorder 3.2)."""
        return min(0.0, self.sprung_summe)

    def z_senden(self, z_wunsch, vorlauf=True, boden=MIN_HOEHE):
        """Wunschhöhe über dem Fußboden -> gesendete Höhe, mit Möbel,
        Decke und Vorlauf. Gibt (z_gesendet, grund, versatz) zurück."""
        versatz = self.versatz()
        z = z_wunsch + versatz
        grund = None
        z_ist = self.d.get('stateEstimate.z')
        oben = self.abstand('range.up')
        if z_ist is not None:
            if oben is not None:
                deckel = z_ist + oben - DECKEN_ABSTAND
                if z > deckel:
                    z, grund = deckel, 'decke'
            if (vorlauf and z_wunsch > self.z_soll + 1e-6
                    and z > z_ist + VORLAUF):
                z = z_ist + VORLAUF
                grund = grund or 'vorlauf'
        return max(boden, z), grund, versatz

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
        offen = self.tuer()
        for name, wo in SEITEN:
            seit = self.nah_seit[name]
            lange = seit is not None and self.d_fw - seit >= ENG_ZEIT
            if self.nah[name] >= ENG_FOLGE or lange:
                # In einer Öffnung sind die Seiten naturgemäß nah.
                # Dort zu landen ist schlechter als durchzufahren
                # (Version 2.9). Erst ganz dicht am Rahmen ist
                # Schluss. Vorne, hinten und oben bleiben scharf.
                if offen is not None and name in TUER_SEITEN \
                        and (self.nah_wert[name] or 0.0) > TUER_RAND:
                    continue
                return ('Hindernis %s bei %s m'
                        % (wo, zahl(self.nah_wert[name])), True)
        # Akku: erst bei der kritischen Schwelle der Firmware landet
        # sie, und dann sofort (Version 2.8).
        if self.akku_kritisch >= AKKU_KRITISCH_TAKTE:
            return ('Akku kritisch (%.2f V), NOTLANDUNG'
                    % (self.d.get('pm.vbat') or 0.0), True)
        if self.akku_leer >= AKKU_TAKTE and not self.akku_leer_gewarnt:
            self.akku_leer_gewarnt = True
            sag('  AKKU UNTER %.2f V (Firmware meldet leer). Sie fliegt '
                'weiter, unter %.2f V landet sie sofort.'
                % (AKKU_LEER, AKKU_KRITISCH))
        return None

    def tuer(self):
        """(links, rechts), wenn sie gerade in einer Öffnung steckt,
        sonst None (Version 2.9). Erkannt wird sie daran, dass auf BEIDEN
        Seiten gleichzeitig eine Wand in Reichweite ist und der Gang
        schmal genug ist. Ein einzelnes Hindernis hat nur auf einer Seite
        eine Wand und zählt nicht als Öffnung."""
        links = self.abstand('range.left')
        rechts = self.abstand('range.right')
        if links is None or rechts is None:
            return None
        if links < TUER_SEITE and rechts < TUER_SEITE \
                and links + rechts <= TUER_SUMME:
            return links, rechts
        return None

    def tuer_mitte(self, links, rechts):
        """Seitliches Tempo, das sie in die Mitte der Öffnung schiebt.
        Positiv = nach links (wie bei bremsen). Steht sie zu weit links,
        ist links kleiner als rechts und das Ergebnis negativ."""
        fehler = (links - rechts) / 2.0
        return max(-TUER_TEMPO, min(TUER_TEMPO, fehler * TUER_REGLER))

    def bremsen(self, vx, vy):
        """Drosselt nur die Fahrt AUF ein Hindernis zu (wie Recorder 3.2).
        Zwischen 50 und 15 cm fällt die erlaubte Geschwindigkeit
        gleichmäßig von 0,5 m/s auf null."""
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
        """Ruhelage der Sticks. Der Xbox-Nullpunkt springt bei jedem
        Einschalten des Controllers."""
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

    def stick_bewegt(self):
        return any(self.stick(n) != 0.0 for n in ACHSEN)

    def glaette(self, name, ziel):
        self.glatt[name] += (ziel - self.glatt[name]) * RAMPE
        if abs(self.glatt[name]) < 0.005:
            self.glatt[name] = 0.0
        return self.glatt[name]

    def tasten(self):
        """Liest ALLE Controller-Ereignisse seit dem letzten Aufruf.
        Gibt 'weg', 'start', 'b', 'a' oder None zurück (in dieser
        Rangfolge). Ein Druck zählt genau einmal."""
        rang = {None: 0, 'a': 1, 'b': 2, 'start': 3, 'weg': 4}
        was = None
        for e in pygame.event.get():
            neu = None
            if e.type == pygame.JOYDEVICEREMOVED:
                neu = 'weg'
            elif e.type == pygame.JOYBUTTONDOWN:
                neu = {KNOPF_START: 'start', KNOPF_B: 'b',
                       KNOPF_A: 'a'}.get(e.button)
            if rang[neu] > rang[was]:
                was = neu
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
        if not_aus:
            self.gesperrt = True

    # ------------------------------------------------------------ Vorbereitung
    def verbinden(self, scf):
        self.scf = scf
        cf = scf.cf
        self.cf = cf
        cf.connection_lost.add_callback(self._funk_weg)
        try:
            cf.link_statistics.link_quality_updated.add_callback(
                self._funk_qualitaet)
        except AttributeError:
            pass

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
            raise Abbruch('ohne Flow Deck kennt sie ihre Position nicht')
        if not ranger:
            raise Abbruch('ohne Multi-Ranger gibt es keinen Hindernisschutz')

        # Ohne Position kein Rückflug, deshalb hier Pflicht (im Recorder
        # war es freiwillig)
        for name in POS_VARIABLEN:
            if cf.log.toc.get_element_by_complete_name(name) is None:
                raise Abbruch('die Drohne liefert %s nicht' % name)
        for name in ('kalman.initialX', 'kalman.initialY', 'kalman.initialZ',
                     'kalman.initialYaw', 'kalman.resetEstimation'):
            if cf.param.toc.get_element_by_complete_name(name) is None:
                raise Abbruch('die Firmware kennt %s nicht' % name)
        self._logs_starten()

        time.sleep(0.6)
        if time.time() - self.d_zeit > DATEN_ALT:
            raise Abbruch('es kommen keine Sensordaten an')
        if self.position() is None:
            raise Abbruch('es kommen keine Positionsdaten an')

        volt = self.d.get('pm.vbat')
        self.akku_anfang = volt
        if volt is None or volt <= 0.5:
            sag('  Akku: kein Messwert.')
        elif volt < AKKU_MINIMUM:
            raise Abbruch('Akku %.2f V, zu leer zum Abheben. Erst laden.'
                          % volt)
        elif volt < AKKU_START:
            sag('  Akku %.2f V, unter %.2f V wird es knapp. Der Rückflug '
                'braucht auch Strom.' % (volt, AKKU_START))
            antwort = input('  Trotzdem fliegen? (j/n): ').strip().lower()
            sag('  Antwort: %s' % (antwort or '-'))
            if antwort != 'j':
                raise Abbruch('Akku zu schwach, nicht gestartet')
        else:
            sag('  Akku %.2f V, gut.' % volt)

    def _logs_starten(self):
        """Sensor- und Positions-Log anmelden. Auch nach dem Neuverbinden,
        denn dabei löscht die Drohne alle Log-Blöcke."""
        cf = self.cf
        lg = LogConfig(name='Heimflug', period_in_ms=50)
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

        lp = LogConfig(name='HeimflugPos', period_in_ms=50)
        for name in POS_VARIABLEN:
            lp.add_variable(name, 'float')
        cf.log.add_config(lp)
        lp.data_received_cb.add_callback(self._pos_empfangen)
        lp.start()
        self.lg_pos = lp

        # Kameraqualität (Version 3.0). Der Typ kommt aus der Drohne
        # selbst, nicht aus einer Annahme: Firmwares benennen ihn
        # unterschiedlich. Geht der Block nicht, fliegt sie trotzdem.
        self.lg_flow = None
        lf = LogConfig(name='HeimflugFlow', period_in_ms=FLOW_TAKT)
        dabei = 0
        for name in FLOW_VARIABLEN:
            try:
                el = cf.log.toc.get_element_by_complete_name(name)
                if el is None:
                    continue
                lf.add_variable(name, el.ctype)
                dabei += 1
            except Exception:
                pass
        if dabei:
            try:
                cf.log.add_config(lf)
                lf.data_received_cb.add_callback(self._flow_empfangen)
                lf.start()
                self.lg_flow = lf
            except Exception as e:
                sag('  Kameraqualität wird nicht mitgeschrieben: %s'
                    % (str(e).strip() or type(e).__name__))

    def param_setzen(self, name, wert):
        """Setzt einen Parameter und wartet, bis die Drohne ihn bestätigt.
        True = bestätigt, False = keine Antwort in PARAM_ACK s."""
        gruppe, kurz = name.split('.')
        da = threading.Event()

        def bestaetigt(_name, _wert):
            da.set()

        self.cf.param.add_update_callback(group=gruppe, name=kurz,
                                          cb=bestaetigt)
        try:
            self.cf.param.set_value(name, wert)
            ende = time.time() + PARAM_ACK
            while not da.is_set() and time.time() < ende:
                self.warten(0.02)
            return da.is_set()
        finally:
            self.cf.param.remove_update_callback(group=gruppe, name=kurz,
                                                 cb=bestaetigt)

    def kalman_setzen(self, x, y, yaw):
        """Setzt die Schätzung der Drohne auf (x, y, yaw in Grad).
        Vor dem Hinflug (0, 0, 0) = Startpunkt. Vor dem Rückflug die
        Position kurz vor der Landung: Am Boden läuft die Schätzung weg
        (Flug 18.09.: 12 Grad beim Aufsetzen, dann 39 Grad beim Warten).
        Die Werte bleiben bis zum Ausschalten in der Drohne, deshalb auch
        vor dem Hinflug immer ausdrücklich setzen.

        Version 2.3: Jeder Wert wird erst gesendet, wenn die Drohne den
        vorigen bestätigt hat (Test 19:04: Reset kam zweimal nicht an).
        Fertig ist es, sobald die Schätzung KALMAN_RUHIG s lang am Soll
        steht, nicht erst nach fester Wartezeit. Sonst sagt die Meldung,
        woran es lag. Die Motoren sind dabei aus."""
        werte = (('kalman.initialX', x), ('kalman.initialY', y),
                 ('kalman.initialZ', 0.0),
                 ('kalman.initialYaw', math.radians(yaw)))

        def am_soll(pos):
            return (pos is not None
                    and math.hypot(pos[0] - x, pos[1] - y) <= KALMAN_WEG
                    and abs(wrap(pos[2] - yaw)) <= KALMAN_DREH)

        fehler = ''
        for versuch in range(1, KALMAN_VERSUCHE + 1):
            fehlt = [name for name, wert in werte
                     if not self.param_setzen(name, '%.4f' % wert)]
            if not self.param_setzen('kalman.resetEstimation', '1'):
                fehlt.append('kalman.resetEstimation')
            t0 = time.time()
            ruhig_seit = None
            je_am_soll = False
            geschafft = False
            zurueck = False
            while time.time() - t0 < KALMAN_ZEIT:
                self.warten(0.05)
                if not zurueck and time.time() - t0 >= 0.2:
                    # Die Firmware setzt ihn meist selbst zurück, sicher ist
                    # sicher. Die Antwort ist hier egal.
                    self.cf.param.set_value('kalman.resetEstimation', '0')
                    zurueck = True
                if am_soll(self.position()):
                    je_am_soll = True
                    if ruhig_seit is None:
                        ruhig_seit = time.time()
                    elif time.time() - ruhig_seit >= KALMAN_RUHIG:
                        geschafft = True
                        break
                else:
                    ruhig_seit = None
            if not zurueck:
                self.cf.param.set_value('kalman.resetEstimation', '0')
            pos = self.position()
            if geschafft and pos is not None:
                sag('  Schätzung steht auf x %.2f m, y %.2f m, Richtung '
                    '%.0f Grad.' % pos)
                return
            if pos is None:
                fehler = 'nach dem Kalman-Reset keine Positionsdaten'
            else:
                fehler = ('Kalman-Reset hat nicht gegriffen: soll x %.2f y '
                          '%.2f %.0f Grad, ist x %.2f y %.2f %.0f Grad'
                          % (x, y, yaw, pos[0], pos[1], pos[2]))
            if fehlt:
                fehler += ('. Die Drohne hat %s nicht bestätigt (Funk)'
                           % ', '.join(n.split('.')[1] for n in fehlt))
            elif je_am_soll:
                fehler += ('. Sie war kurz am Soll, dann lief die Schätzung '
                           'am Boden weg (Flow Deck)')
            else:
                fehler += ('. Alle Werte bestätigt, die Schätzung hat sich '
                           'trotzdem nicht bewegt')
            if versuch < KALMAN_VERSUCHE:
                sag('  %s.' % fehler)
                sag('  Versuch %d von %d ...' % (versuch + 1,
                                                 KALMAN_VERSUCHE))
                self.warten(0.5)
        sag('  Tipp: Drohne am Startpunkt aus- und wieder einschalten, '
            'dann steht die Schätzung von selbst auf 0.')
        raise Abbruch(fehler)

    def startklar_machen(self, countdown, pose, nachflug=False):
        """Countdown, Sticks, Platz prüfen, Kalman auf `pose` setzen,
        armen. pose = (x, y, yaw in Grad)."""
        kalman_reset = pose == (0.0, 0.0, 0.0)
        pygame.event.clear()
        sag()
        if nachflug:
            sag('  Drohne an DENSELBEN Startpunkt stellen wie beim Hinflug,')
            sag('  Nase in DIESELBE Richtung. B oder START bricht ab.')
        elif kalman_reset:
            sag('  Drohne jetzt frei hinstellen. B oder START bricht ab.')
        else:
            sag('  Rückflug gleich. Nicht anfassen! B oder START bricht ab.')
        for i in range(countdown, 0, -1):
            sag('  Start in %2d s   %s' % (i, self.abstaende_text()))
            self.warten(1.0)

        if self.pad is not None:
            t0 = time.time()
            gemeldet = False
            while self.stick_bewegt():
                if not gemeldet:
                    sag('  Sticks loslassen, sie müssen in der Mitte stehen.')
                    gemeldet = True
                if time.time() - t0 > 10.0:
                    raise Abbruch('Sticks stehen nicht in der Mitte')
                self.warten(0.05)

        sag('  Prüfe den Platz drumherum (2 s) ...')
        proben = {name: [] for name, _ in ALLE_SENSOREN}
        flow_proben = []
        ende = time.time() + 2.0
        while time.time() < ende:
            for name, _ in ALLE_SENSOREN:
                m = self.unten() if name == 'range.zrange' \
                    else self.abstand(name)
                if m is not None:
                    proben[name].append(m)
            q = self.flow.get('motion.squal')
            if q is not None:
                flow_proben.append(q)
            self.warten(0.05)
        if time.time() - self.d_zeit > DATEN_ALT:
            raise Abbruch('Sensordaten sind abgerissen')

        def median(w):
            w = sorted(w)
            return w[len(w) // 2] if w else None

        sag('  Abstände: %s' % '   '.join(
            '%s %s' % (wo, zahl(median(proben[name])))
            for name, wo in ALLE_SENSOREN))
        for name, wo in SEITEN:
            m = median(proben[name])
            if m is not None and m < NOT_STOPP_ABSTAND:
                raise Abbruch('%s nur %.2f m frei, sie würde sofort wieder '
                              'landen' % (wo, m))
            if m is not None and m < BREMS_ABSTAND:
                sag('  Hinweis: %s %.2f m. Das kann der Boden selbst sein, '
                    'in der Luft wird neu gemessen.' % (wo, m))
        oben = median(proben['range.up'])
        if oben is not None and oben < MIN_HOEHE + DECKEN_ABSTAND:
            raise Abbruch('oben nur %.2f m frei, zu wenig zum Fliegen' % oben)

        # Ohne Bodenkamera hält sie die Position nicht, sie driftet
        # weg. Das sieht man schon am Boden: beim Flug um 15:41 stand
        # squal dort bei 196, beim Fehlstart um 17:29 bei 0 -- von der
        # ersten Zeile an. Blind abheben und erst in der Luft warnen
        # ist zu spät, deshalb hier Schluss.
        q = median(flow_proben)
        if q is not None and q < FLOW_SQUAL_BLIND:
            raise Abbruch(
                'die Bodenkamera sieht nichts (squal %d). Mach Licht '
                'an, stell sie auf gemusterten Boden, und sieh nach, '
                'ob die Linse unten am Flow Deck frei ist' % q)
        if q is not None and q < FLOW_SQUAL_SCHWACH:
            sag('  Hinweis: Bodenkamera schwach (squal %d). Sie '
                'fliegt, kann aber wegdriften.' % q)
        elif q is not None:
            sag('  Bodenkamera: squal %d, in Ordnung.' % q)

        self.cf.commander.send_stop_setpoint()
        self.warten(0.1)
        self.cf.commander.send_setpoint(0, 0, 0, 0)
        self.warten(0.1)
        if kalman_reset:
            sag('  Kalman zurücksetzen, hier ist jetzt der Startpunkt ...')
        else:
            sag('  Kalman auf den Landepunkt setzen ...')
        self.kalman_setzen(*pose)
        arm(self.cf, True)
        self.warten(0.3)

    # ------------------------------------------------------------ Flug
    def lage_unbekannt(self):
        """Vermerkt in heim_lande_<Zeit>.csv, dass die Landestelle offen
        ist (Version 2.7). Erst ab hier ist die alte Landestelle
        ungültig: Sie ist nicht mehr dort, wo sie zuletzt lag."""
        if self.lage_offen:
            self.lage_offen = False
            if self.lande_datei:
                lage_speichern(self.lande_datei, None)

    def lage_pruefen(self):
        """Ist sie vom Boden weg, gilt die alte Landestelle nicht mehr."""
        if not self.lage_offen:
            return
        hoch = self.unten()
        if hoch is not None and hoch > LAGE_HOCH:
            self.lage_unbekannt()

    def abheben(self, ziel):
        """Steigt auf die Zielhöhe (wie Recorder 3.2). Gibt (Grund,
        schnell) zurück, wenn abgebrochen wurde, sonst None."""
        ziel = max(MIN_HOEHE, min(MAX_HOEHE, ziel))
        sag('  Abheben auf %.2f m ...' % ziel)
        # Die alte Landestelle bleibt stehen, bis sie wirklich vom
        # Boden weg ist (2.7). Hebt sie nicht ab, ist sie noch dort.
        self.lage_offen = bool(self.lande_datei)
        self.akku_leer_gewarnt = False
        self.z_vorher = None
        self.sprung_summe = 0.0
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
            self.lage_pruefen()
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
            z, _grund, _v = self.z_senden(self.z_soll, vorlauf=False,
                                          boden=0.0)
            self.z_gesendet = z
            self.senden(0.0, 0.0, 0.0, z)
            takt.warte()

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
        self.lage_unbekannt()   # oben: wo sie landet, ist offen
        return None

    def befehl_sticks(self):
        dreh = self.glaette('dreh', self.stick('drehen') * MAX_YAW)
        vor = self.glaette('vor', self.stick('vor') * MAX_SPEED)
        seit = self.glaette('seit', self.stick('seit') * MAX_SPEED)
        steig = self.glaette('hoch', self.stick('hoehe') * STEIG_RATE)
        return vor, seit, dreh, self.z_soll + steig * TAKT

    def befehl_heim(self):
        """Ein Takt Rückflug. Wirft Ende, wenn sie landen soll."""
        if self.uebernommen:
            return self.befehl_sticks()
        if not self.stick_frei:
            # Beim Umkehren in der Luft hat man den Stick oft noch in der
            # Hand. Übernommen wird erst, wenn er STICK_FREI_ZEIT am Stück
            # in der Mitte war (2.7). Ein einzelner Takt reicht nicht:
            # Beim Loslassen schwingt der Stick durch die Mitte, und der
            # Rückflug galt dadurch schon als übernommen.
            if self.stick_bewegt():
                self.stick_mitte_seit = None
            elif self.stick_mitte_seit is None:
                self.stick_mitte_seit = time.time()
            elif time.time() - self.stick_mitte_seit >= STICK_FREI_ZEIT:
                self.stick_frei = True
        elif self.stick_bewegt():
            self.uebernommen = True
            sag('  Stick bewegt: DU STEUERST. Das Skript hält sich raus. '
                'B = landen.')
            return self.befehl_sticks()

        pos = self.position()
        if pos is None:
            jetzt = time.time()
            if self.pos_weg_seit is None:
                self.pos_weg_seit = jetzt
            elif jetzt - self.pos_weg_seit > POS_WEG_ZEIT:
                raise Ende('keine Positionsdaten mehr, sie landet hier')
            return 0.0, 0.0, 0.0, self.z_soll     # auf der Stelle halten
        self.pos_weg_seit = None

        jetzt = time.time()
        if self.heim_start is None:
            self.heim_start = jetzt
        grenze = self.heim.zeitgrenze()
        if jetzt - self.heim_start > grenze:
            raise Ende('Zeit um (%.0f s), sie landet hier' % grenze)

        wendet_vorher = self.heim.wendet
        vx, vy, gier, z, neben = self.heim.schritt(*pos)
        if self.heim.wendet and not wendet_vorher:
            self.stat['wenden'] += 1
            self.wende_seit = jetzt
        if not self.heim.wendet:
            self.wende_seit = None
        elif self.wende_seit is not None \
                and jetzt - self.wende_seit > WENDE_MAX:
            raise Ende('dreht sich seit %.0f s auf der Stelle, sie landet '
                       'hier' % WENDE_MAX)
        self.neben_jetzt = neben
        self.rest_jetzt = self.heim.rest(pos[0], pos[1])
        self.stat['neben_max'] = max(self.stat['neben_max'], neben)
        if neben > VERIRRT:
            raise Ende('%.2f m neben dem Weg, die Position stimmt nicht '
                       'mehr. Sie landet hier.' % neben)
        if self.heim.phase == 'fertig':
            if self.heim.zeit_um:
                raise Ende('%s nicht genau erreicht (Zeit um), '
                           'sie landet hier' % self.ziel_name)
            raise Ende('Am %s angekommen' % self.ziel_name)
        return vx, vy, gier, z

    def rueck_vorbereiten(self, pfad_datei):
        """Baut den Rückweg und speichert ihn.
        spiegel: die Aufnahme rückwärts (wie Replay im Recorder).
        weg:     der Weg ohne Schleifen (Version 2.0)."""
        if RUECKWEG_ART == 'spiegel' and self.bilder:
            gespiegelt = spiegel_bauen(self.bilder)
            self.heim = Spiegel(gespiegelt, start_gier=self.spur[0][3])
            punkte = self.heim.p
            sag('  Rückflug: deine Aufnahme rückwärts, %d von %d Takten '
                '(Stillstand weggelassen), etwa %.0f s, %.2f m.'
                % (len(gespiegelt), len(self.bilder),
                   spiegel_zeit(self.bilder), weglaenge(punkte)))
        else:
            voll = rueckweg_bauen(self.spur)
            punkte = schleifen_kuerzen(voll)
            self.heim = Heimweg(punkte, start_gier=self.spur[0][3])
            sag('  Rückweg %.2f m statt %.2f m (Schleifen weggelassen), '
                'etwa %.0f s.' % (weglaenge(punkte), weglaenge(voll),
                                  rueckzeit(punkte)))
        self.ziel_name = 'Startpunkt'
        self.start_gier = self.spur[0][3]
        self.uebernommen = False
        self.stick_frei = False
        self.stick_mitte_seit = None
        self.heim_start = None
        self.wende_seit = None
        pfad_speichern(pfad_datei, punkte)
        sag('  Rückweg gespeichert: %s' % pfad_datei)
        return punkte

    def rest_vorbereiten(self, rest, start_gier, pfad_datei):
        """Rückweg ab einer Landestelle unterwegs (Version 2.6): rest ist
        der gespiegelte Weg ab dem nächsten Punkt (rest_rueckweg)."""
        self.heim = Spiegel(rest, start_gier=start_gier)
        self.ziel_name = 'Startpunkt'
        self.start_gier = start_gier
        self.uebernommen = False
        self.stick_frei = False
        self.stick_mitte_seit = None
        self.heim_start = None
        self.wende_seit = None
        pfad_speichern(pfad_datei, self.heim.p)
        return self.heim.p

    def nach_vorbereiten(self, bilder):
        """Nachflug (Menü 2): die Aufnahme vorwärts, Ziel ist ihr letzter
        Punkt. Gibt die Anzahl der Takte zurück."""
        vorwaerts = vorwaerts_bauen(bilder)
        ende = letzte_lage(bilder)
        if ende is None:
            raise Abbruch('Aufnahme ohne Wegdaten')
        self.heim = Spiegel(vorwaerts, start_gier=ende[2],
                            ziel=(ende[0], ende[1]))
        self.ziel_name = 'Ziel'
        self.uebernommen = False
        self.stick_frei = False
        self.stick_mitte_seit = None
        self.heim_start = None
        self.wende_seit = None
        return len(vorwaerts)

    def umkehr_pruefen(self, t):
        """Einmal pro Sekunde im Hinflug: Reicht der Akku noch für den
        Rückweg? Gibt (UMKEHREN, False) zurück, wenn es Zeit ist."""
        if len(self.vbat_letzte) < 20 or len(self.spur) < 2:
            return None
        v = sum(self.vbat_letzte) / len(self.vbat_letzte)
        self.akku_kurve.append((t, v))
        t0, v0 = self.akku_kurve[0]
        rate = (v0 - v) / (t - t0) if t - t0 > 20.0 else 0.0
        if RUECKWEG_ART == 'spiegel':
            tr = spiegel_zeit(self.bilder)
        else:
            tr = rueckzeit(schleifen_kuerzen(rueckweg_bauen(self.spur)))
        self.rueck_info = (v, rate, tr)
        if umkehren_noetig(v, rate, tr):
            sag()
            sag('  AKKU: %.2f V reicht nur noch für den Rückweg (%.0f s). '
                'SIE KEHRT UM.' % (v, tr))
            sag('  Sticks loslassen, sie fliegt allein zurück.')
            return UMKEHREN, False
        if not self.akku_gewarnt and umkehren_noetig(v + 0.05, rate, tr):
            self.akku_gewarnt = True
            sag('  Akku wird knapp (%.2f V), bald kehrt sie von selbst um.'
                % v)
        return None

    def schleife(self, befehl, schreiber, phase):
        """Die Flugschleife, gleich für Hin- und Rückflug.
        befehl() liefert (vx, vy, gier, z) oder wirft Ende."""
        takt = Takt()
        t0 = time.time()
        naechste_anzeige = t0 + 1.0
        gebremst_zuletzt = False
        versperrt_seit = None
        while True:
            taste = self.tasten()
            if taste in ('start', 'b'):
                return 'Taste %s gedrückt' % taste.upper(), False
            if taste == 'weg':
                return 'Controller getrennt', False
            if taste == 'a' and phase in HIN_PHASEN and len(self.spur) >= 2:
                sag()
                sag('  A gedrückt: SIE KEHRT UM. Sticks loslassen.')
                return UMKEHREN, False
            g = self.gefahr()
            if g:
                return g

            try:
                vx, vy, gier, z = befehl()
            except Ende as e:
                # Nachflug am Ende der Aufnahme: umkehren statt landen
                if phase == 'nach' and self.heim is not None \
                        and self.heim.phase == 'fertig':
                    sag()
                    sag('  Ende der Aufnahme erreicht. SIE KEHRT UM.')
                    return UMKEHREN, False
                return str(e), False
            vx_wunsch = vx
            t = time.time() - t0

            moebel = -self.versatz()
            if abs(moebel - self.moebel_gemeldet) > 0.05:
                if moebel > 0.005:
                    sag('  Möbel unter ihr: %.2f m hoch, Höhe angepasst.'
                        % moebel)
                else:
                    sag('  Wieder über dem Boden.')
                self.moebel_gemeldet = moebel
            self.stat['moebel_max'] = max(self.stat['moebel_max'], moebel)

            z_wunsch = max(MIN_HOEHE, min(MAX_HOEHE, z))
            z_send, grund, versatz = self.z_senden(z_wunsch)
            if grund == 'decke':
                self.glatt['hoch'] = 0.0
                self.stat['decke'] += 1
            self.z_soll = z_send - versatz
            self.z_gesendet = z_send

            z_ist = self.d.get('stateEstimate.z')
            if z_ist is not None and z_ist < HOEHE_VERLOREN:
                if not self.hoehe_weg:
                    sag('  Höhe verloren (%.2f m, Akku %s V), Fahrt gestoppt.'
                        % (z_ist, zahl(self.d.get('pm.vbat'))))
                    self.hoehe_weg = True
                vx = vy = gier = 0.0
                self.stat['hoehe_weg'] += 1
            elif self.hoehe_weg and z_ist is not None \
                    and z_ist > HOEHE_VERLOREN + 0.05:
                sag('  Wieder auf %.2f m, Fahrt geht weiter.' % z_ist)
                self.hoehe_weg = False

            vx, vy, gebremst = self.bremsen(vx, vy)

            # Mittig durch die Öffnung (Version 2.9). Die Seiten-
            # abstände sind gemessen, nicht geschätzt: Das greift
            # auch dann, wenn das Flow Deck auf dem Teppich driftet.
            # Nur im Alleinflug; steuerst du, mischt sich nichts ein.
            offen = self.tuer()
            if offen is not None and phase in AUTO_PHASEN \
                    and not self.uebernommen:
                vy = self.tuer_mitte(*offen)
                if not self.tuer_gemeldet:
                    self.tuer_gemeldet = True
                    sag('  Öffnung: links %.2f m, rechts %.2f m. Sie '
                        'fährt mittig durch.' % offen)
            elif offen is None:
                self.tuer_gemeldet = False
            self.glatt['vor'], self.glatt['seit'] = vx, vy
            if phase in AUTO_PHASEN and not self.uebernommen:
                # Drehbefehl weich machen (3.2). Steuerst du von Hand,
                # laeuft der Stick durch glaette(); im Alleinflug ging
                # der Wert des Reglers bisher ungefiltert raus und
                # sprang von Takt zu Takt um bis zu 67 Grad/s. Beim
                # Gieren kippt sie dadurch sichtbar. glaette() setzt
                # self.glatt['dreh'] gleich mit, die Uebernahme von
                # Hand beginnt also weiter beim aktuellen Wert.
                gier = self.glaette('dreh', gier)

            # Rückflug: Will sie vorwärts und kommt nicht, steht etwas im
            # Weg. Ein paar Sekunden warten (es kann ja weggehen), dann
            # landen. Sie sucht sich KEINEN Weg drumherum.
            if phase in AUTO_PHASEN and not self.uebernommen:
                if vx_wunsch > 0.10 and vx < 0.05:
                    if versperrt_seit is None:
                        versperrt_seit = time.time()
                        sag('  Etwas steht im Weg (vorne %s m), sie wartet.'
                            % zahl(self.abstand('range.front')))
                    elif time.time() - versperrt_seit > VERSPERRT_ZEIT:
                        return ('Weg versperrt (vorne %s m), sie landet hier'
                                % zahl(self.abstand('range.front')), False)
                else:
                    versperrt_seit = None

            self.senden(vx, vy, gier, z_send)

            pos = self.position()
            if phase in HIN_PHASEN:
                # Genau das, was gesendet wurde (nach Bremse), wie die
                # Aufnahme im Recorder 3.2
                if pos is None:
                    self.bilder.append((vx, vy, gier, self.z_soll,
                                        None, None, None))
                else:
                    self.bilder.append((vx, vy, gier, self.z_soll,
                                        pos[0], pos[1], pos[2]))
                    self.spur.append((pos[0], pos[1], self.z_soll, pos[2]))

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
                vbat = self.d.get('pm.vbat')
                zeile = ['%.2f' % t, phase if not self.uebernommen else 'hand',
                         '%.3f' % vx, '%.3f' % vy, '%.1f' % gier,
                         '%.3f' % self.z_soll,
                         '' if z_ist is None else '%.3f' % z_ist,
                         '%.3f' % z_send]
                if pos is None:
                    zeile += ['', '', '']
                else:
                    zeile += ['%.3f' % pos[0], '%.3f' % pos[1],
                              '%.1f' % pos[2]]
                zeile.append('' if vbat is None else '%.2f' % vbat)
                for name in ('range.front', 'range.back', 'range.left',
                             'range.right', 'range.up', 'range.zrange'):
                    m = roh_m(self.d.get(name))
                    zeile.append('' if m is None else '%.3f' % m)
                zeile.append('1' if gebremst else '0')
                zeile.append('%.3f' % max(0.0, -versatz))
                if phase in AUTO_PHASEN and not self.uebernommen:
                    zeile.append(zahl(self.neben_jetzt, '%.3f'))
                    zeile.append(zahl(self.rest_jetzt, '%.3f'))
                else:
                    zeile += ['', '']
                for name in FLOW_VARIABLEN:
                    w = self.flow.get(name)
                    zeile.append('' if w is None else '%d' % w)
                schreiber.writerow(zeile)

            # Kameraqualität für den Bericht (3.1). Hier und nicht im
            # Callback: Beim Abheben und Landen steht sie dicht über
            # dem Boden, da sieht die Kamera naturgemäß wenig. Diese
            # Takte stehen in keiner CSV-Zeile und gehören auch nicht
            # in die Statistik.
            fq = self.flow.get('motion.squal')
            if fq is not None:
                self.flow_squal.append(fq)
            fb = self.flow.get('motion.shutter')
            if fb is not None:
                self.flow_shutter.append(fb)

            if time.time() >= naechste_anzeige:
                naechste_anzeige += 1.0
                v = self.versatz()
                extra = ''
                if pos is not None:
                    extra += '   bei x %.2f y %.2f' % (pos[0], pos[1])
                if phase in HIN_PHASEN:
                    umkehr = self.umkehr_pruefen(t)
                    if umkehr:
                        return umkehr
                    if self.rueck_info is not None:
                        extra += '   zurück %.0f s' % self.rueck_info[2]
                if phase in AUTO_PHASEN and not self.uebernommen \
                        and self.rest_jetzt is not None:
                    extra += '   noch %.2f m (%s)' % (self.rest_jetzt,
                                                     self.heim.phase)
                if v < -0.005:
                    extra += '   Möbel %.2f m' % -v
                if gebremst_zuletzt:
                    extra += '   BREMST'
                q = self.flow.get('motion.squal')
                if q is not None and q < FLOW_SQUAL_SCHWACH:
                    extra += '   Kamera schwach (squal %d)' % q
                    if not self.flow_gemeldet:
                        self.flow_gemeldet = True
                        sag('  Die Bodenkamera sieht wenig (squal %d). '
                            'Die Position kann wegdriften. Sie fliegt '
                            'normal weiter.' % q)
                extra += self.funk_text()
                sag('  %5.1f s  Höhe %s m  Akku %s V   %s%s'
                    % (t, zahl(None if z_ist is None else z_ist - v),
                       zahl(self.d.get('pm.vbat')),
                       '  '.join('%s %s' % (wo[0], zahl(self.abstand(n)))
                                 for n, wo in SEITEN), extra))
                gebremst_zuletzt = False
            takt.warte()

    def landen(self, schnell=False):
        """Sinkt gleichmäßig bis zum Boden, dann Motoren aus. Ein zweiter
        Druck auf START schaltet sofort ab (Not-Aus)."""
        tempo = SINK_TEMPO_NOT if schnell else SINK_TEMPO
        z = max(self.z_soll, 0.0)
        sag('  %sLandung aus %.2f m mit %.1f m/s ...'
            % ('NOT-' if schnell else '', z, tempo))
        takt = Takt()
        boden_seit = None
        self.luft_pos = self.position()
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
            # Letzte Position, solange das Flow Deck noch sicher misst
            p = self.position()
            if p is not None and unten is not None and unten > LUFT_GRENZE:
                self.luft_pos = p
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
        if self.lande_datei:
            lage_speichern(self.lande_datei, self.luft_pos)

    def sicher_landen(self, grund):
        """Egal wie der Flug endete: Ist sie in der Luft, landet sie.
        Klappt nicht einmal das, gehen die Motoren aus."""
        if grund:
            sag()
            sag('  Grund: %s' % grund[0])
            if 'Hindernis' in grund[0]:
                sag('  Alle Abstände: %s' % self.abstaende_text())
        try:
            if self.in_luft:
                self.landen(schnell=bool(grund and grund[1]))
            elif self.cf is not None:
                self.motoren_aus()
        except BaseException as e:
            sag('  Landung unterbrochen (%s), Motoren aus.'
                % type(e).__name__)
            self.motoren_aus()

    # ------------------------------------------------------------ Am Boden
    def neu_verbinden(self):
        """Nach einem Funkabbruch AM BODEN (Motoren aus) die Verbindung
        neu aufbauen. True, wenn wieder Sensor- und Positionsdaten kommen.
        Nie, wenn der Funk in der Luft abriss: Dann ist unklar, wie sie
        liegt."""
        if self.scf is None or self.in_luft or self.funk_weg_in_luft \
                or self.gesperrt:
            return False
        for lg in (self.lg, self.lg_pos, self.lg_flow):
            if lg is not None:
                try:
                    lg.stop()
                except Exception:
                    pass
        self.lg = None
        self.lg_pos = None
        self.lg_flow = None
        try:
            self.cf.close_link()        # Reste der alten Verbindung weg
        except Exception:
            pass
        time.sleep(0.5)
        try:
            self.scf.open_link()
        except Exception as e:
            sag('    klappt nicht: %s' % (str(e).strip() or type(e).__name__))
            return False
        ende = time.time() + PARAM_WARTEN
        while not self.scf.is_params_updated() and time.time() < ende:
            time.sleep(0.05)
        self.funk_weg = False
        self.funk_weg_in_luft = False
        self.pos = None
        self.pos_zeit = 0.0
        self.d_zeit = 0.0
        try:
            self._logs_starten()
        except Exception as e:
            sag('    Log neu anmelden klappt nicht: %s' % e)
            return False
        time.sleep(1.0)
        if self.funk_weg:
            return False
        if time.time() - self.d_zeit > DATEN_ALT or self.position() is None:
            sag('    verbunden, aber es kommen keine Daten an')
            return False
        # Sicher ist sicher: Motoren aus, nicht scharf
        try:
            self.cf.commander.send_stop_setpoint()
        except Exception:
            pass
        arm(self.cf, False)
        self.funk_neu += 1
        return True

    def funk_retten(self):
        """Verbindet nach einem Funkabbruch am Boden neu, bis es klappt
        oder B/START gedrückt wird. True = wieder verbunden."""
        if self.funk_weg_in_luft or self.in_luft:
            sag('  Der Funk ist IN DER LUFT abgerissen. Die Drohne hat sich '
                'selbst abgeschaltet.')
            sag('  Kein Neuverbinden: Es ist unklar, wie sie jetzt liegt.')
            return False
        sag()
        sag('  Funk weg. Die Drohne steht, Motoren aus. Ich verbinde neu.')
        sag('  Tipp: Funkstick höher legen oder näher an die Drohne. '
            'B oder START = aufgeben.')
        for versuch in range(1, NEU_VERSUCHE + 1):
            sag('  Neu verbinden, Versuch %d von %d ...'
                % (versuch, NEU_VERSUCHE))
            if self.neu_verbinden():
                sag('  Wieder verbunden.%s' % self.funk_text())
                pygame.event.clear()
                return True
            ende = time.time() + NEU_PAUSE
            while time.time() < ende:
                taste = self.tasten()
                if taste in ('b', 'start', 'weg'):
                    sag('  Aufgegeben.')
                    return False
                time.sleep(0.05)
        sag('  Keine Verbindung nach %d Versuchen. Drohne aus- und '
            'einschalten und das Skript neu starten.' % NEU_VERSUCHE)
        return False

    def auf_rueckflug_warten(self, lande_pos):
        """Nach der Landung: Gibt True zurück, wenn A gedrückt wurde und
        ein Rückflug möglich ist."""
        pygame.event.clear()
        sag()
        sag('  >>> A = zurück zum Startpunkt fliegen    B = beenden <<<')
        naechste_anzeige = time.time() + 2.0
        while True:
            if time.time() >= naechste_anzeige:
                naechste_anzeige = time.time() + 2.0
                pos = self.position()
                if pos is not None:
                    sag('  (am Boden läuft die Schätzung: %.2f m, %.0f Grad '
                        'weg, wird vor dem Start gelöscht)%s'
                        % (math.hypot(pos[0] - lande_pos[0],
                                      pos[1] - lande_pos[1]),
                           wrap(pos[2] - lande_pos[2]), self.funk_text()))
            if self.funk_weg:
                if not self.funk_retten():
                    sag('  Kein Rückflug.')
                    return False
                sag()
                sag('  >>> A = zurück zum Startpunkt fliegen    '
                    'B = beenden <<<')
                naechste_anzeige = time.time() + 2.0
                continue
            taste = self.tasten()
            if taste == 'weg':
                sag('  Controller getrennt, kein Rückflug.')
                return False
            if taste in ('b', 'start'):
                sag('  Beendet ohne Rückflug.')
                return False
            if taste == 'a':
                break
            time.sleep(0.02)

        volt = self.d.get('pm.vbat')
        if volt is not None and 0.5 < volt < AKKU_MINIMUM:
            sag('  Akku %.2f V, zu leer für den Rückflug.' % volt)
            return False
        return True


# -----------------------------------------------------------------------------
# DATEIEN
# -----------------------------------------------------------------------------
def csv_oeffnen(pfad):
    datei = open(pfad, 'w', encoding='utf-8', newline='')
    schreiber = csv.writer(datei, delimiter=';')
    schreiber.writerow(CSV_KOPF)
    return datei, schreiber


def pfad_speichern(pfad, punkte):
    with open(pfad, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['nr', 'x_m', 'y_m', 'z_m'])
        for nr, (x, y, z) in enumerate(punkte):
            w.writerow([nr, '%.3f' % x, '%.3f' % y, '%.3f' % z])


def zusammenfassung(r, titel, grund):
    s = r.stat
    sag()
    sag('  ---------------- %s ----------------' % titel)
    sag('  Beendet weil:      %s' % (grund[0] if grund else '-'))
    sag('  Geflogen:          %.1f s (%d Takte)' % (s['dauer'], s['takte']))
    if s['takte']:
        sag('  Gebremst:          %d Takte (%.0f %%)'
            % (s['gebremst'], 100.0 * s['gebremst'] / s['takte']))
        sag('  An der Decke:      %d Takte' % s['decke'])
        if s['moebel_max'] > 0.005:
            sag('  Möbel darunter:    max. %.2f m' % s['moebel_max'])
        if s['hoehe_weg']:
            sag('  Höhe verloren:     %d Takte, Fahrt dabei gestoppt'
                % s['hoehe_weg'])
        sag('  Kleinster Abstand: %s'
            % '   '.join('%s %s' % (wo, zahl(s['min'][n]))
                         for n, wo in SEITEN))
    if r.flow_squal:
        klein = min(r.flow_squal)
        sag('  Bodenkamera:       squal Mittel %.0f, kleinster %d%s'
            % (sum(r.flow_squal) / len(r.flow_squal), klein,
               '   SCHWACH' if klein < FLOW_SQUAL_SCHWACH else ''))
    if r.flow_shutter:
        sag('                     shutter Mittel %.0f, größter %d'
            % (sum(r.flow_shutter) / len(r.flow_shutter),
               max(r.flow_shutter)))
    sag('  Akku jetzt:        %s V' % zahl(r.d.get('pm.vbat')))


# -----------------------------------------------------------------------------
# ABLAUF
# -----------------------------------------------------------------------------
def fliegen(pad, stempel, nach=None, zurueck=None,
            ohne_rueckflug=False):
    """nach = (Name, Bilder) für den Nachflug (Menü 2) oder eine benannte
    Strecke (Menü 4), zurueck = (Bilder, Startrichtung, Lage, Landedatei)
    für Nur zurück (Menü 3), sonst Hin und zurück (Menü 1).

    ohne_rueckflug (Menü 5): sie zeichnet nur auf und landet am Ende,
    statt allein zurückzufliegen."""
    r = FlowRanger(pad)
    r.ohne_rueckflug = ohne_rueckflug
    r.nullpunkt_messen()

    cflib.crtp.init_drivers()
    sag('  Verbinde mit %s ...' % URI)
    try:
        with SyncCrazyflie(URI, cf=Crazyflie(
                rw_cache=os.path.join(HIER, 'cache'))) as scf:
            try:
                if zurueck is not None:
                    return _nur_zurueck(r, scf, zurueck)
                return _hin_und_zurueck(r, scf, stempel, nach)
            finally:
                for lg in (r.lg, r.lg_pos, r.lg_flow):
                    if lg is not None:
                        try:
                            lg.stop()
                        except Exception:
                            pass
    except Exception as e:
        sag('  Keine Verbindung zur Drohne: %s' % e)
        sag('  Ist sie eingeschaltet, steckt der Funkstick, ist der '
            'cfclient zu?')
        return 1


def _ein_flug(r, phase, csv_pfad, start_hoehe, befehl, countdown, pose,
              rueck_pfad=None, pfad_datei=None):
    """Startklar machen, abheben, fliegen, landen. Gibt den Grund des
    Endes zurück. Landet in jedem Fall.

    Hinflug oder Nachflug: Endet er mit UMKEHREN (Taste A, Akku oder
    beim Nachflug das Ende der Aufnahme), geht es ohne Landung direkt in
    den Rückflug (r.rueck_in_luft wird True)."""
    grund = None
    dateien = []
    r.stat_neu()
    try:
        r.startklar_machen(countdown, pose, nachflug=phase == 'nach')
        datei, schreiber = csv_oeffnen(csv_pfad)
        dateien.append(datei)
        grund = r.abheben(start_hoehe)
        if grund is None:
            sag('  In der Luft: %s' % r.abstaende_text())
            sag()
            if phase == 'hin' and r.ohne_rueckflug:
                sag('  Du steuerst, der Weg wird mitgeschrieben.')
                sag('  Kein Rückflug: A und B landen beide.')
            elif phase == 'hin':
                sag('  Du steuerst, der Weg wird mitgeschrieben.')
                sag('  A = umkehren und zurückfliegen   B oder START = landen')
            elif phase == 'nach':
                sag('  Nachflug läuft, am Ende kehrt sie um. Stick bewegen = '
                    'du übernimmst.')
                sag('  A = sofort umkehren   B oder START = landen')
            else:
                sag('  Rückflug läuft. Stick bewegen = du übernimmst. '
                    'B oder START = landen.')
            grund = r.schleife(befehl, schreiber, phase)
            if (phase in HIN_PHASEN and grund[0] == UMKEHREN
                    and not r.ohne_rueckflug):
                zusammenfassung(r, TITEL[phase], grund)
                sag()
                sag('  ============ RÜCKFLUG (ohne Landung) ============')
                r.rueck_vorbereiten(pfad_datei)
                datei, schreiber = csv_oeffnen(rueck_pfad)
                dateien.append(datei)
                r.stat_neu()
                r.rueck_in_luft = True
                sag('  Stick loslassen = sie fliegt allein. Danach Stick '
                    'bewegen = du übernimmst. B = landen.')
                grund = r.schleife(r.befehl_heim, schreiber, 'rueck')
    except Abbruch as e:
        grund = 'vor dem Start abgebrochen: %s' % e, False
    except KeyboardInterrupt:
        grund = 'Strg+C', False
    except Exception as e:
        grund = 'Programmfehler: %s' % e, False
        for zeile in traceback.format_exc().splitlines():
            sag('    ' + zeile)
    finally:
        r.sicher_landen(grund)
        for datei in dateien:
            datei.close()
    return grund


TITEL = {'hin': 'Hinflug', 'nach': 'Nachflug', 'rueck': 'Rückflug'}


def funk_am_boden(r, grund):
    """True, wenn der Flug vor dem Abheben am Funk scheiterte und die
    Drohne dabei am Boden stand."""
    return (r.funk_weg and not r.funk_weg_in_luft and not r.in_luft
            and not r.gesperrt and grund is not None
            and grund[0].startswith('vor dem Start'))


def mit_neustart(r, flug):
    """Führt flug() aus. Reißt der Funk vor dem Abheben ab, wird neu
    verbunden und der Start wiederholt (höchstens START_VERSUCHE)."""
    grund = flug()
    for _ in range(START_VERSUCHE - 1):
        if not funk_am_boden(r, grund):
            return grund
        if not r.funk_retten():
            return grund
        sag('  Neuer Startversuch.')
        grund = flug()
    if funk_am_boden(r, grund):
        sag('  %d Mal Funkabbruch vor dem Start, ich gebe auf.'
            % START_VERSUCHE)
    return grund


def rueck_bericht(r, grund, rueck_pfad):
    zusammenfassung(r, 'Rückflug', grund)
    s = r.stat
    sag('  Wenden an Ecken:   %d' % s['wenden'])
    sag('  Neben dem Weg:     höchstens %.2f m' % s['neben_max'])
    if r.uebernommen:
        sag('  Du hast unterwegs übernommen.')
    # Position kurz VOR dem Aufsetzen: Danach läuft die Schätzung am
    # Boden weg (Flug 18.09. 19:51: in der Luft 7 cm, am Boden 17 cm,
    # nachgemessen 7 cm)
    pos = r.luft_pos
    if pos is not None and r.start_gier is not None:
        sag('  Gelandet laut Drohne %.2f m vom Startpunkt, Richtung %.0f '
            'Grad daneben (kurz vor dem Aufsetzen).'
            % (math.hypot(pos[0], pos[1]), wrap(pos[2] - r.start_gier)))
        sag('  Miss mal nach, wie weit sie WIRKLICH vom Startpunkt steht.')
        sag('  Der Unterschied ist der Fehler des Flow Decks.')
    if s['takte']:
        sag('  Aufnahme:          %s' % rueck_pfad)


def weiter_moeglich(r, grund):
    """Nach einem Rückflug (Version 2.6): Darf sie ab der Landestelle
    weiterfliegen? Nur wenn DU gelandet hast (B oder START) und die Lage
    sicher bekannt ist."""
    return (grund is not None and grund[0].startswith('Taste')
            and not r.gesperrt and not r.funk_weg_in_luft
            and r.luft_pos is not None)


def _rest_flug(r, bilder, start_gier, lage):
    """Ein Rückflug ab `lage` (x, y, Grad) auf dem gespiegelten Weg
    (Version 2.6). Wartet vorher auf A. Gibt den Grund des Endes zurück,
    None = nicht geflogen."""
    rest, abstand = rest_rueckweg(bilder, lage[0], lage[1])
    luftlinie = math.hypot(lage[0], lage[1])
    sag()
    sag('  Sie steht bei x %.2f m, y %.2f m, Richtung %.0f Grad.' % lage)
    sag('  Luftlinie zum Start %.2f m.' % luftlinie)
    if luftlinie < MIN_WEG:
        sag('  Sie steht schon fast am Start, kein Rückflug nötig.')
        return None
    if abstand > REST_ABSTAND:
        sag('  Sie steht %.2f m neben dem aufgezeichneten Weg, zu weit. '
            'Kein Rückflug.' % abstand)
        return None
    stempel = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    rest_pfad = os.path.join(HIER, 'heim_rest_%s.csv' % stempel)
    punkte = r.rest_vorbereiten(
        rest, start_gier, os.path.join(HIER, 'heim_pfad_%s.csv' % stempel))
    sag('  Rückweg ab hier: %d Takte, etwa %.0f s, %.2f m (%.2f m neben '
        'dem Weg).' % (len(rest), len(rest) * TAKT + RUECK_EXTRA,
                       weglaenge(punkte), abstand))
    sag('  Die Drohne jetzt NICHT anfassen.')
    if not r.auf_rueckflug_warten(lage):
        return None
    sag()
    sag('  ==================== RÜCKFLUG ====================')
    grund = mit_neustart(r, lambda: _ein_flug(
        r, 'rueck', rest_pfad, max(START_HOEHE, punkte[0][2]),
        r.befehl_heim, COUNTDOWN_RUECK, pose=lage))
    rueck_bericht(r, grund, rest_pfad)
    return grund


def _weiter_zurueck(r, grund, bilder, start_gier):
    """Hast du sie auf dem Rückweg gelandet: A = ab dort weiter zum
    Startpunkt, beliebig oft (Version 2.6)."""
    while start_gier is not None and weiter_moeglich(r, grund):
        sag()
        sag('  Sie ist auf dem Rückweg gelandet.')
        grund = _rest_flug(r, bilder, start_gier, r.luft_pos)


def _nur_zurueck(r, scf, zurueck):
    """Menü 3: ab der letzten Landestelle zurück zum Startpunkt."""
    bilder, start_gier, lage, lande_datei = zurueck
    try:
        r.verbinden(scf)
    except Abbruch as e:
        sag('  Abgebrochen: %s' % e)
        return 1
    r.lande_datei = lande_datei
    grund = _rest_flug(r, bilder, start_gier, lage)
    _weiter_zurueck(r, grund, bilder, start_gier)
    if r.funk_neu:
        sag('  Neu verbunden:     %d Mal' % r.funk_neu)
    return 0


def _hin_und_zurueck(r, scf, stempel, nach=None):
    """Menü 1 (nach = None): du fliegst hin, sie fliegt zurück.
    Menü 2 (nach = (Pfad, Bilder)): sie fliegt die Aufnahme hin und
    danach zurück."""
    try:
        r.verbinden(scf)
    except Abbruch as e:
        sag('  Abgebrochen: %s' % e)
        return 1
    r.lande_datei = os.path.join(HIER, 'heim_lande_%s.csv' % stempel)

    phase = 'hin' if nach is None else 'nach'
    hin_pfad = os.path.join(HIER, 'heim_%s_%s.csv' % (phase, stempel))
    rueck_pfad = os.path.join(HIER, 'heim_rueck_%s.csv' % stempel)
    pfad_datei = os.path.join(HIER, 'heim_pfad_%s.csv' % stempel)

    if nach is None:
        befehl = r.befehl_sticks
        hoehe = START_HOEHE
    else:
        pfad, bilder = nach      # pfad ist hier nur der Anzeigename
        takte = r.nach_vorbereiten(bilder)
        ziel = letzte_lage(bilder)
        assert ziel is not None     # hat hinflug_waehlen geprüft
        sag()
        sag('  Aufnahme: %s' % pfad)
        sag('  Hin: %d von %d Takten (Stillstand weggelassen), etwa %.0f s, '
            '%.2f m.' % (takte, len(bilder), takte * TAKT,
                         weglaenge(r.heim.p)))
        sag('  Umkehrpunkt: x %.2f m, y %.2f m. Danach fliegt sie zurück.'
            % ziel[:2])
        befehl = r.befehl_heim
        hoehe = max(START_HOEHE, bilder[0][3])

    # ------------------------------------------------ Hinflug / Nachflug
    titel = TITEL[phase]
    sag()
    sag('  ==================== %s ====================' % titel.upper())
    grund = mit_neustart(r, lambda: _ein_flug(
        r, phase, hin_pfad, hoehe, befehl, COUNTDOWN_HIN,
        pose=(0.0, 0.0, 0.0), rueck_pfad=rueck_pfad, pfad_datei=pfad_datei))
    if r.rueck_in_luft:
        rueck_bericht(r, grund, rueck_pfad)
        sag('  %s-Aufnahme: %s' % (titel, hin_pfad))
        _weiter_zurueck(r, grund, r.bilder, r.start_gier)
        if r.funk_neu:
            sag('  Neu verbunden:     %d Mal' % r.funk_neu)
        return 0
    zusammenfassung(r, titel, grund)
    if r.stat['takte']:
        sag('  Aufnahme:          %s' % hin_pfad)

    if r.ohne_rueckflug:
        # Menü 5. Sie bleibt liegen, wo sie steht. Zurückholen geht
        # danach noch mit Menü 3, solange sie nicht angefasst wird.
        sag('  Nur aufgezeichnet, kein Rückflug.')
        sag('  Mit [3] holst du sie von dort zurück, solange sie')
        sag('  unberührt liegen bleibt.')
        return 0
    if r.funk_weg and r.funk_weg_in_luft:
        sag('  Der Funk ist in der Luft abgerissen, kein Rückflug.')
        return 0
    if r.gesperrt or grund is None or grund[0].startswith('vor dem Start'):
        sag('  Kein Rückflug möglich.')
        return 0
    # Funk nach dem Aufsetzen weg: auf_rueckflug_warten verbindet neu
    if len(r.spur) < 2:
        sag('  Keine Wegdaten aufgezeichnet, kein Rückflug.')
        return 0

    # Position kurz VOR dem Aufsetzen: Am Boden läuft die Schätzung weg
    lande_pos = r.luft_pos
    if lande_pos is None:
        sag('  Keine Positionsdaten von der Landung, kein Rückflug.')
        return 0
    luftlinie = math.hypot(lande_pos[0], lande_pos[1])
    sag()
    sag('  Gelandet bei x %.2f m, y %.2f m, Richtung %.0f Grad.'
        % lande_pos)
    sag('  Luftlinie zum Start %.2f m.' % luftlinie)
    punkte = r.rueck_vorbereiten(pfad_datei)
    if luftlinie < MIN_WEG and weglaenge(punkte) < MIN_WEG:
        sag('  Sie steht schon fast am Start, kein Rückflug nötig.')
        return 0
    sag('  Die Drohne jetzt NICHT anfassen.')

    if not r.auf_rueckflug_warten(lande_pos):
        return 0

    # ------------------------------------------------ Rückflug
    sag()
    sag('  ==================== RÜCKFLUG ====================')
    # Immer mindestens auf Starthöhe abheben. Mit 0,20 m (Landehöhe im
    # Test vom 18.09.) kam sie nur 9 cm hoch und brach als "hebt nicht ab"
    # ab. Danach sinkt sie von selbst auf die Höhe des Weges.
    grund = mit_neustart(r, lambda: _ein_flug(
        r, 'rueck', rueck_pfad, max(START_HOEHE, punkte[0][2]),
        r.befehl_heim, COUNTDOWN_RUECK, pose=lande_pos))
    rueck_bericht(r, grund, rueck_pfad)
    _weiter_zurueck(r, grund, r.bilder, r.start_gier)
    if r.funk_neu:
        sag('  Neu verbunden:     %d Mal' % r.funk_neu)
    return 0


def hinflug_waehlen():
    """Zeigt die neuesten 5 Hinflüge (wie im Recorder). Gibt (Pfad,
    Bilder) oder None zurück."""
    dateien = sorted(glob.glob(os.path.join(HIER, 'heim_hin_*.csv')),
                     key=os.path.getmtime, reverse=True)[:5]
    if not dateien:
        sag('  Kein Hinflug gefunden (heim_hin_*.csv in %s).' % HIER)
        sag('  Erst mit [1] einen Hinflug fliegen.')
        return None
    sag()
    sag('  Die neuesten Hinflüge:')
    geladen = []
    for i, pfad in enumerate(dateien, 1):
        bilder = hinflug_laden(pfad)
        geladen.append(bilder)
        ende = letzte_lage(bilder)
        if not bilder:
            sag('  [%d] %s   leer' % (i, os.path.basename(pfad)))
        elif ende is None:
            sag('  [%d] %s   %5.1f s, ohne Wegdaten'
                % (i, os.path.basename(pfad), len(bilder) * TAKT))
        else:
            sag('  [%d] %s   %5.1f s, bis %.2f m hoch, endet bei x %.2f '
                'y %.2f' % (i, os.path.basename(pfad), len(bilder) * TAKT,
                            max(b[3] for b in bilder), ende[0], ende[1]))
    wahl = input('  Welche? (Enter = 1): ').strip() or '1'
    sag('  Gewählt: %s' % wahl)
    try:
        nr = int(wahl) - 1
        if nr < 0:
            raise IndexError
        pfad, bilder = dateien[nr], geladen[nr]
    except (ValueError, IndexError):
        sag('  Ungültige Wahl.')
        return None
    if not bilder or letzte_lage(bilder) is None:
        sag('  Dieser Hinflug hat keine Wegdaten, nachfliegen geht nicht.')
        return None
    return os.path.basename(pfad), bilder


def nur_zurueck_waehlen():
    """Menü 3: Letzten Flug und Landestelle suchen, nachfragen. Gibt
    (Bilder, Startrichtung, Lage, Landedatei) oder None zurück."""
    pfad = letzter_flug(HIER)
    if pfad is None:
        sag('  Kein Flug gefunden (heim_hin_*.csv, heim_nach_*.csv).')
        return None
    art, zeit = os.path.basename(pfad)[:-4].split('_', 2)[1:]
    bilder = hinflug_laden(pfad, ('hin',) if art == 'hin'
                           else ('nach', 'hand'))
    richtung = start_richtung(bilder)
    lande_datei = os.path.join(HIER, 'heim_lande_%s.csv' % zeit)
    lage = lage_lesen(lande_datei)
    sag()
    sag('  Letzter Flug: %s' % os.path.basename(pfad))
    if richtung is None:
        sag('  Er hat keine Wegdaten, kein Rückflug.')
        return None
    if lage is None:
        sag('  Zu diesem Flug gibt es keine sichere Landeposition')
        sag('  (Flug vor Version 2.6, Not-Aus oder Funkabbruch in der Luft).')
        sag('  Bitte von Hand zum Startpunkt bringen.')
        return None
    sag('  Zuletzt gelandet bei x %.2f m, y %.2f m, Richtung %.0f Grad, '
        '%.2f m vom Startpunkt.' % (*lage, math.hypot(lage[0], lage[1])))
    sag()
    sag('  Sie muss GENAU dort liegen, wo sie gelandet ist: nicht angehoben,')
    sag('  nicht verschoben, nicht gedreht. Aus- und einschalten ist in')
    sag('  Ordnung. Sonst fliegt sie einen falschen Weg.')
    antwort = input('  Liegt sie unberührt da? (j/n): ').strip().lower()
    sag('  Antwort: %s' % (antwort or '-'))
    if antwort != 'j':
        sag('  Dann bitte von Hand zum Startpunkt bringen. Beendet.')
        return None
    return bilder, richtung, lage, lande_datei


def _frage(text):
    """input(), das bei Strg+C oder geschlossener Eingabe leer zurückgibt
    statt das Programm zu beenden. Der Flugbericht soll noch geschrieben
    werden. Die Antwort landet auch im Bericht."""
    try:
        antwort = input(text).strip()
    except (EOFError, KeyboardInterrupt):
        sag()
        antwort = ''
    sag('  Eingabe: %s' % (antwort or '-'))
    return antwort


def strecke_anbieten(stempel, wahl):
    """Fragt nach der Landung, ob der Hinflug einen Namen bekommen soll.

    Das läuft erst, wenn alles vorbei ist: Motoren aus, Funk zu, CSV
    geschlossen. Von hier aus kann nichts mehr fliegen. Geht etwas
    schief, wird es gemeldet und der Bericht trotzdem geschrieben.

    Nur für Menü 1 und 2 -- Menü 3 fliegt nur zurück und zeichnet
    keinen neuen Hinweg auf."""
    phase = {'1': 'hin', '5': 'hin', '2': 'nach', '4': 'nach'}.get(wahl)
    if strecken is None or phase is None:
        return
    quelle = os.path.join(HIER, 'heim_%s_%s.csv' % (phase, stempel))
    if not os.path.isfile(quelle):
        return
    try:
        kz = strecken.kennzahlen_rechnen(quelle, phase)
    except Exception as e:
        sag('  Die Aufnahme ist nicht auswertbar: %s' % e)
        return
    # Unter einer Sekunde war das kein Flug, sondern ein Fehlstart.
    if kz.takte < int(1.0 / TAKT):
        return

    sag()
    sag('  ---------------- Strecke behalten? ----------------')
    sag('  %.0f s, %.2f m Weg, %.2f m Luftlinie, %.0f Grad gedreht, '
        '%.0f %% Schweben.'
        % (kz.dauer_s, kz.weg_m, kz.luftlinie_m, kz.gedreht_grad,
           100 * kz.schweben_anteil))
    for warnung in kz.warnungen():
        sag('  Achtung: %s' % warnung)
    sag('  Mit einem Namen liegt sie in %s'
        % os.path.join(HIER, strecken.ORDNER))
    sag('  und du kannst sie später wieder abfliegen. Leer lassen = nicht')
    sag('  behalten; die Aufnahme selbst bleibt in jedem Fall liegen.')
    name = _frage('  Name: ')
    if not name:
        sag('  Nicht als Strecke gespeichert.')
        return
    _strecke_ablegen(quelle, name, phase)


def _strecke_ablegen(quelle, name, phase):
    """Legt die Strecke ab. Ist der Name vergeben, wird gefragt, bevor
    etwas ersetzt wird -- überschreiben passiert nie von allein."""
    try:
        sauber = strecken.name_pruefen(name)
    except strecken.StreckenFehler as e:
        sag('  %s' % e)
        sag('  Nicht als Strecke gespeichert.')
        return
    ersetzen = False
    if os.path.exists(os.path.join(strecken.ordner_pfad(HIER),
                                   sauber + '.json')):
        sag('  Es gibt schon eine Strecke "%s".' % sauber)
        if _frage('  Die alte ersetzen? (j/n): ').lower() != 'j':
            sag('  Nicht als Strecke gespeichert.')
            return
        ersetzen = True
    try:
        s = strecken.speichern(quelle, sauber, HIER, phase=phase,
                               ueberschreiben=ersetzen)
    except Exception as e:
        sag('  Konnte die Strecke nicht speichern: %s' % e)
        return
    sag('  Gespeichert als "%s".' % s.name)
    sag('  %s' % s.csv_datei)


# Der Flugraum: 4,5 m lang, 2,7 m breit, zwei Zimmer mit Tür dazwischen.
# Passt ein zusammengehängter Weg da nicht hinein, fliegt sie gegen eine
# Wand. Der Multi-Ranger bremst sie zwar, aber dann steht sie fest und
# der Rest des Weges stimmt nicht mehr.
RAUM_X = 4.5
RAUM_Y = 2.7

# Phasen, die einen Hinweg beschreiben. 'rueck' gehört nicht dazu: eine
# Strecke ist immer der Weg vom Start weg, der Rückweg entsteht daraus.
HIN_SPALTEN = ('hin', 'nach', 'hand')


def strecke_laden(s):
    """Die Bilder einer benannten Strecke. Leer, wenn die CSV fehlt."""
    return hinflug_laden(s.csv_datei, HIN_SPALTEN)


def strecken_liste(ueberschrift):
    """Zeigt die benannten Strecken durchnummeriert an. Gibt die Liste
    zurück, oder eine leere Liste, wenn es keine gibt."""
    if strecken is None:
        sag('  strecken.py fehlt, deshalb gibt es keine benannten Strecken.')
        return []
    liste = strecken.alle(HIER)
    if not liste:
        sag('  Noch keine benannte Strecke in %s.'
            % os.path.join(HIER, strecken.ORDNER))
        sag('  Flieg erst eine mit [1] und gib ihr danach einen Namen.')
        return []
    sag()
    sag('  %s' % ueberschrift)
    for i, s in enumerate(liste, 1):
        sag('  [%d] %s' % (i, strecken.zeile(s)))
    return liste


def _nummern(text, anzahl):
    """"1,3,1" wird zu [0, 2, 0]. Wirft ValueError bei allem, was nicht
    in die Liste passt."""
    nummern = []
    for teil in text.replace(' ', ',').split(','):
        if not teil:
            continue
        nr = int(teil) - 1
        if not 0 <= nr < anzahl:
            raise ValueError(teil)
        nummern.append(nr)
    if not nummern:
        raise ValueError('leer')
    return nummern


def strecke_waehlen():
    """Menü 4: eine oder mehrere benannte Strecken zu einem Weg
    zusammensetzen. Gibt (Anzeigename, Bilder) oder None zurück."""
    liste = strecken_liste('Benannte Strecken:')
    if not liste:
        return None
    sag()
    sag('  Eine Nummer, oder mehrere für hintereinander: 1,2,1')
    gewaehlt = _frage('  Welche? (Enter = 1): ') or '1'
    try:
        nummern = _nummern(gewaehlt, len(liste))
    except ValueError:
        sag('  Ungültige Wahl.')
        return None
    wie_oft = _frage('  Wie oft das Ganze? (Enter = 1 Mal): ') or '1'
    try:
        mal = int(wie_oft)
        if not 1 <= mal <= 20:
            raise ValueError
    except ValueError:
        sag('  Das ist keine Anzahl zwischen 1 und 20.')
        return None

    teile, namen = [], []
    for nr in nummern * mal:
        s = liste[nr]
        bilder = strecke_laden(s)
        if not bilder or letzte_lage(bilder) is None:
            sag('  "%s" hat keine Wegdaten, damit geht das nicht.' % s.name)
            return None
        teile.append(bilder)
        namen.append(s.name)
    weg = bilder_ketten(teile)
    name = ' + '.join(namen) if len(namen) <= 4 else (
        '%s ... %s (%d Teile)' % (namen[0], namen[-1], len(namen)))
    benutzt = [liste[nr] for nr in dict.fromkeys(nummern)]
    return (name, weg) if _weg_abnehmen(name, weg, teile, benutzt) else None


# Wie weit ein zusammengesetzter Weg über den grössten Einzelteil
# hinausragen darf, bevor gewarnt wird. Die Positionsschätzung driftet:
# eine Strecke quer durch beide Zimmer misst 4,54 m, obwohl der Raum nur
# 4,5 m lang ist. Ohne diese Toleranz meldete schon eine einzelne, real
# geflogene Strecke "passt nicht" -- und eine Warnung, die immer kommt,
# ist keine.
RAUM_TOLERANZ = 0.30


def _weg_abnehmen(name, weg, teile, benutzt):
    """Zeigt, was daraus geworden ist, und fragt nach. True = losfliegen.

    Zusammensetzen ist der Punkt, an dem aus zwei harmlosen Strecken ein
    Weg wird, der nicht mehr in den Raum passt oder den Akku nicht mehr
    hergibt. Deshalb hier die Zahlen und eine ausdrückliche Zusage."""
    breit, tief = spannweite(weg)
    ende = letzte_lage(weg)
    sag()
    sag('  Zusammengesetzt: %s' % name)
    sag('  %d Takte, etwa %.0f s hin, %.2f m Weg.'
        % (len(weg), len(weg) * TAKT, weglaenge([(b[4], b[5], b[3])
                                                 for b in weg
                                                 if b[4] is not None])))
    sag('  Er spannt %.2f m in der Länge und %.2f m in der Breite.'
        % (breit, tief))
    if ende is not None:
        sag('  Umkehrpunkt: x %.2f m, y %.2f m. Danach fliegt sie zurück.'
            % ende[:2])

    # Jeder Teil für sich ist einmal geflogen worden, passt also in den
    # Raum. Gefährlich wird erst, was durch das Zusammensetzen darüber
    # hinauswächst.
    einzeln = [spannweite(teil) for teil in teile] or [(0.0, 0.0)]
    eng = (breit > max(e[0] for e in einzeln) + RAUM_TOLERANZ
           or tief > max(e[1] for e in einzeln) + RAUM_TOLERANZ)
    if eng:
        sag('  ACHTUNG: zusammen reicht der Weg weiter, als jede Strecke')
        sag('  für sich gegangen ist. Dein Raum ist %.1f x %.1f m.'
            % (RAUM_X, RAUM_Y))
        sag('  Sinnvoll ist das nur bei einer Runde, die dort endet, wo')
        sag('  sie anfängt.')

    for s in benutzt:
        for warnung in s.kennzahlen.warnungen():
            sag('  "%s": %s' % (s.name, warnung))
    sag('  Der Rückflug kommt oben drauf, der Weg zählt also doppelt.')
    sag('  Reicht der Akku nicht, kehrt sie von selbst vorher um.')
    frage = ('  Trotzdem fliegen? (j/n): ' if eng
             else '  Losfliegen? (j = ja, sonst zurück): ')
    if _frage(frage).lower() != 'j':
        sag('  Abgebrochen, es wird nicht geflogen.')
        return False
    return True


def strecken_verwalten():
    """Menü 6: ansehen, umbenennen, aussortieren. Fliegt nicht, braucht
    keinen Controller und fasst keine Drohne an."""
    if strecken is None:
        sag('  strecken.py fehlt neben dem Flugskript, das geht nicht.')
        return 1
    while True:
        liste = strecken_liste('Strecken in %s'
                               % os.path.join(HIER, strecken.ORDNER))
        if not liste:
            return 0
        sag()
        sag('  [u] umbenennen   [a] aussortieren   [Enter] zurück')
        was = _frage('  Was? ').lower()
        if was == 'u':
            _verwalten_umbenennen(liste)
        elif was == 'a':
            _verwalten_aussortieren(liste)
        else:
            return 0


def _eine_waehlen(liste, text):
    """Eine Strecke aus der Liste, oder None bei leerer Eingabe."""
    gewaehlt = _frage(text)
    if not gewaehlt:
        return None
    try:
        return liste[_nummern(gewaehlt, len(liste))[0]]
    except ValueError:
        sag('  Ungültige Wahl.')
        return None


def _verwalten_umbenennen(liste):
    s = _eine_waehlen(liste, '  Welche umbenennen? (Enter = keine): ')
    if s is None:
        return
    neu = _frage('  Neuer Name für "%s": ' % s.name)
    if not neu:
        return
    try:
        fertig = strecken.umbenennen(s.name, neu, HIER)
    except Exception as e:
        sag('  %s' % e)
        return
    sag('  Heißt jetzt "%s".' % fertig.name)
    sag('  %s' % fertig.csv_datei)


def _verwalten_aussortieren(liste):
    s = _eine_waehlen(liste, '  Welche aussortieren? (Enter = keine): ')
    if s is None:
        return
    sag('  "%s" wird nicht gelöscht, nur beiseite gelegt.' % s.name)
    if _frage('  Wirklich? (j/n): ').lower() != 'j':
        sag('  Bleibt, wo sie ist.')
        return
    try:
        ziel = strecken.aussortieren(s.name, HIER)
    except Exception as e:
        sag('  %s' % e)
        return
    sag('  Liegt jetzt in %s' % ziel)


def main():
    stempel = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    sag()
    sag('  Crazyflie Flow-Ranger: Heimflug (Version 4.1)')
    sag('  %s' % datetime.now().strftime('%d.%m.%Y %H:%M'))
    sag()
    sag('  [1] Hin und zurück fliegen (du fliegst hin, sie fliegt allein '
        'zurück, wird aufgezeichnet)')
    sag('  [2] Aufnahme nachfliegen (sie fliegt hin und zurück, wie das '
        'Replay)')
    sag('  [3] Nur zurückfliegen (ab der Stelle, an der sie zuletzt '
        'gelandet ist)')
    sag('  [4] Strecke abfliegen (benannte Strecken, auch mehrfach '
        'oder hintereinander)')
    sag('  [5] Nur aufzeichnen (du fliegst, sie bleibt stehen -- kein '
        'Rückflug)')
    sag('  [6] Strecken verwalten (ansehen, umbenennen, aussortieren, '
        'fliegt nicht)')
    sag('  [7] Beenden')
    wahl = input('\n  Modus (1-7): ').strip()
    sag('  Gewählt: %s' % wahl)
    if wahl == '6':
        # Reine Dateiarbeit: kein Controller, keine Funkverbindung,
        # keine Drohne. Deshalb vor allem anderen und gleich zurück.
        return strecken_verwalten()
    if wahl not in ('1', '2', '3', '4', '5'):
        sag('  Beendet.')
        return 0
    nach = None
    zurueck = None
    if wahl == '2':
        nach = hinflug_waehlen()
        if nach is None:
            return 1
    if wahl == '4':
        nach = strecke_waehlen()
        if nach is None:
            return 1
    if wahl == '3':
        zurueck = nur_zurueck_waehlen()
        if zurueck is None:
            return 1
    sag()

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        sag('  Kein Controller gefunden. Der wird gebraucht.')
        return 1
    pad = pygame.joystick.Joystick(0)
    pad.init()
    sag('  Controller: %s' % pad.get_name())

    bericht = os.path.join(HIER, 'flug_heim_%s.txt' % stempel)
    try:
        return fliegen(pad, stempel, nach, zurueck,
                       ohne_rueckflug=wahl == '5')
    finally:
        strecke_anbieten(stempel, wahl)
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
