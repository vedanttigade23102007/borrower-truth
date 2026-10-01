"""Lien registers hold names as filers typed them; the matcher must see through that."""
from bt.systems.s5_hidden_debt import core


def test_filer_abbreviations_normalise_to_the_legal_name():
    assert core("Ironwood Inds Grp L.L.C.") == core("Ironwood Industries Group LLC")
    assert core("Summit Hldgs Inc") == core("Summit Holdings Inc")
    assert core("Pioneer Cap Partners LP") == core("Pioneer Capital Partners LP")


def test_different_companies_stay_different():
    assert core("Ironwood Industries Group LLC") != core("Ironwood Parts Corp")


def test_same_named_funds_resolve_by_full_legal_name():
    # two different funds share a shortened name; the lien's full name must pick the right one
    from bt.systems.s5_hidden_debt import lender_ids, norm_addr
    names = {"E1": "Silverline Credit Fund LP", "E2": "Silverline Credit Fund LLC", "E3": "Harbor Capital Partners LP"}
    exact, by_core = {}, {}
    for e, n in names.items():
        exact.setdefault(norm_addr(n), set()).add(e)
        by_core.setdefault(core(n), set()).add(e)
    assert lender_ids("Silverline Credit Fund LP", exact, by_core) == {"E1"}
    assert lender_ids("Silverline Credit Fund, L.P.", exact, by_core) == {"E1"}
    assert lender_ids("Harbor Cap Partners", exact, by_core) == {"E3"}  # unique shortened name still resolves
    assert lender_ids("Silverline Credit Fund", exact, by_core) == {"E1", "E2"}  # ambiguous: both kept
