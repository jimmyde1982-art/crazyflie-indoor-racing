"""Tests für das Aneinanderhängen von Strecken (ohne Drohne).

Reine Rechnung: aus mehreren Aufnahmen wird ein Weg. Geprüft wird, dass
an der Nahtstelle nichts springt und dass die Fahrbefehle unangetastet
bleiben -- sie gelten im Rahmen der Drohne, nicht im Raum.
"""

import math

import pytest

from flow_ranger_heimflug import (
    bilder_ketten,
    bilder_versetzen,
    erste_lage,
    letzte_lage,
    spannweite,
)


def gerade(laenge_m=2.0, yaw=0.0, x0=0.0, y0=0.0, takte=40, z=0.50):
    """Eine gerade Fahrt nach vorn, aufgezeichnet aus Sicht des Raums."""
    schritt = laenge_m / takte
    bilder = []
    for i in range(takte + 1):
        s = i * schritt
        bilder.append((0.40, 0.0, 0.0, z,
                       x0 + s * math.cos(math.radians(yaw)),
                       y0 + s * math.sin(math.radians(yaw)),
                       yaw))
    return bilder


def lage_nah(a, b, toleranz=1e-6):
    return all(abs(x - y) < toleranz for x, y in zip(a, b, strict=True))


# ------------------------------------------------------------ versetzen

def test_versetzen_ohne_alles_aendert_nichts():
    bilder = gerade()
    assert bilder_versetzen(bilder, 0.0, 0.0, 0.0) == bilder


def test_versetzen_verschiebt_die_positionen():
    aus = bilder_versetzen(gerade(), 1.5, -0.5, 0.0)
    assert lage_nah(erste_lage(aus), (1.5, -0.5, 0.0))
    assert lage_nah(letzte_lage(aus), (3.5, -0.5, 0.0))


def test_versetzen_dreht_um_den_nullpunkt():
    """90 Grad: aus 2 m nach +x werden 2 m nach +y."""
    aus = bilder_versetzen(gerade(), 0.0, 0.0, 90.0)
    assert lage_nah(letzte_lage(aus), (0.0, 2.0, 90.0), 1e-9)


def test_versetzen_laesst_die_fahrbefehle_in_ruhe():
    """vx, vy, Drehrate und Höhe gelten im Rahmen der Drohne. Wer sie
    mitdrehte, würde aus einer Vorwärtsfahrt eine Seitwärtsfahrt
    machen."""
    versetzt = bilder_versetzen(gerade(), 3.0, 2.0, 47.0)
    for alt, neu in zip(gerade(), versetzt, strict=True):
        assert alt[:4] == neu[:4]


def test_versetzen_haelt_die_blickrichtung_im_bereich():
    """350 Grad plus 20 Grad ist 10, nicht 370."""
    aus = bilder_versetzen(gerade(yaw=350.0), 0.0, 0.0, 20.0)
    assert lage_nah(erste_lage(aus), (0.0, 0.0, 10.0), 1e-9)


def test_versetzen_vertraegt_takte_ohne_wegdaten():
    bilder = [(0.4, 0.0, 0.0, 0.5, None, None, None)] + gerade()
    aus = bilder_versetzen(bilder, 1.0, 0.0, 0.0)
    assert aus[0][4] is None and aus[0][5] is None
    assert lage_nah(erste_lage(aus), (1.0, 0.0, 0.0))


# ---------------------------------------------------------------- ketten

def test_ein_teil_bleibt_wie_es_ist():
    bilder = gerade()
    assert bilder_ketten([bilder]) == bilder


def test_leere_teile_fallen_weg():
    bilder = gerade()
    assert bilder_ketten([[], bilder, []]) == bilder


def test_zwei_gerade_ergeben_die_doppelte_laenge():
    aus = bilder_ketten([gerade(2.0), gerade(2.0)])
    assert lage_nah(letzte_lage(aus), (4.0, 0.0, 0.0), 1e-9)


def test_an_der_naht_springt_nichts():
    """Der erste Punkt des zweiten Teils muss auf dem letzten Punkt des
    ersten liegen. Sonst zieht die Wegkorrektur die Drohne quer durch
    den Raum."""
    eins, zwei = gerade(2.0), gerade(1.0)
    aus = bilder_ketten([eins, zwei])
    naht = aus[len(eins)]
    assert lage_nah((naht[4], naht[5]), letzte_lage(eins)[:2], 1e-9)


def test_der_zweite_teil_folgt_der_blickrichtung():
    """Endet der erste Teil mit Blick nach 90 Grad, läuft der zweite
    nach +y weiter, nicht nach +x."""
    ecke = gerade(2.0)
    ecke[-1] = ecke[-1][:6] + (90.0,)
    aus = bilder_ketten([ecke, gerade(1.0)])
    assert lage_nah(letzte_lage(aus), (2.0, 1.0, 90.0), 1e-6)


def runde(laenge_m=1.0, takte=20):
    """Hin und rückwärts wieder zurück, ohne zu drehen: sie endet dort,
    wo sie anfing, und schaut noch in dieselbe Richtung."""
    hin = gerade(laenge_m, takte=takte)
    zurueck = [(-0.40, 0.0, 0.0, b[3], b[4], b[5], b[6])
               for b in reversed(hin)]
    return hin + zurueck


def test_eine_schleife_bleibt_an_ort_und_stelle():
    """Eine Runde, die dort endet, wo sie anfing, darf beim zweiten Mal
    nicht davonwandern -- sonst wäre mehrfach abspielen sinnlos."""
    aus = bilder_ketten([runde(), runde()])
    assert lage_nah(letzte_lage(aus), letzte_lage(runde()), 1e-9)


def test_eine_schleife_bleibt_auch_nach_fuenf_runden_im_raum():
    """Fünf Runden dürfen die Spannweite nicht vergrößern."""
    einmal = spannweite(runde())
    fuenfmal = spannweite(bilder_ketten([runde()] * 5))
    assert fuenfmal[0] == pytest.approx(einmal[0], abs=1e-9)
    assert fuenfmal[1] == pytest.approx(einmal[1], abs=1e-9)


def test_dreimal_ist_dreimal_so_lang():
    aus = bilder_ketten([gerade(1.0)] * 3)
    assert lage_nah(letzte_lage(aus), (3.0, 0.0, 0.0), 1e-9)


def test_teil_ohne_wegdaten_wird_angehaengt():
    """Versetzen lässt sich nur, was Positionen hat. Der Rest wird
    trotzdem mitgenommen, statt verloren zu gehen."""
    blind = [(0.4, 0.0, 0.0, 0.5, None, None, None)] * 5
    aus = bilder_ketten([gerade(), blind])
    assert len(aus) == len(gerade()) + 5


# ----------------------------------------------------------- spannweite

def test_spannweite_einer_geraden():
    x, y = spannweite(gerade(2.0))
    assert x == pytest.approx(2.0)
    assert y == pytest.approx(0.0)


def test_spannweite_waechst_beim_mehrfachen_abspielen():
    """Genau darum muss vor dem Start gewarnt werden: dreimal 2 m
    geradeaus sind 6 m und passen in keinen Raum hier."""
    x, _ = spannweite(bilder_ketten([gerade(2.0)] * 3))
    assert x == pytest.approx(6.0)


def test_spannweite_ohne_wegdaten_ist_null():
    assert spannweite([(0.4, 0.0, 0.0, 0.5, None, None, None)]) == (0.0, 0.0)
