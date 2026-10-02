import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { doctorCatalogs, patientCatalogs, rawCatalogs, saktiCatalogs } from "../src/catalogs";
import { errorMessage, flattenKeys, interpolate, lookup, translate, type Messages } from "../src/index";

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("catalogue parity", () => {
  const en = flattenKeys(patientCatalogs.en).sort();

  it.each(["hi", "ta"])("patient %s has exactly the English keys", (locale) => {
    expect(flattenKeys(patientCatalogs[locale]).sort()).toEqual(en);
  });

  it.each(["hi", "ta"])("patient %s keeps every {placeholder}", (locale) => {
    for (const key of en) {
      const source = lookup(patientCatalogs.en, key)!;
      const translated = lookup(patientCatalogs[locale], key)!;
      expect(placeholders(translated), `${locale}:${key}`).toEqual(placeholders(source));
    }
  });

  it("no empty strings in any catalogue", () => {
    for (const [name, catalog] of Object.entries(rawCatalogs)) {
      for (const key of flattenKeys(catalog as Messages)) {
        expect(lookup(catalog as Messages, key)?.trim(), `${name}:${key}`).toBeTruthy();
      }
    }
  });

  // An app catalogue may *extend* a shared namespace (e.g. `ai.*`), but any
  // shared string it redefines must be a deliberate, listed override —
  // otherwise an app silently changes a string other components rely on.
  const ALLOWED_OVERRIDES = new Set(["ai.unavailable", "ai.provenance"]);

  it.each([
    ["patient", rawCatalogs.patientEn],
    ["doctor", rawCatalogs.doctorEn],
  ])("%s catalogue only overrides shared keys deliberately", (_name, catalog) => {
    const common = new Set(flattenKeys(rawCatalogs.commonEn));
    const clashes = flattenKeys(catalog as Messages).filter(
      (key) => common.has(key) && !ALLOWED_OVERRIDES.has(key),
    );
    expect(clashes).toEqual([]);
  });

  it("doctor catalogue contains common keys", () => {
    expect(lookup(doctorCatalogs.en, "status.active")).toBe("Active");
  });
});

/** Generic interface keys IP-SAKTI defines for itself, under the same names the
 * shared components read (state.loading, actions.retry…). Its own copies, not
 * the shared catalogue's. */
const saktiKeysThatShareANameWithCommon = new Set(flattenKeys(saktiCatalogs.en));

