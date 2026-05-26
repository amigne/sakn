import { test, expect } from "@playwright/test";

test.describe("Layout", () => {
  test("page title is correct", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page).toHaveTitle("SAKN — Network Diagnostic Tools");
  });

  test("header is visible and contains SAKN", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator("header")).toBeVisible();
    await expect(page.locator("header")).toContainText("SAKN");
  });

  test("sidebar is visible with tool links", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    const nav = page.locator("nav");
    await expect(nav).toBeVisible();
    await expect(nav).toContainText("Ping");
    await expect(nav).toContainText("Traceroute");
    await expect(nav).toContainText("DNS");
    await expect(nav).toContainText("TLS");
  });

  test("footer is visible with version", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    const footer = page.getByRole("contentinfo");
    await expect(footer).toBeVisible();
    await expect(footer).toContainText(/SAKN v/);
  });

  test("ping page loads as default", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.locator("h1")).toHaveText("Ping");
  });

  test("navigates to all tool pages via sidebar", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    const tools: [string, string, string][] = [
      ["Traceroute", "/traceroute", "Traceroute"],
      ["DNS Lookup", "/dns", "DNS Lookup"],
      ["TLS/SSL", "/ssl", "TLS/SSL Certificate Viewer"],
    ];

    for (const [label, route, expected] of tools) {
      await page.click(`a[href="${route}"]`);
      await expect(page.locator("h1")).toHaveText(expected);
    }
  });

  test("executes ping and shows results", async ({ page }) => {
    test.skip(!!process.env.CI, "Backend required — follow-up issue for E2E backend-dependent tests");
    await page.goto("/ping", { waitUntil: "networkidle" });

    const execBtn = page.locator("button", { hasText: "Execute" });
    await expect(execBtn).toBeVisible();
    await execBtn.click();
    await expect(page.locator("table tr").first()).toBeVisible({ timeout: 10000 });

    const rows = await page.locator("table tr").count();
    expect(rows).toBeGreaterThan(5);
  });

  test("table/text toggle works", async ({ page }) => {
    test.skip(!!process.env.CI, "Backend required — follow-up issue for E2E backend-dependent tests");
    await page.goto("/ping", { waitUntil: "networkidle" });

    const execBtn = page.locator("button", { hasText: "Execute" });
    await execBtn.click();
    await expect(page.locator("table tr").first()).toBeVisible({ timeout: 10000 });

    await page.click('button:has-text("Text")');
    await expect(page.locator("pre").first()).toBeVisible({ timeout: 5000 });
  });
});
