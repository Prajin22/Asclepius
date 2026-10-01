import { ROLES_BY_PRODUCT, type SaktiRole } from "@carebridge/shared-types";
import { describe, expect, it } from "vitest";
import { SAKTI_NAV } from "@/components/sakti/nav";
import { PRODUCT, PRODUCT_CONFIGS, acceptsRole, parseProduct } from "./product";
import { HOME_FOR_ROLE } from "./routes";

describe("the product setting", () => {
  it("is CareBridge when unset, exactly as before", () => {
    expect(parseProduct(undefined)).toBe("carebridge");
    expect(parseProduct("")).toBe("carebridge");
    expect(PRODUCT).toBe("carebridge"); // the test environment sets nothing
  });

  it("accepts the two products", () => {
    expect(parseProduct("carebridge")).toBe("carebridge");
    expect(parseProduct("ip_sakti")).toBe("ip_sakti");
  });

  it.each(["ipsakti", "IP-SAKTI", "health", "ip_sakti "])("refuses %j rather than guessing", (value) => {
    expect(() => parseProduct(value)).toThrow(/not a product/);
  });
});

describe("CareBridge is unchanged", () => {
  const cb = PRODUCT_CONFIGS.carebridge;

  it("keeps its name, colour and storage keys, so existing sessions survive", () => {
    expect(cb.name).toBe("Asclepius");
    expect(cb.themeColor).toBe("#d83a2e");
    expect(cb.sessionKey).toBe("asclepius.session");
    expect(cb.localeKey).toBe("carebridge.patient.locale");
  });

  it("keeps its roles and where each lands", () => {
    expect(cb.roles).toEqual(["patient", "doctor", "admin"]);
    expect(HOME_FOR_ROLE.patient).toBe("/home");
    expect(HOME_FOR_ROLE.doctor).toBe("/clinician");
    expect(HOME_FOR_ROLE.admin).toBe("/admin");
  });
});

describe("IP-SAKTI Sahayak", () => {
  const sakti = PRODUCT_CONFIGS.ip_sakti;

  it("has its own identity and its own storage", () => {
    expect(sakti.name).toBe("IP-SAKTI Sahayak");
    expect(sakti.description).toMatch(/not legal advice/);
    expect(sakti.sessionKey).not.toBe(PRODUCT_CONFIGS.carebridge.sessionKey);
    expect(sakti.localeKey).not.toBe(PRODUCT_CONFIGS.carebridge.localeKey);
    expect(sakti.themeColor).not.toBe(PRODUCT_CONFIGS.carebridge.themeColor);
  });

  it("has the role vocabulary user, facilitator, curator, admin", () => {
    expect(sakti.roles).toEqual(["user", "facilitator", "curator", "admin"]);
    expect(ROLES_BY_PRODUCT.ip_sakti).toEqual(sakti.roles);
  });

  it.each(ROLES_BY_PRODUCT.ip_sakti)("lands %s on the first destination of its own area", (role) => {
    expect(HOME_FOR_ROLE[role]).toBe(SAKTI_NAV[role as SaktiRole][0].href);
  });

  it("accepts its roles and only its roles", () => {
    for (const role of ["user", "facilitator", "curator", "admin"] as const) expect(acceptsRole(role, "ip_sakti")).toBe(true);
    for (const role of ["patient", "doctor"] as const) expect(acceptsRole(role, "ip_sakti")).toBe(false);
    for (const role of ["user", "facilitator", "curator"] as const) expect(acceptsRole(role, "carebridge")).toBe(false);
  });

  it("shares only the admin role with CareBridge", () => {
    const shared = ROLES_BY_PRODUCT.ip_sakti.filter((r) => (ROLES_BY_PRODUCT.carebridge as readonly string[]).includes(r));
    expect(shared).toEqual(["admin"]);
  });
});
