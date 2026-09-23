"""Deterministic local provider.

This is a *demonstration implementation of the same contract* as the real
providers — not a separate fake path. It runs the identical pipeline
(detect → normalise → extract), returns the identical schemas, produces real
evidence offsets into the source, and is subject to the same evidence
validation. It needs no credentials and no network, so a demo cannot fail on an
outage, a quota or latency.

It is rule-based: a small lexicon plus conservative patterns. It finds only
what it recognises, never infers, and marks what it could not parse. Its
quality is measured by the same evaluation harness as any other provider
(`backend/evaluation/`), and it must never be described as clinical-grade.
"""

import re
import time
import unicodedata

from app.core.languages import LanguageCode
from app.models.enums import FactCategory, FactSubject
from app.providers.ai.base import (
    AIProvider,
    AIUsage,
    Evidence,
    ExtractedFact,
    ExtractionResult,
    LanguageDetection,
    NormalizationResult,
    SummaryOrganisation,
)
from app.providers.ai.lexicon import (
    ALLERGY_PATTERNS,
    CLAUSE_BOUNDARY_CHARS,
    CLAUSE_BOUNDARY_WORDS,
    CONDITIONS,
    FAMILY_CUES,
    INTERVAL_WORDS,
    LABEL_FILLER,
    SUGAR_WORDS,
    MEDICATIONS,
    NEGATION_AFTER,
    NEGATION_BEFORE,
    NO_ALLERGY_PATTERNS,
    NUMBER_WORDS,
    SYMPTOMS,
    TIME_UNITS,
    Concept,
)
from app.providers.ai.prompts import CASE_SUMMARY, EXTRACTION, LANGUAGE_DETECTION, NORMALIZATION

MOCK_MODEL = "mock-0"

