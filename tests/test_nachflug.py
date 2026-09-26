"""Tests für den Nachflug (Menü 2) in flow_ranger_heimflug.py (ohne Drohne)."""
import math

import pytest
from test_heimweg import VORWAERTS_ECKE, hinflug

from flow_ranger_heimflug import (
    CSV_KOPF,
    MAX_HOEHE,
    MAX_SPEED,
    MAX_YAW,
    TAKT,
    ZIEL_GIER,
    ZIEL_RADIUS,
    Spiegel,
    hinflug_laden,
    letzte_lage,
    spiegel_bauen,
    vorwaerts_bauen,
    wrap,
)


def nachfliegen(bilder, x=0.0, y=0.0, yaw=0.0, max_s=200.0):
    """Rechen-Drohne fliegt den Nachflug ab dem Startpunkt."""
    ende = letzte_lage(bilder)
    assert ende is not None
    h = Spiegel(vorwaerts_bauen(bilder), start_gier=ende[2],
                ziel=(ende[0], ende[1]))
    neben_max = 0.0
    for _ in range(int(max_s / TAKT)):
        vx, vy, gier, _z, neben = h.schritt(x, y, yaw)
        if h.phase == 'nachfliegen':
            neben_max = max(neben_max, neben)
        if h.phase == 'fertig':
            return h, x, y, yaw, neben_max
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x += (c * vx - s * vy) * TAKT
        y += (s * vx + c * vy) * TAKT
        yaw = wrap(yaw + gier * TAKT)
    pytest.fail('nicht angekommen')


def test_vorwaerts_behaelt_reihenfolge_und_richtung():
    bilder, _x, _y, _yaw = hinflug(VORWAERTS_ECKE)
    v = vorwaerts_bauen(bilder)
    assert len(v) == len(bilder) - 40           # 2 s Stillstand fallen weg
    assert v[0] == bilder[0]                    # nicht umgedreht
    assert v[-1] == bilder[-1]
    assert all(b[2] >= 0.0 for b in v)          # Drehrichtung nicht negiert


def test_nachflug_kommt_am_ende_an():
    bilder, x_end, y_end, yaw_end = hinflug(VORWAERTS_ECKE)
    h, x, y, yaw, neben_max = nachfliegen(bilder)
    assert not h.zeit_um
    ende = letzte_lage(bilder)
    assert ende is not None
    assert math.hypot(x - ende[0], y - ende[1]) < 1.5 * ZIEL_RADIUS
    assert abs(wrap(yaw - ende[2])) < ZIEL_GIER
    assert neben_max < 0.05
    # letzte Lage ist die VOR dem letzten Takt, also fast das echte Ende
    assert math.hypot(x_end - ende[0], y_end - ende[1]) < 0.05


def test_nachflug_korrigiert_versatz():
    bilder, _x, _y, _yaw = hinflug(VORWAERTS_ECKE)
    h, x, y, _yaw2, _n = nachfliegen(bilder, x=0.10, y=-0.10, yaw=5.0)
    ende = letzte_lage(bilder)
    assert ende is not None
    assert not h.zeit_um
    assert math.hypot(x - ende[0], y - ende[1]) < 1.5 * ZIEL_RADIUS


def test_spiegel_ziel_standard_ist_start():
    bilder, _x, _y, _yaw = hinflug(VORWAERTS_ECKE)
    h = Spiegel(spiegel_bauen(bilder))
    assert h.p[-1][:2] == (0.0, 0.0)


def test_spiegel_rest_zum_ziel():
    bilder, _x, _y, _yaw = hinflug([(0.4, 0.0, 0.0, 10)])
    h = Spiegel(vorwaerts_bauen(bilder), ziel=(1.0, 2.0))
    h.phase = 'ankommen'
    assert h.rest(1.0, 1.0) == pytest.approx(1.0)


def test_letzte_lage_ueberspringt_luecken():
    bilder = [(0.0, 0.0, 0.0, 0.3, 1.0, 2.0, 30.0),
              (0.0, 0.0, 0.0, 0.3, None, None, None)]
    assert letzte_lage(bilder) == (1.0, 2.0, 30.0)
    assert letzte_lage([bilder[1]]) is None


def test_hinflug_laden(tmp_path):
    def zeile(phase, vx, gier, z, x):
        werte = dict.fromkeys(CSV_KOPF, '')
        werte.update(t_s='0.00', phase=phase, vx_ms=vx, vy_ms='0.000',
                     gier_grad_s=gier, z_soll_m=z, x_m=x, y_m='0.100' if x
                     else '', gier_ist_grad='5.0' if x else '')
        return ';'.join(werte[k] for k in CSV_KOPF)

    pfad = tmp_path / 'heim_hin_test.csv'
    pfad.write_text('\n'.join([
        ';'.join(CSV_KOPF),
        zeile('hin', '0.300', '10.0', '0.300', '0.500'),
        zeile('hin', '9.000', '500.0', '5.000', ''),     # wird geklemmt
        zeile('hand', '0.100', '0.0', '0.300', '0.600'),  # nicht Hinflug
        zeile('hin', 'kaputt', '0.0', '0.300', '0.700'),  # übersprungen
    ]) + '\n', encoding='utf-8')
    bilder = hinflug_laden(str(pfad))
    assert len(bilder) == 2
    assert bilder[0] == (0.3, 0.0, 10.0, 0.3, 0.5, 0.1, 5.0)
    vx, _vy, gier, z, x, _y, _yaw = bilder[1]
    assert (vx, gier, z, x) == (MAX_SPEED, MAX_YAW, MAX_HOEHE, None)


def test_hinflug_laden_fehlt(tmp_path):
    assert hinflug_laden(str(tmp_path / 'gibt_es_nicht.csv')) == []


def test_nachflug_hin_und_zurueck():
    """Menü 2 ganz: Aufnahme nachfliegen (dabei aufzeichnen wie die
    schleife), dann das Geflogene gespiegelt zurück zum Start."""
    aufnahme, _x, _y, _yaw = hinflug(VORWAERTS_ECKE)
    ende = letzte_lage(aufnahme)
    assert ende is not None
    h = Spiegel(vorwaerts_bauen(aufnahme), start_gier=ende[2],
                ziel=(ende[0], ende[1]))
    x = y = yaw = 0.0
    geflogen = []
    for _ in range(int(200.0 / TAKT)):
        vx, vy, gier, z, _n = h.schritt(x, y, yaw)
        if h.phase == 'fertig':
            break
        geflogen.append((vx, vy, gier, z, x, y, yaw))
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x += (c * vx - s * vy) * TAKT
        y += (s * vx + c * vy) * TAKT
        yaw = wrap(yaw + gier * TAKT)
    else:
        pytest.fail('Umkehrpunkt nicht erreicht')
    assert math.hypot(x - ende[0], y - ende[1]) < 1.5 * ZIEL_RADIUS

    r = Spiegel(spiegel_bauen(geflogen), start_gier=0.0)
    for _ in range(int(200.0 / TAKT)):
        vx, vy, gier, _z, _n = r.schritt(x, y, yaw)
        if r.phase == 'fertig':
            break
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x += (c * vx - s * vy) * TAKT
        y += (s * vx + c * vy) * TAKT
        yaw = wrap(yaw + gier * TAKT)
    else:
        pytest.fail('Startpunkt nicht erreicht')
    assert not r.zeit_um
    assert math.hypot(x, y) < 1.5 * ZIEL_RADIUS
    assert abs(wrap(yaw)) < ZIEL_GIER
