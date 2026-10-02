/**
 * The shape a source-grounded answer will have when Phase 4 builds the answer
 * service. Nothing in Phase 3.5 produces one: these types exist so the screens
 * that will show answers can be designed, tested and reviewed before any
 * answer exists. Every legal word in an answer is a quotation of approved
 * corpus text; the product's own words are only ever statements about what
 * the quotations say, and each statement carries its citations.
 */
import type { CorpusLane, ISODate, ISODateTime, ProvisionStatus, SourceAuthority, UUID } from "@carebridge/shared-types";

/** India and International are answered separately, never merged. */
export type Jurisdiction = CorpusLane;

/**
 * How far the cited text supports a lane's answer. Words, never a percentage:
 * "supported" — every point has a citation; "partial" — some of the question
 * is not covered by the sources; "insufficient" — the service abstained.
 */
export type Confidence = "supported" | "partial" | "insufficient";

/** One approved provision version, identified exactly as the corpus stores it. */
export interface SourceRef {
  provisionVersionId: UUID;
  lane: Jurisdiction;
  authority: SourceAuthority;
  instrumentTitle: string;
  /** The label as the source prints it, e.g. a section or article number. Copied, never composed. */
  locator: string;
  versionNumber: number;
  validFrom: ISODate | null;
  validTo: ISODate | null;
  /** The latest status a curator recorded from a cited source, if any. */
  status: ProvisionStatus | null;
  sourceTitle: string;
  retrievedOn: ISODate;
  approvedAt: ISODateTime;
  /** SHA-256 of the quoted text as approved. */
  textSha256: string;
}

/** An exact quotation of approved corpus text, with where it came from. */
export interface QuotedProvision {
  /** Verbatim. Never paraphrased, never machine-translated. */
  text: string;
  /** Character range within the approved version, so the quote can be checked. */
  charStart: number;
  charEnd: number;
  /** Part of the text was read by OCR and was checked by a curator against the original. */
  ocrDerived: boolean;
  source: SourceRef;
}

export interface AnswerPoint {
  id: string;
  /** "requirement": the quoted text imposes something; "information": it describes something. */
  kind: "requirement" | "information";
  /** A statement about what the citations say. Not itself legal text. */
  statement: string;
  /** Never empty: a point without a citation is not shown. */
  citations: QuotedProvision[];
}

export interface LaneAnswer {
  lane: Jurisdiction;
  asOf: ISODate;
  confidence: Confidence;
  points: AnswerPoint[];
  /** Parts of the question the approved sources do not cover. */
  notCovered: string[];
}

export interface CitedAnswer {
  question: string;
  asOf: ISODate;
  lanes: Partial<Record<Jurisdiction, LaneAnswer>>;
  /** Present when a human facilitator should look at the question. */
  escalation: { reason: string } | null;
  /** The corpus snapshot the answer was built from. */
  corpusVersion: string;
}
