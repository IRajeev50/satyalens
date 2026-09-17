import re, unicodedata
from dataclasses import dataclass
from langdetect import detect, DetectorFactory, LangDetectException
from unidecode import unidecode
DetectorFactory.seed=0
@dataclass(frozen=True)
class LanguageInfo:
    code: str; label: str; is_code_switched: bool; queries: list[str]

def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC",text).split())
def analyze(text: str) -> LanguageInfo:
    clean=normalize(text); devanagari=bool(re.search(r"[\u0900-\u097f]",clean)); latin=bool(re.search(r"[A-Za-z]",clean))
    try: code=detect(clean) if len(clean)>=20 else ("hi" if devanagari else "en")
    except LangDetectException: code="unknown"
    switched=devanagari and latin
    label="Hinglish" if switched else "Hindi" if code in {"hi","mr","ne"} and devanagari else "English" if code=="en" else code
    queries=[clean]; roman=unidecode(clean)
    if devanagari and roman.lower()!=clean.lower(): queries.append(roman)
    return LanguageInfo(code,label,switched,queries)
