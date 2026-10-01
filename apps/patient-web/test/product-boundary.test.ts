/**
 * Every route in the app belongs to a product, and says so (D-077).
 *
 * Reads the route tree itself. A page added later without a product boundary
 * would appear in both products at once — this is the test that notices.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { SAKTI_NAV } from "@/components/sakti/nav";

const APP = join(dirname(fileURLToPath(import.meta.url)), "..", "app");

function pages(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return pages(p);
    return name === "page.tsx" ? [relative(APP, p).split(sep).join("/")] : [];
  });
}

const read = (path: string) => readFileSync(join(APP, path), "utf8");
const gated = (layout: string, product: string) => read(layout).includes(`<ProductOnly product="${product}">`);

/** The only paths both products serve: each picks one screen per product. */
const SHARED = ["page.tsx", "login/page.tsx", "admin/page.tsx"];

function owner(page: string): "carebridge" | "ip_sakti" | "shared" | undefined {
  if (SHARED.includes(page)) return "shared";
  if (page.startsWith("(ip-sakti)/")) return gated("(ip-sakti)/layout.tsx", "ip_sakti") ? "ip_sakti" : undefined;
  if (page.startsWith("(app)/")) return gated("(app)/layout.tsx", "carebridge") ? "carebridge" : undefined;
  if (page.startsWith("clinician/")) return gated("clinician/layout.tsx", "carebridge") ? "carebridge" : undefined;
  return undefined;
}

/** The URL a page file serves: route groups do not appear in it. */
const urlOf = (page: string) =>
  "/" + page.replace(/\/?page\.tsx$/, "").split("/").filter((s) => s && !/^\(.*\)$/.test(s)).join("/");

describe("the route tree", () => {
  const all = pages(APP);

  it("finds the pages it is checking", () => {
    expect(all.length).toBeGreaterThan(25);
  });

  it.each(all)("%s belongs to a product", (page) => {
    expect(owner(page), `${page} has no product boundary: put it under a ProductOnly area or use forProduct`).toBeDefined();
  });

  it.each(SHARED)("shared path %s picks one screen per product", (page) => {
    expect(read(page)).toMatch(/export default forProduct\(\{ carebridge: \w+, ip_sakti: \w+ \}\)/);
  });

  it("the shared admin layout picks one shell per product", () => {
    expect(read("admin/layout.tsx")).toMatch(/export default forProduct\(\{ carebridge: \w+, ip_sakti: \w+ \}\)/);
  });

  it("every healthcare area is CareBridge-only", () => {
    for (const page of all.filter((p) => p.startsWith("(app)/") || p.startsWith("clinician/"))) {
      expect(owner(page), page).toBe("carebridge");
    }
  });

  it("every IP-SAKTI navigation destination is a real IP-SAKTI route", () => {
    const sakti = new Map(all.filter((p) => owner(p) === "ip_sakti" || p === "admin/page.tsx").map((p) => [urlOf(p), p]));
    for (const item of Object.values(SAKTI_NAV).flat()) {
      expect(sakti.has(item.href), `${item.href} has no page`).toBe(true);
    }
  });

  it("no IP-SAKTI route reuses a healthcare URL", () => {
    const healthcare = new Set(all.filter((p) => owner(p) === "carebridge").map(urlOf));
    for (const page of all.filter((p) => owner(p) === "ip_sakti")) {
      expect(healthcare.has(urlOf(page)), urlOf(page)).toBe(false);
    }
  });

  it("no legal-content route exists yet", () => {
    const urls = all.map(urlOf).join(" ");
    for (const word of ["provision", "citation", "answers", "retrieval", "/corpus"]) {
      expect(urls).not.toContain(word);
    }
    expect(existsSync(join(APP, "api"))).toBe(false);
  });
});
