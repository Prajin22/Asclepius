import commonEn from "../messages/common.en.json";
import commonHi from "../messages/common.hi.json";
import commonTa from "../messages/common.ta.json";
import doctorEn from "../messages/doctor.en.json";
import patientEn from "../messages/patient.en.json";
import patientHi from "../messages/patient.hi.json";
import patientTa from "../messages/patient.ta.json";
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

export const rawCatalogs = { commonEn, commonHi, commonTa, patientEn, patientHi, patientTa, doctorEn };
