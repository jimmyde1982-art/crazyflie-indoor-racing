"""Tests für das Neuverbinden nach Funkabbruch in flow_ranger_heimflug.py
(ohne Drohne)."""
from flow_ranger_heimflug import START_VERSUCHE, funk_am_boden, mit_neustart

FUNK = ('vor dem Start abgebrochen: Funkverbindung verloren', False)
GUT = ('Taste B gedrückt', False)


class FakeR:
    """Nur die Felder, die mit_neustart und funk_am_boden brauchen."""

    def __init__(self, retten=True, in_luft=False):
        self.funk_weg = False
        self.funk_weg_in_luft = in_luft
        self.in_luft = False
        self.gesperrt = False
        self.retten_klappt = retten
        self.gerettet = 0

    def funk_retten(self):
        self.gerettet += 1
        if self.retten_klappt:
            self.funk_weg = False
        return self.retten_klappt


def flug_folge(r, gruende):
    """Liefert der Reihe nach die Gründe, setzt funk_weg wie echt."""
    liste = list(gruende)
    aufrufe = []

    def flug():
        grund = liste.pop(0)
        aufrufe.append(grund)
        r.funk_weg = grund is FUNK
        return grund
    return flug, aufrufe


def test_funk_am_boden_erkannt():
    r = FakeR()
    r.funk_weg = True
    assert funk_am_boden(r, FUNK)


def test_funk_in_luft_kein_neustart():
    r = FakeR(in_luft=True)
    r.funk_weg = True
    assert not funk_am_boden(r, FUNK)


def test_anderer_grund_kein_neustart():
    r = FakeR()
    assert not funk_am_boden(r, GUT)
    assert not funk_am_boden(r, None)


def test_neustart_nach_funkabbruch():
    r = FakeR()
    flug, aufrufe = flug_folge(r, [FUNK, GUT])
    assert mit_neustart(r, flug) is GUT
    assert len(aufrufe) == 2
    assert r.gerettet == 1


def test_ohne_funkabbruch_nur_ein_flug():
    r = FakeR()
    flug, aufrufe = flug_folge(r, [GUT])
    assert mit_neustart(r, flug) is GUT
    assert len(aufrufe) == 1
    assert r.gerettet == 0


def test_neuverbinden_klappt_nicht():
    r = FakeR(retten=False)
    flug, aufrufe = flug_folge(r, [FUNK, GUT])
    assert mit_neustart(r, flug) is FUNK
    assert len(aufrufe) == 1


def test_hoechstens_start_versuche():
    r = FakeR()
    flug, aufrufe = flug_folge(r, [FUNK] * (START_VERSUCHE + 2))
    assert mit_neustart(r, flug) is FUNK
    assert len(aufrufe) == START_VERSUCHE
