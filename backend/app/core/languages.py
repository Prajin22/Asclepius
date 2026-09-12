"""Language registry.

The single place that knows which languages exist and what we support for each.
Nothing else in the codebase should branch on a specific language code.
"""

from dataclasses import dataclass
from enum import StrEnum


class LanguageCode(StrEnum):
    EN = "en"
    HI = "hi"
    TA = "ta"
    TE = "te"
    KN = "kn"
    ML = "ml"
    MR = "mr"
    BN = "bn"
    GU = "gu"
    PA = "pa"
    OR = "or"
    AS = "as"


class AISupport(StrEnum):
    """Honest status of AI language processing for a language."""

    PLANNED = "planned"  # architecture ready, nothing built/evaluated
    EXPERIMENTAL = "experimental"  # built, not yet evaluated on our eval set
    EVALUATED = "evaluated"  # passed our synthetic evaluation set


@dataclass(frozen=True)
class LanguageInfo:
    code: LanguageCode
    english_name: str
    native_name: str
    script: str
    ui_available: bool
    ai_support: AISupport


LANGUAGES: dict[LanguageCode, LanguageInfo] = {
    info.code: info
    for info in [
        LanguageInfo(LanguageCode.EN, "English", "English", "Latin", True, AISupport.PLANNED),
        LanguageInfo(LanguageCode.HI, "Hindi", "हिन्दी", "Devanagari", True, AISupport.PLANNED),
        LanguageInfo(LanguageCode.TA, "Tamil", "தமிழ்", "Tamil", True, AISupport.PLANNED),
        LanguageInfo(LanguageCode.TE, "Telugu", "తెలుగు", "Telugu", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.KN, "Kannada", "ಕನ್ನಡ", "Kannada", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.ML, "Malayalam", "മലയാളം", "Malayalam", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.MR, "Marathi", "मराठी", "Devanagari", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.BN, "Bengali", "বাংলা", "Bengali", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.GU, "Gujarati", "ગુજરાતી", "Gujarati", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.PA, "Punjabi", "ਪੰਜਾਬੀ", "Gurmukhi", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.OR, "Odia", "ଓଡ଼ିଆ", "Odia", False, AISupport.PLANNED),
        LanguageInfo(LanguageCode.AS, "Assamese", "অসমীয়া", "Bengali-Assamese", False, AISupport.PLANNED),
    ]
}

DEFAULT_LANGUAGE = LanguageCode.EN
