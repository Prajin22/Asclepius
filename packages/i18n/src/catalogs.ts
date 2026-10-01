import commonEn from "../messages/common.en.json";
import commonHi from "../messages/common.hi.json";
import commonTa from "../messages/common.ta.json";
import doctorEn from "../messages/doctor.en.json";
import patientEn from "../messages/patient.en.json";
import patientHi from "../messages/patient.hi.json";
import patientTa from "../messages/patient.ta.json";
import saktiEn from "../messages/sakti.en.json";
import saktiHi from "../messages/sakti.hi.json";
import saktiTa from "../messages/sakti.ta.json";
import { mergeMessages, type Catalogs } from "./index";

/** Patient app: fully translated into every UI language. */
export const patientCatalogs: Catalogs = {
  en: mergeMessages(commonEn, patientEn),
  hi: mergeMessages(commonHi, patientHi),
  ta: mergeMessages(commonTa, patientTa),
};

/** Doctor app: English UI in Phase 1; keys fall back to English. */
export const doctorCatalogs: Catalogs = {
  en: mergeMessages(commonEn, doctorEn),
};

/**
 * IP-SAKTI Sahayak (PRODUCT=ip_sakti). Self-contained on purpose: the common
 * catalogue carries CareBridge's medical vocabulary and disclaimers, and none of
 * it may appear in IP-SAKTI, even as a fallback (D-080). Hindi and Tamil are
 * interface translations drafted by the team, awaiting native-speaker review —
 * never translations of law.
 */
export const saktiCatalogs: Catalogs = {
  en: saktiEn,
  hi: saktiHi,
  ta: saktiTa,
};

export const rawCatalogs = {
  commonEn,
  commonHi,
  commonTa,
  patientEn,
  patientHi,
  patientTa,
  doctorEn,
  saktiEn,
  saktiHi,
  saktiTa,
};
