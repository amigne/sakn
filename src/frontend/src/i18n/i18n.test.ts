import { beforeEach, describe, expect, it, vi } from "vitest";

// i18n.ts runs i18n.init() at import time which reads document.cookie.
// Dynamic imports ensure mocks are in place before module init.

describe("setLanguage cookie Secure flag", () => {
  beforeEach(() => {
    vi.resetModules();
    Object.defineProperty(document, "cookie", {
      writable: true,
      value: "",
    });
  });

  it("includes Secure flag when protocol is https:", async () => {
    vi.stubGlobal("window", {
      ...window,
      location: { protocol: "https:" },
    });
    const { setLanguage } = await import("./i18n");
    setLanguage("fr");
    expect(document.cookie).toContain("; Secure");
  });

  it("omits Secure flag when protocol is http:", async () => {
    vi.stubGlobal("window", {
      ...window,
      location: { protocol: "http:" },
    });
    const { setLanguage } = await import("./i18n");
    setLanguage("fr");
    expect(document.cookie).not.toContain("; Secure");
  });

  it("includes all mandatory cookie attributes", async () => {
    vi.stubGlobal("window", {
      ...window,
      location: { protocol: "https:" },
    });
    const { setLanguage } = await import("./i18n");
    setLanguage("en");
    const cookie = document.cookie;
    expect(cookie).toMatch(/^lang=en;/);
    expect(cookie).toContain("path=/");
    expect(cookie).toContain("max-age=31536000");
    expect(cookie).toContain("SameSite=Lax");
  });

  it("rejects unsupported languages", async () => {
    vi.stubGlobal("window", {
      ...window,
      location: { protocol: "https:" },
    });
    const { setLanguage } = await import("./i18n");
    const prevCookie = document.cookie;
    setLanguage("de");
    // Cookie should be unchanged (document.cookie starts empty)
    expect(document.cookie).toBe(prevCookie);
  });
});
