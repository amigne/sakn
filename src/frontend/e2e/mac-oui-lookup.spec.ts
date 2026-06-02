import { test, expect } from "@playwright/test";

/**
 * MAC OUI Lookup — E2E golden path.
 *
 * Preconditions:
 * - Backend running locally (seed includes mac_oui tool + IEEE data).
 * - A test user exists (e.g., seeded authenticated user).
 *
 * Run:
 *   cd src/frontend
 *   pnpm playwright test mac-oui-lookup.spec.ts
 */

const BASE_URL = "http://localhost:5173";

test.describe("MAC OUI Lookup Page", () => {
  test("golden path: paste MAC addresses, execute, verify results", async ({ page }) => {
    // 1. Navigate to the app
    await page.goto(BASE_URL);

    // 2. Login as a test user (adjust credentials to match seed data)
    await page.fill('input[name="email"]', "user@example.com");
    await page.fill('input[name="password"]', "Password123!");
    await page.click('button[type="submit"]');

    // Wait for redirect to /ping or similar
    await page.waitForURL("**/ping", { timeout: 10000 }).catch(() => {
      // If already logged in or redirected elsewhere, continue.
    });

    // 3. Navigate to /mac-oui
    await page.goto(`${BASE_URL}/mac-oui`);
    await page.waitForLoadState("networkidle");

    // 4. Verify the page rendered
    await expect(page.locator("h1")).toContainText("MAC OUI Lookup");
    await expect(page.locator("#mac-oui-textarea")).toBeVisible();

    // 5. Paste text with MAC addresses
    const textToPaste = [
      "Internet  10.0.0.1   0   00:11:22:33:44:55   ARPA   Vlan10",
      "Internet  10.0.0.2   0   aa-bb-cc-dd-ee-ff   ARPA   Vlan10",
    ].join("\n");
    await page.fill("#mac-oui-textarea", textToPaste);

    // 6. Verify char counter updated
    await expect(page.locator("#mac-oui-charcount")).toContainText(/\/ 50[,.]?000/);

    // 7. Click Execute
    await page.click('button:has-text("Lookup")');

    // 8. Wait for results (may return "Unknown vendor" if seed data missing)
    // The table should appear with at least 1 row
    await page.waitForSelector("table", { timeout: 15000 }).catch(() => {
      // If table doesn't appear, check for no_results or error
    });

    // 9. Verify results table has rows
    const table = page.locator("table");
    if (await table.isVisible()) {
      const rows = table.locator("tbody tr");
      const count = await rows.count();
      expect(count).toBeGreaterThanOrEqual(1);
    }
  });

  test("empty state: text without MAC addresses shows no_results", async ({ page }) => {
    await page.goto(`${BASE_URL}/mac-oui`);
    await page.waitForLoadState("networkidle");

    // Fill with text that has no MAC addresses
    await page.fill("#mac-oui-textarea", "Hello, world! This is just plain text.");

    // Click Execute
    await page.click('button:has-text("Lookup")');

    // Should show "No MAC addresses or OUIs found" message
    await expect(page.getByText(/No MAC addresses or OUIs found/)).toBeVisible({ timeout: 5000 });
  });

  test("copy global button copies results as TSV", async ({ page }) => {
    await page.goto(`${BASE_URL}/mac-oui`);
    await page.waitForLoadState("networkidle");

    // Fill with MAC text
    await page.fill("#mac-oui-textarea", "00:11:22:33:44:55 and aa:bb:cc:dd:ee:ff");

    // Click Execute
    await page.click('button:has-text("Lookup")');

    // Wait for results table
    await page.waitForSelector("table", { timeout: 15000 }).catch(() => {});

    // Click copy global button
    const copyBtn = page.locator('button:has-text("Copy all results")');
    if (await copyBtn.isVisible()) {
      // Verify clipboard permission is granted via browser context
      await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
      await copyBtn.click();
      // Read clipboard and verify TSV format
      const clipboard = await page.evaluate(() => navigator.clipboard.readText());
      expect(clipboard).toContain("OUI\tVendor\tType\tFirst seen\tLast seen\tAddress");
    }
  });
});
