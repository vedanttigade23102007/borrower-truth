"""The bank's name is one setting (buyer review gap 6, kept private). Wells Fargo is the worked example and the default;
for any other bank, its own liens are skipped and Wells Fargo's become another lender's."""
import pytest

from bt.common import bank
from bt.datagen.generate import main as generate
from bt.pipeline.run import run as pipeline


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    out = tmp_path_factory.mktemp("bank") / "book"
    generate(["--borrowers", "30", "--scale", "0.2", "--seed", "13", "--out", str(out)])
    return out


def lien_lenders(sigs):
    return {s.explanation.split("'")[1] for s in sigs if s.type in ("COMPETING_LIEN", "UNDISCLOSED_SECURED_PARTY")}


def test_the_banks_own_liens_are_never_hidden_debt(book, monkeypatch):
    sigs, _, _ = pipeline(str(book), 23)
    assert not any(bank.is_bank(n) for n in lien_lenders(sigs))  # the default: Wells Fargo's own liens are skipped

    monkeypatch.setattr(bank, "NAME", "First Example Bank")
    other, _, _ = pipeline(str(book), 23)
    # run by another bank, Wells Fargo's liens are another lender's: undisclosed ones are now clues
    assert any("WELLS FARGO" in n.upper() for n in lien_lenders(other))


def test_explanations_name_the_bank_that_runs_it(book, monkeypatch):
    monkeypatch.setattr(bank, "NAME", "First Example Bank")
    sigs, _, _ = pipeline(str(book), 23)
    named = [s.explanation for s in sigs if "disclosed to" in s.explanation]
    assert named and all("disclosed to First Example Bank" in e for e in named)
