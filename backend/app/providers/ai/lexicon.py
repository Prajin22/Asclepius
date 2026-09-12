"""Multilingual surface forms used by the deterministic provider.

Data only — no logic. Adding a language means adding forms here, never an
`if language == ...` anywhere in the codebase.

This lexicon is intentionally small and demonstrative. It is *not* a medical
terminology resource and must not be presented as one.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Concept:
    """An English canonical value with its surface forms per language."""

    value: str
    forms: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def all_forms(self) -> list[tuple[str, str]]:
        return [(lang, form) for lang, forms in self.forms.items() for form in forms]


SYMPTOMS: tuple[Concept, ...] = (
    Concept("headache", {"en": ("headache", "head ache", "head pain"), "ta": ("தலைவலி",), "hi": ("सिरदर्द", "सर दर्द", "सिर दर्द")}),
    Concept("fever", {"en": ("fever", "temperature high", "high temperature"), "ta": ("காய்ச்சல்", "ஜுரம்"), "hi": ("बुखार", "ज्वर")}),
    Concept("cough", {"en": ("cough",), "ta": ("இருமல்",), "hi": ("खांसी", "खाँसी")}),
    Concept("cold", {"en": ("common cold", "runny nose"), "ta": ("சளி",), "hi": ("जुकाम", "ज़ुकाम")}),
    Concept("dizziness", {"en": ("dizziness", "dizzy", "giddiness", "light headed"), "ta": ("தலைச்சுற்றல்", "மயக்கம்"), "hi": ("चक्कर",)}),
    Concept("vomiting", {"en": ("vomiting", "vomit", "throwing up"), "ta": ("வாந்தி",), "hi": ("उल्टी", "उल्टियाँ")}),
    Concept("nausea", {"en": ("nausea", "feeling sick"), "ta": ("குமட்டல்",), "hi": ("मिचली", "जी मिचलाना")}),
    Concept("stomach pain", {"en": ("stomach pain", "stomach ache", "abdominal pain", "tummy pain"), "ta": ("வயிற்று வலி", "வயிறு வலி"), "hi": ("पेट दर्द", "पेट में दर्द")}),
    Concept("chest pain", {"en": ("chest pain", "chest discomfort"), "ta": ("நெஞ்சு வலி", "மார்பு வலி"), "hi": ("सीने में दर्द", "छाती में दर्द")}),
    Concept("breathlessness", {"en": ("breathlessness", "shortness of breath", "difficulty breathing", "cannot breathe"), "ta": ("மூச்சுத் திணறல்", "மூச்சு திணறல்"), "hi": ("सांस लेने में तकलीफ", "साँस फूलना")}),
    Concept("fatigue", {"en": ("fatigue", "tiredness", "very tired", "weakness"), "ta": ("சோர்வு", "பலவீனம்"), "hi": ("थकान", "कमजोरी", "कमज़ोरी")}),
    Concept("back pain", {"en": ("back pain", "backache"), "ta": ("முதுகு வலி",), "hi": ("पीठ दर्द", "कमर दर्द")}),
    Concept("joint pain", {"en": ("joint pain", "knee pain"), "ta": ("மூட்டு வலி",), "hi": ("जोड़ों का दर्द", "घुटने का दर्द")}),
    Concept("sore throat", {"en": ("sore throat", "throat pain"), "ta": ("தொண்டை வலி",), "hi": ("गले में दर्द", "गला दर्द")}),
    Concept("skin rash", {"en": ("rash", "skin rash", "itching"), "ta": ("தோல் அரிப்பு", "அரிப்பு"), "hi": ("चकत्ते", "खुजली")}),
    Concept("swelling", {"en": ("swelling", "swollen"), "ta": ("வீக்கம்",), "hi": ("सूजन",)}),
    Concept("loose motions", {"en": ("loose motions", "diarrhoea", "diarrhea", "loose stools"), "ta": ("வயிற்றுப்போக்கு",), "hi": ("दस्त", "पेट खराब")}),
    Concept("blurred vision", {"en": ("blurred vision", "blurry vision"), "ta": ("மங்கலான பார்வை",), "hi": ("धुंधला दिखना",)}),
    Concept("sleeplessness", {"en": ("cannot sleep", "sleeplessness", "insomnia"), "ta": ("தூக்கமின்மை",), "hi": ("नींद नहीं आती", "अनिद्रा")}),
)

MEDICATIONS: tuple[Concept, ...] = (
    Concept("paracetamol", {"en": ("paracetamol", "acetaminophen", "dolo", "crocin"), "ta": ("பாராசிட்டமால்",), "hi": ("पैरासिटामोल",)}),
    Concept("ibuprofen", {"en": ("ibuprofen", "brufen"), "hi": ("आइबुप्रोफेन",)}),
    Concept("amlodipine", {"en": ("amlodipine", "amlong"), "ta": ("அம்லோடிபைன்",), "hi": ("एम्लोडिपिन",)}),
    Concept("metformin", {"en": ("metformin", "glycomet"), "ta": ("மெட்ஃபார்மின்",), "hi": ("मेटफॉर्मिन",)}),
    Concept("amoxicillin", {"en": ("amoxicillin", "amoxycillin"), "hi": ("एमोक्सिसिलिन",)}),
    Concept("penicillin", {"en": ("penicillin",), "ta": ("பென்சிலின்",), "hi": ("पेनिसिलिन",)}),
    Concept("aspirin", {"en": ("aspirin", "ecosprin"), "hi": ("एस्पिरिन",)}),
    Concept("atorvastatin", {"en": ("atorvastatin", "atorva"), "hi": ("एटोरवास्टेटिन",)}),
    Concept("omeprazole", {"en": ("omeprazole", "pantoprazole", "pan 40"), "hi": ("ओमेप्राजोल",)}),
    Concept("cetirizine", {"en": ("cetirizine",), "hi": ("सेटिरिज़िन",)}),
    Concept("insulin", {"en": ("insulin",), "ta": ("இன்சுலின்",), "hi": ("इंसुलिन",)}),
    Concept("oral rehydration salts", {"en": ("ors", "oral rehydration"), "ta": ("ஓஆர்எஸ்",), "hi": ("ओआरएस",)}),
    Concept("thyroxine", {"en": ("thyroxine", "eltroxin", "thyronorm"), "hi": ("थायरोक्सिन",)}),
)

CONDITIONS: tuple[Concept, ...] = (
    Concept("diabetes", {"en": ("diabetes", "sugar problem", "sugar disease"), "ta": ("நீரிழிவு", "சர்க்கரை நோய்"), "hi": ("मधुमेह", "शुगर")}),
    Concept("hypertension", {"en": ("hypertension", "high blood pressure", "high bp", "bp problem"), "ta": ("இரத்த அழுத்தம்", "உயர் இரத்த அழுத்தம்"), "hi": ("उच्च रक्तचाप", "बीपी की समस्या", "हाई बीपी")}),
    Concept("asthma", {"en": ("asthma",), "ta": ("ஆஸ்துமா",), "hi": ("दमा", "अस्थमा")}),
    Concept("thyroid disorder", {"en": ("thyroid",), "ta": ("தைராய்டு",), "hi": ("थायराइड",)}),
    Concept("tuberculosis", {"en": ("tuberculosis", "tb"), "ta": ("காசநோய்",), "hi": ("टीबी", "क्षय रोग")}),
    Concept("typhoid", {"en": ("typhoid",), "ta": ("டைபாய்டு",), "hi": ("टाइफाइड",)}),
    Concept("heart attack", {"en": ("heart attack", "myocardial infarction"), "ta": ("மாரடைப்பு",), "hi": ("दिल का दौरा",)}),
    Concept("surgery", {"en": ("surgery", "operation", "operated"), "ta": ("அறுவை சிகிச்சை",), "hi": ("ऑपरेशन", "सर्जरी")}),
    Concept("pregnancy", {"en": ("pregnant", "pregnancy"), "ta": ("கர்ப்பம்",), "hi": ("गर्भवती", "गर्भावस्था")}),
)

# Negation cues. English negates before the term; Tamil and Hindi after it.
NEGATION_BEFORE: dict[str, tuple[str, ...]] = {
    "en": ("no ", "not ", "without ", "never had ", "denies ", "don't have ", "do not have ", "haven't had "),
}
NEGATION_AFTER: dict[str, tuple[str, ...]] = {
    "ta": ("இல்லை", "கிடையாது"),
    "hi": ("नहीं", "नही"),
}

# A negation only applies inside its own clause: "cough but no fever" negates
# fever, not cough. These end the window searched for a negation cue.
CLAUSE_BOUNDARY_CHARS = ".,;:।!?\n"
CLAUSE_BOUNDARY_WORDS: dict[str, tuple[str, ...]] = {
    "en": ("but", "however", "although", "though"),
    "ta": ("ஆனால்", "இருந்தாலும்"),
    "hi": ("लेकिन", "मगर", "पर "),
}

NUMBER_WORDS: dict[str, dict[str, int]] = {
    "en": {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
           "eight": 8, "nine": 9, "ten": 10, "couple of": 2, "few": 3},
    "ta": {"ஒரு": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8,
           "ஒன்பது": 9, "பத்து": 10},
    "hi": {"एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8,
           "नौ": 9, "दस": 10},
}

# Surface form -> canonical English unit.
TIME_UNITS: dict[str, dict[str, str]] = {
    "en": {"hour": "hour", "hours": "hour", "day": "day", "days": "day", "week": "week", "weeks": "week",
           "month": "month", "months": "month", "year": "year", "years": "year"},
    "ta": {"மணி": "hour", "மணிநேரம்": "hour", "நாள்": "day", "நாட்கள்": "day", "நாட்களாக": "day",
           "நாளாக": "day", "வாரம்": "week", "வாரங்கள்": "week", "வாரமாக": "week", "மாதம்": "month",
           "மாதங்கள்": "month", "மாதமாக": "month", "வருடம்": "year", "ஆண்டு": "year", "வருடங்களாக": "year"},
    "hi": {"घंटे": "hour", "घंटा": "hour", "दिन": "day", "दिनों": "day", "सप्ताह": "week", "हफ्ते": "week",
           "हफ़्ते": "week", "महीना": "month", "महीने": "month", "साल": "year", "वर्ष": "year"},
}

# Explicit statements that the patient has no allergies (including document forms).
NO_ALLERGY_PATTERNS: dict[str, tuple[str, ...]] = {
    "en": ("no known allergies", "no known drug allergies", "no allergies", "no allergy",
           "not allergic to anything", "no drug allergies", "allergies: none", "allergies: nil",
           "allergy: none", "allergies: nkda", "nkda"),
    "ta": ("ஒவ்வாமை இல்லை", "ஒவ்வாமை கிடையாது", "அலர்ஜி இல்லை"),
    "hi": ("कोई एलर्जी नहीं", "एलर्जी नहीं", "कोई एलर्जी नही"),
}

# Patterns that introduce an allergen; group 1 is the allergen.
ALLERGY_PATTERNS: dict[str, tuple[str, ...]] = {
    "en": (r"allergic to ([A-Za-z][A-Za-z \-]{1,40})", r"allergy to ([A-Za-z][A-Za-z \-]{1,40})",
           r"([A-Za-z][A-Za-z\-]{2,25}) allergy",
           # Document form: "Allergies: Penicillin".
           r"allerg(?:y|ies)\s*[:\-]\s*([A-Za-z][A-Za-z \-]{1,40})"),
    "ta": (r"([^\s,\.]{2,25})\s*(?:மருந்துக்கு\s*)?ஒவ்வாமை", r"([^\s,\.]{2,25})\s*அலர்ஜி"),
    "hi": (r"([^\s,।]{2,25})\s*से\s*एलर्जी", r"([^\s,।]{2,25})\s*की\s*एलर्जी"),
}

# Words for blood sugar in scripts the labelled-measurement pattern cannot read.
SUGAR_WORDS: tuple[str, ...] = ("sugar", "glucose", "சர்க்கரை", "शुगर", "ग्लूकोज", "शर्करा")

# Words that turn "N days" into a future interval ("follow up in 4 weeks",
# "every 8 hours") rather than how long something has lasted.
INTERVAL_WORDS: tuple[str, ...] = ("in", "after", "within", "every", "each", "next", "per")

# Words trimmed from the edges of a measurement label ("Sugar was 210" -> "sugar").
LABEL_FILLER: frozenset[str] = frozenset(
    {"was", "is", "are", "of", "level", "levels", "reading", "value", "result", "and", "with", "the",
     "my", "at", "on", "in", "today", "yesterday", "i", "had", "have", "has", "got", "checked", "measured",
     "showed", "shows", "came", "back", "about", "around"}
)

# Cues that attribute a statement to a relative rather than the patient.
# Checked before self cues: "என் அப்பா" contains "என்", "मेरे पिता" contains "मेरे".
FAMILY_CUES: dict[str, tuple[str, ...]] = {
    "en": ("my father", "my mother", "my dad", "my mum", "my mom", "my brother", "my sister",
           "my son", "my daughter", "my wife", "my husband", "my grandfather", "my grandmother",
           "my uncle", "my aunt", "my parents", "my family", "in my family", "family history of",
           "father has", "mother has", "father had", "mother had", "runs in the family"),
    "ta": ("என் அப்பா", "என் அம்மா", "என் தந்தை", "என் தாய்", "எனது தந்தை", "எனது தாய்",
           "என் சகோதரர்", "என் சகோதரி", "என் மனைவி", "என் கணவர்", "என் மகன்", "என் மகள்",
           "அப்பாவுக்கு", "அம்மாவுக்கு", "தந்தைக்கு", "தாய்க்கு", "குடும்பத்தில்"),
    "hi": ("मेरे पिता", "मेरी माता", "मेरे पिताजी", "मेरी माँ", "मेरी मां", "मेरे भाई", "मेरी बहन",
           "मेरी पत्नी", "मेरे पति", "मेरे बेटे", "मेरी बेटी", "मेरे परिवार", "परिवार में",
           "पिताजी को", "माँ को", "पिता को", "माता को"),
}

# Cues that attribute a statement to the patient themselves.
SELF_CUES: dict[str, tuple[str, ...]] = {
    "en": ("i have", "i am", "i feel", "i had", "i've", "i take", "i was", "my "),
    "ta": ("எனக்கு", "என்னுடைய", "நான்"),
    "hi": ("मुझे", "मैं", "मेरा", "मेरी", "मेरे"),
}

# Phrases that mark what follows as past history.
HISTORY_MARKERS: dict[str, tuple[str, ...]] = {
    "en": ("diagnosed with", "history of", "suffering from", "i have", "i had", "since childhood"),
    "ta": ("கண்டறியப்பட்டது", "வரலாறு", "உள்ளது", "இருந்தது"),
    "hi": ("पता चला", "इतिहास", "से पीड़ित", "मुझे है", "था"),
}
