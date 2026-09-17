from backend.app.services.rubric import assess

def test_abstains_without_evidence():
    f=assess(1,[]); assert (f.verdict,f.confidence)==("unverifiable","Low")
def test_maps_two_false_ratings_to_contradicted():
    f=assess(1,[{"rating":"False"},{"rating":"Incorrect"}]); assert (f.verdict,f.confidence)==("contradicted","Moderate")
def test_maps_disagreement_to_mixed():
    assert assess(1,[{"rating":"True"},{"rating":"False"}]).verdict=="mixed"