describe("IP-SAKTI catalogue", () => {
  const en = flattenKeys(saktiCatalogs.en).sort();

  it.each(["hi", "ta"])("%s has exactly the English keys", (locale) => {
    expect(flattenKeys(saktiCatalogs[locale]).sort()).toEqual(en);
  });

  it.each(["hi", "ta"])("%s keeps every {placeholder}", (locale) => {
    for (const key of en) {
      const source = lookup(saktiCatalogs.en, key)!;
      expect(placeholders(lookup(saktiCatalogs[locale], key)!), `${locale}:${key}`).toEqual(placeholders(source));
    }
  });

  // The product is shown as Asclepius. IP-SAKTI and Sahayak (and their Hindi and
  // Tamil renderings) are internal or former names and never reach the screen.
  it.each(["en", "hi", "ta"])("%s never displays the internal or former product name", (locale) => {
    for (const key of flattenKeys(saktiCatalogs[locale])) {
      expect(lookup(saktiCatalogs[locale], key), `${locale}:${key}`).not.toMatch(/IP-?SAKTI|Sahayak|सहायक|சகாயக்/i);
    }
  });

  it.each(["en", "hi", "ta"])("%s names the product and its domain", (locale) => {
    expect(lookup(saktiCatalogs[locale], "app.name")).toBe("Asclepius");
    expect(lookup(saktiCatalogs[locale], "app.domain")).toBeTruthy();
    expect(lookup(saktiCatalogs[locale], "disclaimer.short")).toBeTruthy();
  });

  // The common catalogue carries CareBridge's medical text. IP-SAKTI must not
  // reach it, even as a fallback for a missing key.
  it("does not include the shared catalogue", () => {
    const common = flattenKeys(rawCatalogs.commonEn).filter((k) => !saktiKeysThatShareANameWithCommon.has(k));
    for (const key of common) expect(lookup(saktiCatalogs.en, key), key).toBeUndefined();
    expect(lookup(saktiCatalogs.en, "safety.notDiagnosis")).toBeUndefined();
    expect(lookup(saktiCatalogs.en, "safety.emergency")).toBeUndefined();
  });

  const MEDICAL = {
    en: /patient|doctor|symptom|diagnos|prescri|medicat|medicine|allerg|clinic|hospital|health|consultation|treatment|disease|emergency/i,
    hi: /मरीज़|मरीज|डॉक्टर|रोग|निदान|दवा|इलाज|अस्पताल|स्वास्थ्य|लक्षण/,
    ta: /நோயாளி|மருத்துவர்|நோய்|மருந்து|சிகிச்சை|மருத்துவமனை|அறிகுறி|உடல்நல/,
  } as const;

  it.each(["en", "hi", "ta"] as const)("%s carries no medical vocabulary", (locale) => {
    for (const key of flattenKeys(saktiCatalogs[locale])) {
      expect(lookup(saktiCatalogs[locale], key), `${locale}:${key}`).not.toMatch(MEDICAL[locale]);
    }
  });

  it("never claims to give legal advice or official status", () => {
    for (const key of flattenKeys(saktiCatalogs.en)) {
      const text = lookup(saktiCatalogs.en, key)!;
      expect(text, key).not.toMatch(/(we|it) (will )?advise|legal advice is|official (service|app) of|government[- ]approved|certified by/i);
    }
    expect(lookup(saktiCatalogs.en, "disclaimer.short")).toMatch(/not legal advice/);
    expect(lookup(saktiCatalogs.en, "disclaimer.prototype")).toMatch(/Not an official government service/);
  });
});

describe("translate", () => {
  const catalogs = { en: { a: { b: "Hello {name}" }, only: "English only" }, ta: { a: { b: "வணக்கம் {name}" } } };

  it("interpolates", () => {
    expect(translate(catalogs, "ta", "en", "a.b", { name: "Arun" })).toBe("வணக்கம் Arun");
  });
  it("falls back to the fallback locale, then to the key", () => {
    expect(translate(catalogs, "ta", "en", "only")).toBe("English only");
    expect(translate(catalogs, "ta", "en", "missing.key")).toBe("missing.key");
  });
  it("leaves unknown placeholders intact", () => {
    expect(interpolate("{a} {b}", { a: 1 })).toBe("1 {b}");
  });
  it("maps error codes to messages", () => {
    const t = (k: string) => translate(patientCatalogs, "en", "en", k);
    expect(errorMessage(t, { code: "file_too_large" })).toMatch(/too large/);
    expect(errorMessage(t, { code: "unknown_code" })).toBe(lookup(patientCatalogs.en, "errors.generic"));
    expect(errorMessage(t, new Error("x"))).toBe(lookup(patientCatalogs.en, "errors.generic"));
  });
});

describe("no hard-coded language conditionals in app code", () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
  const offenders: string[] = [];
  const pattern = /(===?|!==?)\s*["'](en|hi|ta|te|kn|ml|mr|bn|gu|pa|or|as)["']|["'](en|hi|ta|te|kn|ml|mr|bn|gu|pa|or|as)["']\s*(===?|!==?)/;

  function walk(dir: string) {
    for (const name of readdirSync(dir)) {
      if (["node_modules", ".next", "test", "coverage"].includes(name)) continue;
      const p = join(dir, name);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(tsx?|jsx?)$/.test(name) && !/\.test\./.test(name)) {
        readFileSync(p, "utf8")
          .split("\n")
          .forEach((line, i) => {
            if (pattern.test(line)) offenders.push(`${p}:${i + 1}: ${line.trim()}`);
          });
      }
    }
  }

  it("apps and ui never branch on a specific language code", () => {
    for (const dir of ["apps", join("packages", "ui", "src")]) walk(join(root, dir));
    expect(offenders).toEqual([]);
  });
});
