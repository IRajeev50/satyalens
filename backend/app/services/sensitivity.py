"""Deterministic gate for politically sensitive and contested public claims."""
from __future__ import annotations

import re
from dataclasses import dataclass

# English and Hindi cues for elections, political actors, identity conflict and public order.
_CUES = {
    "election": ("election", "elections", "electoral", "polling", "ballot", "evm", "exit poll",
                 "vote counting", "मतदान", "चुनाव", "ईवीएम"),
    "political_figure": ("prime minister", "chief minister", "home minister", "president", "governor",
                         "minister", "mla", "mp ", "opposition leader", "political party", "ruling party",
                         "प्रधानमंत्री", "मुख्यमंत्री", "गृह मंत्री", "मंत्री", "नेता", "विधायक", "सांसद"),
    "identity_conflict": ("communal", "religious clash", "caste violence", "caste conflict", "riot",
                          "riots", "दंगा", "दंगे", "सांप्रदायिक", "जातीय हिंसा", "जाति हिंसा"),
    "public_order": ("protester", "protesters", "protest", "curfew", "police firing", "police beating",
                     "mob violence", "public disorder", "arrested", "raid", "छापा", "गिरफ्तार",
                     "प्रदर्शनकारी", "कर्फ्यू", "पुलिस गोलीबारी"),
}

@dataclass(frozen=True)
class SensitivityResult:
    flagged: bool
    categories: tuple[str, ...]
    matches: tuple[str, ...]


def detect(text: str) -> SensitivityResult:
    normalized = re.sub(r"\s+", " ", (text or "").casefold())
    categories, matches = [], []
    for category, cues in _CUES.items():
        found = [cue.strip() for cue in cues if cue.casefold() in normalized]
        if found:
            categories.append(category)
            matches.extend(found)
    return SensitivityResult(bool(categories), tuple(categories), tuple(sorted(set(matches))))
