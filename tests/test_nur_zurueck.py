"""Tests für 'Nur zurückfliegen' (Menü 3, Version 2.6) in
flow_ranger_heimflug.py (ohne Drohne)."""
import math
import os

import pytest
from test_heimweg import VORWAERTS_ECKE, hinflug

from flow_ranger_heimflug import (
    TAKT,
    ZIEL_GIER,
    ZIEL_RADIUS,
    Spiegel,
    hinflug_laden,
    lage_lesen,
    lage_speichern,
    letzter_flug,
    rest_rueckweg,
    spiegel_bauen,
    start_richtung,
    wrap,
)


def heimfliegen(bilder, x, y, yaw, max_s=200.0):
    """Rechen-Drohne fliegt den Rest-Rückweg ab (x, y, yaw)."""
    rest, abstand = rest_rueckweg(bilder, x, y)
    start = start_richtung(bilder)
    assert start is not None
    h = Spiegel(rest, start_gier=start)
    for _ in range(int(max_s / TAKT)):
        vx, vy, gier, _z, _n = h.schritt(x, y, yaw)
        if h.phase == 'fertig':
            return h, x, y, yaw, abstand, len(rest)
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        x += (c * vx - s * vy) * TAKT
        y += (s * vx + c * vy) * TAKT
        yaw = wrap(yaw + gier * TAKT)
    pytest.fail('nicht angekommen')


def test_rest_ab_ende_ist_ganzer_rueckweg():
    bilder, x, y, _yaw = hinflug(VORWAERTS_ECKE)
    rest, abstand = rest_rueckweg(bilder, x, y)
    assert rest == spiegel_bauen(bilder)
    assert abstand < 0.05


def test_rest_ab_mitte_kommt_heim():
    """Unterwegs gelandet, mitten im Wenden (Nase 120 Grad daneben)."""
    bilder, _x, _y, _yaw = hinflug(VORWAERTS_ECKE)
    mitte = bilder[len(bilder) * 2 // 3]
    x, y, yaw = mitte[4], mitte[5], wrap(mitte[6] + 120.0)
    h, x, y, yaw, abstand, n = heimfliegen(bilder, x, y, yaw)
    assert abstand < 0.03
    assert n < len(spiegel_bauen(bilder))       # nicht den ganzen Weg
    assert not h.zeit_um
    assert math.hypot(x, y) < 1.5 * ZIEL_RADIUS
    assert abs(wrap(yaw)) < ZIEL_GIER


def test_rest_neben_dem_weg_meldet_abstand():
    bilder, _x, _y, _yaw = hinflug([(0.4, 0.0, 0.0, 50)])   # 1 m gerade
    _rest, abstand = rest_rueckweg(bilder, 0.5, 0.6)
    assert abstand == pytest.approx(0.6, abs=0.02)


def test_rest_ohne_wegdaten():
    rest, abstand = rest_rueckweg([(0.3, 0.0, 0.0, 0.3, None, None, None)],
                                  1.0, 1.0)
    assert abstand == math.inf
    assert len(rest) == 1


def test_start_richtung():
    assert start_richtung([(0, 0, 0, 0.3, None, None, None),
                           (0, 0, 0, 0.3, 1.0, 1.0, 12.5)]) == 12.5
    assert start_richtung([]) is None


def test_lage_speichern_und_lesen(tmp_path):
    pfad = str(tmp_path / 'heim_lande_x.csv')
    lage_speichern(pfad, (4.6621, 0.4834, 134.93))
    assert lage_lesen(pfad) == pytest.approx((4.662, 0.483, 134.93))
    lage_speichern(pfad, None)                  # abgehoben: unbekannt
    assert lage_lesen(pfad) is None


def test_lage_lesen_fehlt_oder_kaputt(tmp_path):
    assert lage_lesen(str(tmp_path / 'gibt_es_nicht.csv')) is None
    kaputt = tmp_path / 'kaputt.csv'
    kaputt.write_text('x_m;y_m;gier_grad\n1.0;abc;3\n', encoding='utf-8')
    assert lage_lesen(str(kaputt)) is None
    leer = tmp_path / 'leer.csv'
    leer.write_text('x_m;y_m;gier_grad\n', encoding='utf-8')
    assert lage_lesen(str(leer)) is None


def test_letzter_flug_neuester_hin_oder_nach(tmp_path):
    assert letzter_flug(str(tmp_path)) is None
    for name, t in (('heim_hin_a.csv', 100), ('heim_nach_b.csv', 300),
                    ('heim_hin_c.csv', 200), ('heim_rueck_d.csv', 400),
                    ('heim_rest_e.csv', 500)):
        (tmp_path / name).write_text('', encoding='utf-8')
        os.utime(tmp_path / name, (t, t))
    pfad = letzter_flug(str(tmp_path))
    assert pfad is not None
    assert os.path.basename(pfad) == 'heim_nach_b.csv'


def test_nachflug_laden_mit_hand(tmp_path):
    pfad = tmp_path / 'heim_nach_x.csv'
    pfad.write_text(
        'phase;vx_ms;vy_ms;gier_grad_s;z_soll_m;x_m;y_m;gier_ist_grad\n'
        'nach;0.3;0;0;0.3;0.1;0;0\n'
        'hand;0.2;0;0;0.3;0.2;0;0\n'
        'hin;0.1;0;0;0.3;0.3;0;0\n', encoding='utf-8')
    assert len(hinflug_laden(str(pfad), ('nach', 'hand'))) == 2
    assert len(hinflug_laden(str(pfad))) == 1
