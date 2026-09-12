"""Lien registers hold names as filers typed them; the matcher must see through that."""
from bt.systems.s5_hidden_debt import core


def test_filer_abbreviations_normalise_to_the_legal_name():
    assert core("Ironwood Inds Grp L.L.C.") == core("Ironwood Industries Group LLC")
    assert core("Summit Hldgs Inc") == core("Summit Holdings Inc")
    assert core("Pioneer Cap Partners LP") == core("Pioneer Capital Partners LP")


def test_different_companies_stay_different():
    assert core("Ironwood Industries Group LLC") != core("Ironwood Parts Corp")
