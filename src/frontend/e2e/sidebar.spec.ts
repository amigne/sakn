import { test, expect } from "@playwright/test";

test.describe("Sidebar", () => {
  test("navigates to admin section via dev toolbar", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await page.click("button:has-text('Dev:')");
    await page.waitForTimeout(200);
    await page.click("button:has-text('Admin')");
    await page.waitForTimeout(500);

    const navText = await page.textContent("nav");
    expect(navText).toContain("Administration");
  });
});
