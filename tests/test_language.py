from backend.app.services.language import analyze, normalize

def test_hinglish_detects_code_switch_and_transliteration_query():
    x=analyze("सरकार ने new scheme launch की है in Delhi")
    assert x.is_code_switched and x.label=="Hinglish" and len(x.queries)==2
def test_unicode_and_space_normalization():
    assert normalize("A   claim\n here") == "A claim here"
