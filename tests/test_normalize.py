import pytest

from screening.normalize import normalize, strip_accents, tokens


def test_accents_fold_to_base_letters():
    assert strip_accents("José Müller-Ødegård") == "Jose Muller-Odegard"


def test_corporate_suffixes_are_dropped():
    assert normalize("Acme Holdings Ltd") == normalize("ACME Holdings, Limited")


def test_honorifics_are_dropped():
    assert normalize("Dr. Viktor Petrov") == "viktor petrov"


def test_all_suffix_name_does_not_normalize_to_empty():
    # "The Company Ltd" is all noise words; returning "" would make it match
    # everything, so the fallback keeps the raw tokens instead.
    assert normalize("The Company Ltd") != ""


def test_empty_input_returns_empty():
    assert normalize("") == ""
    assert normalize("   ") == ""


def test_tokens_are_order_independent():
    assert tokens("Sergei Ivanov") == tokens("Ivanov, Sergei")
