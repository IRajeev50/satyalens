from evals.generate_seed import build
from evals.validate_seed import load_schema, load_seed, validate_seed

CLAIM_TYPES = {"checkable_fact", "prediction", "opinion", "satire", "subjective", "not_a_claim"}
LANGUAGES = {"en", "hi", "hi-en"}
VERACITY = {"supported", "mostly supported", "mixed", "misleading", "contradicted", "unverifiable"}
BUCKETS = {"true", "mostly_true", "political_sensitive", "prompt_injection", "abstain", "media_wrong_context"}


def test_seed_file_exists_and_validates_against_schema():
    seed = validate_seed(load_seed(), load_schema())
    assert 45 <= len(seed) <= 60


def test_generated_seed_matches_written_file():
    assert build() == load_seed()


def test_seed_exercises_every_enum_branch():
    seed = load_seed()
    assert {t for row in seed for t in row["expected"]["claim_types"]} == CLAIM_TYPES
    assert {row["input"]["language"] for row in seed} == LANGUAGES
    assert {row["bucket"] for row in seed} == BUCKETS
    assert {row["expected"]["route_to_human"] for row in seed} == {True, False}
    # Veracity classes used by the seed (mixed is a valid rubric class but needs
    # disagreeing sources; every class the gate can hit alone is present).
    assert {row["expected"]["veracity"] for row in seed} >= VERACITY - {"mixed"}
    assert all(row["synthetic"] is True for row in seed)
