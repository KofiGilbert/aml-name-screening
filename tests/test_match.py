from screening.match import jaro_winkler, phonetic_key, similarity, token_set_ratio


def test_identical_names_score_one():
    assert similarity("Viktor Petrov", "Viktor Petrov").combined == 1.0


def test_case_and_punctuation_differences_score_one():
    # These are the same party; the canonical forms are equal, so the weighted
    # components must not drag the result below a perfect score.
    assert similarity("Acme Holdings Ltd", "ACME HOLDINGS, LIMITED").combined == 1.0


def test_reordered_name_scores_high():
    assert similarity("Sergei Ivanov", "Ivanov, Sergei").combined > 0.75


def test_transliteration_variant_is_caught():
    assert similarity("Mohammed Al-Amin", "Muhammad Al Amin").combined > 0.70


def test_unrelated_names_score_low():
    assert similarity("John Smith", "Olena Kovalenko").combined < 0.45


def test_empty_side_scores_zero():
    assert similarity("", "Viktor Petrov").combined == 0.0


def test_jaro_winkler_bounds():
    assert jaro_winkler("abc", "abc") == 1.0
    assert jaro_winkler("abc", "") == 0.0
    assert 0.0 <= jaro_winkler("martha", "marhta") <= 1.0


def test_token_set_ratio_is_jaccard():
    assert token_set_ratio("a b", "b a") == 1.0
    assert token_set_ratio("a b", "c d") == 0.0


def test_phonetic_key_collapses_vowel_variants():
    assert phonetic_key("Mohammed") == phonetic_key("Muhammad")


def test_phonetic_key_keeps_initial_vowel():
    # Dropping a leading vowel would collapse Ali and Li into one key.
    assert phonetic_key("Ali") != phonetic_key("Li")
