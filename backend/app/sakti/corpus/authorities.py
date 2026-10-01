"""The official sources a corpus document may come from (D-083).

The list is the build brief's (India Code, IP India, NBA, WIPO Lex) plus the
two the Phase 2 brief adds (e-Gazette, FSSAI). Nothing else can be chosen: a
blog, a law firm's copy, an encyclopaedia or a search snippet has no entry, so
it cannot enter the corpus.

Each authority belongs to one lane. WIPO Lex also republishes national laws,
but a copy of an Indian law from it is not the official Indian source, so it is
international only.

Reuse terms: none has been checked. Every entry is `unknown`, and nothing in the
application may say that redistribution is permitted until someone verifies the
terms and records it.
"""

from dataclasses import dataclass

from app.models.enums import CorpusLane, SourceAuthority, TermsStatus


@dataclass(frozen=True)
class Authority:
    code: SourceAuthority
    name: str
    lane: CorpusLane
    terms_status: TermsStatus = TermsStatus.UNKNOWN


AUTHORITIES: dict[SourceAuthority, Authority] = {
    a.code: a
    for a in (
        Authority(SourceAuthority.INDIA_CODE, "India Code", CorpusLane.INDIA),
        Authority(SourceAuthority.E_GAZETTE, "e-Gazette", CorpusLane.INDIA),
        Authority(SourceAuthority.IP_INDIA, "IP India", CorpusLane.INDIA),
        Authority(SourceAuthority.NBA, "National Biodiversity Authority", CorpusLane.INDIA),
        Authority(SourceAuthority.FSSAI, "FSSAI", CorpusLane.INDIA),
        Authority(SourceAuthority.WIPO_LEX, "WIPO Lex", CorpusLane.INTERNATIONAL),
    )
}

assert set(AUTHORITIES) == set(SourceAuthority), "every SourceAuthority needs an entry"


def authority(code: SourceAuthority) -> Authority:
    return AUTHORITIES[code]