# Unicode block → language. Script level only; a placeholder heuristic.
_SCRIPT_RANGES: tuple[tuple[int, int, LanguageCode], ...] = (
    (0x0B80, 0x0BFF, LanguageCode.TA),
    (0x0900, 0x097F, LanguageCode.HI),
    (0x0C00, 0x0C7F, LanguageCode.TE),
    (0x0C80, 0x0CFF, LanguageCode.KN),
    (0x0D00, 0x0D7F, LanguageCode.ML),
    (0x0980, 0x09FF, LanguageCode.BN),
    (0x0A80, 0x0AFF, LanguageCode.GU),
    (0x0A00, 0x0A7F, LanguageCode.PA),
    (0x0B00, 0x0B7F, LanguageCode.OR),
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")

# Two plausible numbers separated by "/", not part of a date or a longer number.
_BLOOD_PRESSURE = re.compile(r"(?<![\d/.])(\d{2,3})\s*/\s*(\d{2,3})(?![\d/])")

# "<label>: <number> <unit>" on one line. The label is the source's own words.
_LABELLED_MEASUREMENT = re.compile(
    r"(?<![A-Za-z0-9])(?P<label>[A-Za-z][A-Za-z0-9 ()\-]{0,40}?)\s*(?:[:=]|\.{2,}|…+)?\s*(?P<value>\d{1,4}(?:\.\d{1,2})?)\s*"
    r"(?P<unit>mg\s*/\s*dl|g\s*/\s*dl|mmol\s*/\s*l|meq\s*/\s*l|ng\s*/\s*ml|pg\s*/\s*ml|iu\s*/\s*l|u\s*/\s*l|bpm|%)"
    r"(?![A-Za-z])",
    re.IGNORECASE,
)

_UNITS = {
    "mg/dl": "mg/dL",
    "g/dl": "g/dL",
    "mmol/l": "mmol/L",
    "meq/l": "mEq/L",
    "ng/ml": "ng/mL",
    "pg/ml": "pg/mL",
    "iu/l": "IU/L",
    "u/l": "U/L",
    "bpm": "bpm",
    "%": "%",
}


def _elapsed_ms(start: float) -> int:
    return max(1, int((time.perf_counter() - start) * 1000))


class _Match:
    __slots__ = ("start", "end", "value", "category", "quote", "language", "subject", "subject_cue")

    def __init__(self, start: int, end: int, value: str, category: FactCategory, quote: str, language: str):
        self.start, self.end = start, end
        self.value, self.category, self.quote, self.language = value, category, quote, language
        self.subject: FactSubject = FactSubject.SELF
        self.subject_cue: str | None = None


class MockAIProvider(AIProvider):
    name = "mock"
    is_external = False  # nothing leaves this process

    def __init__(self, model: str = MOCK_MODEL):
        self.model = model or MOCK_MODEL

    # ---------- language detection ----------

    async def detect_language(self, text: str) -> LanguageDetection:
        start = time.perf_counter()
        counts: dict[LanguageCode, int] = {}
        latin = 0
        for ch in text or "":
            if not ch.isalpha():
                continue
            cp = ord(ch)
            if ch.isascii():
                latin += 1
                continue
            for lo, hi, code in _SCRIPT_RANGES:
                if lo <= cp <= hi:
                    counts[code] = counts.get(code, 0) + 1
                    break
        total = latin + sum(counts.values())
        if total == 0:
            language, confidence = None, None
        elif counts:
            language = max(counts, key=counts.__getitem__)
            confidence = round(counts[language] / total, 2)
        else:
            language, confidence = LanguageCode.EN, round(latin / total, 2)
        return LanguageDetection(
            provider=self.name,
            model=self.model,
            prompt_version=LANGUAGE_DETECTION.version,
            language=language,
            confidence=confidence,
            usage=AIUsage(latency_ms=_elapsed_ms(start), estimated_cost_usd=0.0),
        )

    # ---------- normalisation ----------

    async def normalize_to_english(self, text: str, source_language: LanguageCode) -> NormalizationResult:
        start = time.perf_counter()
        source = text or ""
        matches = self._find_all(source, source_language)
        covered = {(m.start, m.end) for m in matches}

        if source_language == LanguageCode.EN:
            # Already English: the source is its own normalisation. No invention.
            normalized = source.strip()
            unparsed: list[str] = []
        else:
            normalized = self._compose_english(matches)
            unparsed = [
                sentence.strip()
                for sentence in _SENTENCE_SPLIT.split(source)
                if sentence.strip() and not self._sentence_covered(source, sentence, covered)
            ]
        return NormalizationResult(
            provider=self.name,
            model=self.model,
            prompt_version=NORMALIZATION.version,
            original_text=source,
            source_language=source_language,
            normalized_text_en=normalized,
            unparsed=unparsed,
            confidence=0.6 if normalized else 0.0,
            usage=AIUsage(latency_ms=_elapsed_ms(start), estimated_cost_usd=0.0),
        )

    @staticmethod
    def _sentence_covered(source: str, sentence: str, covered: set[tuple[int, int]]) -> bool:
        offset = source.find(sentence)
        if offset < 0:
            return False
        end = offset + len(sentence)
        return any(offset <= s < end for s, _ in covered)

    def _compose_english(self, matches: list[_Match]) -> str:
        def values(category: FactCategory) -> list[str]:
            seen: list[str] = []
            for m in matches:
                if m.category == category and m.subject == FactSubject.SELF and m.value not in seen:
                    seen.append(m.value)
            return seen

        parts: list[str] = []
        # Anything attributed to a relative is reported as such, never merged
        # into the patient's own description.
        family = []
        for m in matches:
            if m.subject == FactSubject.FAMILY and m.value not in family:
                family.append(m.value)
        symptoms = values(FactCategory.SYMPTOM)
        if symptoms:
            parts.append("Patient reports " + ", ".join(symptoms) + ".")
        durations = values(FactCategory.DURATION)
        if durations:
            parts.append("Reported duration: " + ", ".join(durations) + ".")
        measurements = values(FactCategory.MEASUREMENT)
        if measurements:
            parts.append("Reported measurements: " + ", ".join(measurements) + ".")
        medications = values(FactCategory.MEDICATION)
        if medications:
            parts.append("Medicines mentioned: " + ", ".join(medications) + ".")
        allergies = values(FactCategory.ALLERGY)
        if allergies:
            parts.append("Allergy stated: " + ", ".join(allergies) + ".")
        history = values(FactCategory.MEDICAL_HISTORY)
        if history:
            parts.append("History stated: " + ", ".join(history) + ".")
        if family:
            parts.append("Reported about a family member: " + ", ".join(family) + ".")
        return " ".join(parts)

    # ---------- extraction ----------

    async def extract_medical_information(self, text: str, language: LanguageCode) -> ExtractionResult:
        start = time.perf_counter()
        source = text or ""
        matches = self._find_all(source, language)
        facts = [
            ExtractedFact(
                category=m.category,
                value=m.value,
                original_text=m.quote,
                evidence=Evidence(quote=m.quote, start=m.start, end=m.end),
                subject=m.subject,
                subject_evidence=m.subject_cue,
                confidence=0.75,
            )
            for m in sorted(matches, key=lambda m: m.start)
        ]
        covered = {(m.start, m.end) for m in matches}
        unparsed = [
            sentence.strip()
            for sentence in _SENTENCE_SPLIT.split(source)
            if sentence.strip() and not self._sentence_covered(source, sentence, covered)
        ]
        return ExtractionResult(
            provider=self.name,
            model=self.model,
            prompt_version=EXTRACTION.version,
            facts=facts,
            needs_review=[],
            unparsed=unparsed,
            usage=AIUsage(latency_ms=_elapsed_ms(start), estimated_cost_usd=0.0),
        )

    # ---------- matching ----------


    async def summarize_case(self, bundle_text: str) -> SummaryOrganisation:
        """Deterministic grouping of one authorised bundle.

        The rules live in `mock_summary.organise`, which is a pure function of
        the bundle, so the same shared information always yields the same
        summary — what a reproducible demo needs, and what makes this provider
        measurable by the same evaluation harness as any other.
        """
        import json

        from app.providers.ai.mock_summary import organise

        start = time.perf_counter()
        try:
            payload = json.loads(bundle_text)
        except ValueError as exc:
            from app.providers.ai.errors import AIMalformedOutput

            raise AIMalformedOutput("bundle was not valid JSON", provider=self.name) from exc
        return SummaryOrganisation(
            provider=self.name,
            model=self.model,
            prompt_version=CASE_SUMMARY.version,
            payload=organise(payload),
            usage=AIUsage(latency_ms=_elapsed_ms(start), estimated_cost_usd=0.0),
        )

    @staticmethod
    def _clause_bounds(source: str, start: int, end: int) -> tuple[int, int]:
        """The clause containing [start, end): attribution does not cross clauses."""
        clause_start = 0
        for index in range(start - 1, -1, -1):
            if source[index] in CLAUSE_BOUNDARY_CHARS:
                clause_start = index + 1
                break
        clause_end = len(source)
        for index in range(end, len(source)):
            if source[index] in CLAUSE_BOUNDARY_CHARS:
                clause_end = index
                break
        return clause_start, clause_end

    @classmethod
    def _subject_for(cls, source: str, start: int, end: int) -> tuple[FactSubject, str | None]:
        """Family attribution needs an explicit cue in the same clause.

        "My father has diabetes. I feel fine." attributes diabetes to the father
        and leaves the second clause with the patient.
        """
        clause_start, clause_end = cls._clause_bounds(source, start, end)
        clause = source[clause_start:clause_end]
        lowered = clause.casefold()
        # Cues from every language: patients mix scripts freely.
        for cues in FAMILY_CUES.values():
            for cue in cues:
                position = lowered.find(cue.casefold())
                if position >= 0:
                    return FactSubject.FAMILY, clause[position : position + len(cue)].strip()
        # No cue: the patient's own health record describes the patient.
        return FactSubject.SELF, None

    def _find_all(self, source: str, language: LanguageCode) -> list[_Match]:
        matches: list[_Match] = []
        matches += self._match_concepts(source, SYMPTOMS, FactCategory.SYMPTOM, honour_negation=True)
        matches += self._match_concepts(source, MEDICATIONS, FactCategory.MEDICATION, honour_negation=True)
        matches += self._match_concepts(source, CONDITIONS, FactCategory.MEDICAL_HISTORY, honour_negation=True)
        matches += self._match_durations(source)
        matches += self._match_measurements(source)
        matches += self._match_allergies(source)
        # Allergies win over the symptom/medication reading of the same span.
        allergy_spans = [(m.start, m.end) for m in matches if m.category == FactCategory.ALLERGY]
        deduped: dict[tuple[int, int, FactCategory], _Match] = {}
        for m in matches:
            if m.category != FactCategory.ALLERGY and any(s <= m.start < e for s, e in allergy_spans):
                continue
            deduped.setdefault((m.start, m.end, m.category), m)
        result = list(deduped.values())
        for match in result:
            match.subject, match.subject_cue = self._subject_for(source, match.start, match.end)
        return result

    def _match_concepts(
        self, source: str, concepts: tuple[Concept, ...], category: FactCategory, *, honour_negation: bool
    ) -> list[_Match]:
        found: list[_Match] = []
        lowered = source.casefold()
        for concept in concepts:
            for lang, form in concept.all_forms():
                needle = form.casefold()
                position = lowered.find(needle)
                while position >= 0:
                    end = position + len(needle)
                    if not self._is_word_boundary(source, position, end, lang):
                        position = lowered.find(needle, position + 1)
                        continue
                    if honour_negation and self._is_negated(source, position, end, lang):
                        position = lowered.find(needle, end)
                        continue
                    value = concept.value
                    if category == FactCategory.MEDICATION:
                        value, end = self._with_dose(source, concept.value, position, end)
                    found.append(_Match(position, end, value, category, source[position:end], lang))
                    position = lowered.find(needle, end)
        return found

    @staticmethod
    def _is_word_boundary(source: str, start: int, end: int, lang: str) -> bool:
        # Latin scripts need boundaries so "cold" does not match inside "colder".
        if lang != "en":
            return True
        before = source[start - 1] if start > 0 else " "
        after = source[end] if end < len(source) else " "
        return not (before.isalnum() or after.isalnum())

    @staticmethod
    def _clause(text: str, lang: str) -> str:
        """Text up to the end of the current clause."""
        cut = len(text)
        for index, ch in enumerate(text):
            if ch in CLAUSE_BOUNDARY_CHARS:
                cut = index
                break
        clause = text[:cut]
        lowered = clause.casefold()
        for word in CLAUSE_BOUNDARY_WORDS.get(lang, ()):
            found = lowered.find(word.casefold())
            if found >= 0:
                clause = clause[:found]
                lowered = clause.casefold()
        return clause

    @classmethod
    def _is_negated(cls, source: str, start: int, end: int, lang: str) -> bool:
        # English negates before the term; Tamil and Hindi after it. A cue in a
        # different clause must not negate this term.
        before = cls._clause(source[max(0, start - 24) : start][::-1], lang)[::-1].casefold()
        after = cls._clause(source[end : end + 40], lang)
        for cue in NEGATION_BEFORE.get(lang, ()):  # "no fever"
            if before.rstrip().endswith(cue.strip()):
                return True
        for cue in NEGATION_AFTER.get(lang, ()):  # "காய்ச்சல் இல்லை"
            if cue in after:
                return True
        return False

    @staticmethod
    def _with_dose(source: str, value: str, start: int, end: int) -> tuple[str, int]:
        dose = re.compile(r"\s*(\d+(?:\.\d+)?)\s*(mg|ml|mcg|g|units?)\b", re.IGNORECASE).match(source, end)
        if not dose:
            return value, end
        return f"{value} {dose.group(1)} {dose.group(2).lower()}", dose.end()

    def _match_durations(self, source: str) -> list[_Match]:
        found: list[_Match] = []
        for lang, units in TIME_UNITS.items():
            words = NUMBER_WORDS.get(lang, {})
            number = r"(\d{1,3}|" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")"
            unit = "(" + "|".join(re.escape(u) for u in sorted(units, key=len, reverse=True)) + ")"
            pattern = re.compile(number + r"[\s\-]{0,3}" + unit, re.IGNORECASE)
            for m in pattern.finditer(source):
                raw_number, raw_unit = m.group(1), m.group(2)
                # "in 4 weeks", "every 8 hours": an interval, not how long something lasted.
                before = source[max(0, m.start() - 16) : m.start()].casefold()
                if re.search(r"\b(?:" + "|".join(INTERVAL_WORDS) + r")\s*$", before):
                    continue
                count = int(raw_number) if raw_number.isdigit() else words.get(raw_number.casefold(), 0)
                if count <= 0:
                    continue
                canonical_unit = units.get(raw_unit) or units.get(raw_unit.casefold())
                if canonical_unit is None:
                    continue
                value = f"{count} {canonical_unit}" + ("s" if count != 1 else "")
                found.append(_Match(m.start(), m.end(), value, FactCategory.DURATION, m.group(0), lang))
        return found

    @staticmethod
    def _lines(source: str):
        offset = 0
        for line in source.split("\n"):
            yield offset, line
            offset += len(line) + 1

    @staticmethod
    def _clean_label(raw: str) -> str | None:
        # The few words right before the value, without connecting words: "I had sugar of" -> "sugar".
        words = [w for w in re.split(r"\s+", raw.strip(" :-=()")) if w][-4:]
        while words and words[0].casefold() in LABEL_FILLER:
            words.pop(0)
        while words and words[-1].casefold() in LABEL_FILLER:
            words.pop()
        if not words:
            return None
        label = " ".join(words).casefold()
        return "blood sugar" if label in {"sugar", "glucose", "blood glucose", "blood sugar"} else label

    def _match_measurements(self, source: str) -> list[_Match]:
        """Numbers the source reports, labelled only by the words the source uses.

        A value is never given a label the text does not contain: "Total
        cholesterol: 212 mg/dL" stays cholesterol, and a bare "212 mg/dL" is not
        a fact at all.
        """
        found: list[_Match] = []
        for line_start, line in self._lines(source):
            # Blood pressure, with a plausibility check so dates (12/05/2026) are not read as one.
            for m in _BLOOD_PRESSURE.finditer(line):
                systolic, diastolic = int(m.group(1)), int(m.group(2))
                if not (70 <= systolic <= 260 and 40 <= diastolic <= 160 and systolic > diastolic):
                    continue
                found.append(
                    _Match(line_start + m.start(), line_start + m.end(), f"blood pressure {systolic}/{diastolic}",
                           FactCategory.MEASUREMENT, m.group(0), "en")
                )
            labelled_spans: list[tuple[int, int]] = []
            for m in _LABELLED_MEASUREMENT.finditer(line):
                label = self._clean_label(m.group("label"))
                if label is None:
                    continue
                unit = _UNITS[re.sub(r"\s+", "", m.group("unit")).casefold()]
                labelled_spans.append((m.start(), m.end()))
                found.append(
                    _Match(line_start + m.start(), line_start + m.end(), f"{label} {m.group('value')} {unit}",
                           FactCategory.MEASUREMENT, m.group(0), "en")
                )
            # Sugar in other scripts ("சர்க்கரை 210 mg/dL"), only with a sugar word right before it.
            for m in re.finditer(r"(\d{2,3})\s*mg\s*/?\s*d[lL]", line):
                if any(s <= m.start() < e for s, e in labelled_spans):
                    continue
                before = line[max(0, m.start() - 25) : m.start()].casefold()
                if any(word in before for word in SUGAR_WORDS):
                    found.append(
                        _Match(line_start + m.start(), line_start + m.end(), f"blood sugar {m.group(1)} mg/dL",
                               FactCategory.MEASUREMENT, m.group(0), "en")
                    )
        for m in re.finditer(r"\b(\d{2,3}(?:\.\d)?)\s*(?:°\s*)?(?:f\b|c\b|fahrenheit|celsius|டிகிரி|डिग्री)", source, re.IGNORECASE):
            found.append(
                _Match(m.start(), m.end(), f"temperature {m.group(1)}", FactCategory.MEASUREMENT, m.group(0), "en")
            )
        for m in re.finditer(r"\b(\d{2,3})\s*(?:kg|கிலோ|किलो)\b", source, re.IGNORECASE):
            found.append(
                _Match(m.start(), m.end(), f"weight {m.group(1)} kg", FactCategory.MEASUREMENT, m.group(0), "en")
            )
        return found

    def _match_allergies(self, source: str) -> list[_Match]:
        found: list[_Match] = []
        lowered = source.casefold()
        # Explicit "no allergies" — the only case where absence becomes a fact.
        for _lang, phrases in NO_ALLERGY_PATTERNS.items():
            for phrase in phrases:
                position = lowered.find(phrase.casefold())
                if position >= 0:
                    end = position + len(phrase)
                    found.append(
                        _Match(position, end, "no known allergies (explicitly stated)",
                               FactCategory.ALLERGY, source[position:end], _lang)
                    )
        if found:
            return found
        for lang, patterns in ALLERGY_PATTERNS.items():
            for raw in patterns:
                for m in re.finditer(raw, source, re.IGNORECASE):
                    allergen = unicodedata.normalize("NFC", m.group(1)).strip(" .,-")
                    if not allergen or allergen.casefold() in {"any", "no", "not", "none", "nil", "nkda", "unknown"}:
                        continue
                    found.append(
                        _Match(m.start(), m.end(), f"allergy: {allergen}", FactCategory.ALLERGY, m.group(0), lang)
                    )
        return found
