import { test, expect } from "@playwright/test";

test.describe("Admin Pages", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!!process.env.CI, "Pre-existing — Dev: toolbar removed, see #199");
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    // Activate admin role via dev toolbar
    await page.click("button:has-text('Dev:')");
    await page.waitForTimeout(200);
    await page.click("button:has-text('Admin')");
    await page.waitForTimeout(500);
  });

  test("admin section appears in sidebar", async ({ page }) => {
    const navText = await page.textContent("nav");
    expect(navText).toContain("Administration");
  });

  const adminPages: [string, string, string][] = [
    ["/admin/users", "User Management"],
    ["/admin/access", "Access Rights"],
    ["/admin/rate-limits", "Rate Limits"],
    ["/admin/modules", "Module Activation"],
    ["/admin/settings", "Global Settings"],
    ["/admin/logs", "Log Viewer"],
  ];

  for (const [route, expected] of adminPages) {
    test(`admin page ${route} shows correct heading`, async ({ page }) => {
      await page.goto(route, { waitUntil: "networkidle" });
      await page.waitForTimeout(300);
      await expect(page.locator("h1")).toHaveText(expected);
    });
  }
});

test.describe("Visitor Mode", () => {
  test("admin section is hidden in visitor mode", async ({ page }) => {
    test.skip(!!process.env.CI, "Pre-existing — Dev: toolbar removed, see #199");
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await page.click("button:has-text('Dev:')");
    await page.waitForTimeout(200);
    await page.click("button:has-text('Visitor')");
    await page.waitForTimeout(500);

    const navText = await page.textContent("nav");
    expect(navText).not.toContain("Administration");

    const headerText = await page.textContent("header");
    expect(headerText).toContain("Sign In");
  });
});
