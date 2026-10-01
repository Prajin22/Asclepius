"""What the AI may do, per product (D-079).

Each product has one policy. A policy names the provider capabilities that
product may call at all, the rules its outputs must honour, and the field names
no answer schema in it may contain. The written policy each one implements is
the document it points at; this module is the part code can check.

CareBridge's policy permits every capability it uses today, so selecting it
changes nothing. IP-SAKTI's permits **none** yet: no IP-SAKTI capability exists
in Phase 1, and the medical ones must never run in it. A capability is added to
it in the same change that builds and tests that capability.
"""

from dataclasses import dataclass

#: Every capability on `AIProvider`. A test fails if the provider interface
#: gains a method this list does not name, so nothing can be added to the
#: provider without each policy saying whether it may be used.
CAPABILITIES: tuple[str, ...] = (
    "detect_language",
    "normalize_to_english",
    "extract_medical_information",
    "transcribe_document_image",
    "summarize_case",
)

#: The prompt each capability runs, for reporting what a deployment can do.
PROMPT_FOR_CAPABILITY: dict[str, str] = {
    "detect_language": "language_detection",
    "normalize_to_english": "normalization",
    "extract_medical_information": "extraction",
    "transcribe_document_image": "document_transcription",
    "summarize_case": "case_summary",
}


@dataclass(frozen=True)
class AIPolicy:
    id: str
    #: The written policy, relative to the repository root.
    document: str
    #: Provider capabilities this product may call. Anything else is refused.
    capabilities: frozenset[str]
    #: Rules every output must honour, as stable codes.
    rules: tuple[str, ...]
    #: Field names no answer or summary schema in this product may contain.
    forbidden_answer_fields: frozenset[str]

    def permits(self, capability: str) -> bool:
        return capability in self.capabilities

    @property
    def permits_everything(self) -> bool:
        return self.capabilities >= frozenset(CAPABILITIES)


CAREBRIDGE_POLICY = AIPolicy(
    id="carebridge_health_v1",
    document="docs/AI_POLICY.md",
    capabilities=frozenset(CAPABILITIES),
    rules=(
        "no_diagnosis",
        "no_prescribing",
        "no_choosing_between_doctors",
        "original_text_never_overwritten",
        "patient_confirms_before_record",
        "evidence_for_every_extracted_fact",
    ),
    forbidden_answer_fields=frozenset(
        {"diagnosis", "differential", "triage", "risk_score", "severity", "treatment_recommendation"}
    ),
)

IP_SAKTI_POLICY = AIPolicy(
    id="ip_sakti_legal_information_v1",
    document="docs/IP_SAKTI_AI_POLICY.md",
    # None yet. The medical capabilities must never run here, and the
    # IP-SAKTI ones (answer composition, later) do not exist until they are
    # built, tested and added here in the same change.
    capabilities=frozenset(),
    rules=(
        "no_legal_advice",
        "no_generated_statutory_text",
        "no_fabricated_citations",
        "no_invented_section_numbers",
        "no_unsupported_claims_of_current_law",
        "no_impersonating_lawyer_or_authority",
        "source_grounding_required",
        "abstain_or_escalate_when_uncertain",
        "original_question_never_overwritten",
    ),
    forbidden_answer_fields=frozenset(
        {"recommendation", "recommendations", "advice", "next_steps", "legal_opinion", "action_plan"}
    ),
)
