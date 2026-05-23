import { test, expect } from "@playwright/test";

test.describe("Layout", () => {
  test("page title is correct", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await expect(page).toHaveTitle("SAKN — Network Diagnostic Tools");
  });

  test("header is visible and contains SAKN", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await expect(page.locator("header")).toBeVisible();
    await expect(page.locator("header")).toContainText("SAKN");
  });

  test("sidebar is visible with tool links", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const nav = page.locator("nav");
    await expect(nav).toBeVisible();
    await expect(nav).toContainText("Ping");
    await expect(nav).toContainText("Traceroute");
    await expect(nav).toContainText("DNS");
    await expect(nav).toContainText("TLS");
  });

  test("footer is visible with version", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await expect(page.locator("footer")).toBeVisible();
    await expect(page.locator("footer")).toContainText("v0.0.1");
  });

  test("ping page loads as default", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await expect(page.locator("h1")).toHaveText("Ping");
  });

  test("navigates to all tool pages via sidebar", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const tools: [string, string, string][] = [
      ["Traceroute", "/traceroute", "Traceroute"],
      ["DNS Lookup", "/dns", "DNS Lookup"],
      ["TLS/SSL", "/ssl", "TLS/SSL Certificate Viewer"],
    ];

    for (const [label, route, expected] of tools) {
      await page.click(`a[href="${route}"]`);
      await page.waitForTimeout(400);
      await expect(page.locator("h1")).toHaveText(expected);
    }
  });

  test("executes ping and shows results", async ({ page }) => {
    await page.goto("/ping", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const execBtn = page.locator("button", { hasText: "Execute" });
    await expect(execBtn).toBeVisible();
    await execBtn.click();
    await page.waitForTimeout(4000);

    const rows = await page.locator("table tr").count();
    expect(rows).toBeGreaterThan(5);
  });

  test("table/text toggle works", async ({ page }) => {
    await page.goto("/ping", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const execBtn = page.locator("button", { hasText: "Execute" });
    await execBtn.click();
    await page.waitForTimeout(4000);

    await page.click('button:has-text("Text")');
    await page.waitForTimeout(300);
    await expect(page.locator("pre").first()).toBeVisible();
  });
});
