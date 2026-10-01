# IP-SAKTI Sahayak — AI Policy

**Applies when `PRODUCT=ip_sakti`.** CareBridge's policy is
[docs/AI_POLICY.md](AI_POLICY.md) and is unchanged. Which policy is in force is
decided by the product, in code (`backend/app/core/ai_policy.py`), not by
configuration a deployment could get wrong (D-079).

Policy id: `ip_sakti_legal_information_v1`.

## Core statement

IP-SAKTI Sahayak gives **information about intellectual property and
regulation for Ayurvedic products, grounded in cited official sources**. It is
not a lawyer, not a government authority and not a substitute for qualified
professional advice. When the sources do not support an answer, it says so and
offers a human facilitator instead of guessing.

## What the AI may do — today

**Nothing.** In Phase 1 the policy permits no AI capability at all: the
provider factory hands IP-SAKTI a provider that refuses every call before any
text leaves the server (`PolicyRestrictedProvider`). The healthcare
capabilities — medical extraction, case summaries — can never run in
IP-SAKTI. A capability is added to this policy in the same change that builds
and tests it, never ahead of it.

Phase 2's source corpus adds none. Reading an official source copies its PDF
text layer exactly, or uses the offline OCR engine and marks the result as
machine transcription for a curator to check; no page is ever sent to a model,
and no model writes, repairs or summarises corpus text (D-086). Differences
between versions are computed by `difflib`, not judged by a model.

## Rules every output must honour

Each rule has a stable code. The code list lives in
`backend/app/core/ai_policy.py`; a test fails if a code exists there but not
here.

| Code | Rule |
|---|---|
| `no_legal_advice` | Never tells anyone what they should do. Describes what cited sources say; does not recommend, advise or plan. |
| `no_generated_statutory_text` | Never writes, paraphrases-as-quotation or completes the text of a law. Statutory text comes only from approved official sources. |
| `no_fabricated_citations` | Never cites a source it was not given, and never presents a citation that has not been verified against approved text. |
| `no_invented_section_numbers` | Never produces a section, rule, article or clause number that is not present in an approved source. |
| `no_unsupported_claims_of_current_law` | Never states that a provision is in force, amended, stayed or repealed unless an approved, dated source says so. |
| `no_impersonating_lawyer_or_authority` | Never presents itself as a lawyer, an official, a government body or a source of legal authority. |
| `source_grounding_required` | Every substantive statement must rest on an exact quotation from an approved source. Unsupported statements are removed, not repaired. |
| `abstain_or_escalate_when_uncertain` | When sources are missing, conflicting or insufficient, the answer is an abstention, with the option to ask a human facilitator. |
| `original_question_never_overwritten` | The question is kept exactly as asked. Any normalised or translated form is a labelled machine artifact beside it. |

## What an answer may never contain

No answer, point or summary schema in IP-SAKTI may have a field for a
recommendation, advice, next steps, a legal opinion or an action plan. The
names are listed in `IP_SAKTI_POLICY.forbidden_answer_fields`; the schema tests
that enforce them arrive with the answer schemas themselves.

## Text the system shows

* **Interface text** is translated (English, Hindi, Tamil). Hindi and Tamil
  interface translations are drafts awaiting native-speaker review. They are
  interface translations, never translations of law.
* **Quotations of law**, when they exist, are shown in the language of the
  official text. A machine translation is never presented as the provision.
* **Machine output** is labelled as machine output. **Human facilitator
  replies** are attributed to the person who wrote them.

## Offline demonstration

`DEMO_MODE=true` pins the offline provider in IP-SAKTI exactly as in CareBridge.
A demonstration may use synthetic users, products and questions. It may never
use invented law: any legal text in a demonstration is approved official text.

## What this policy does not yet enforce

These are written down now so later phases are held to them, not because they
are implemented:

* citation verification against approved provision text;
* India and International sources kept in separate retrieval lanes, with every
  citation in its answer's lane;
* time-aware provisions;
* confidence scoring and abstention;
* facilitator escalation.

See [docs/IP_SAKTI_MIGRATION_PLAN.md](IP_SAKTI_MIGRATION_PLAN.md) §10 for where
each will be enforced.
