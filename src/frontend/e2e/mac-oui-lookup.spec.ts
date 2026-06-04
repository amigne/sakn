import { test, expect } from "@playwright/test";

/**
 * MAC OUI Lookup — E2E tests (CI-safe, no backend required).
 *
 * All API calls are intercepted and mocked so the tests run fully
 * self-contained. The auth init returns an authenticated user, the
 * tools list includes mac_oui, and the execute endpoint returns
 * fixture data.
 */

// ── Fixtures ──────────────────────────────────────────────────────────

const AUTH_USER = {
  id: "test-user-1",
  email: "test@example.com",
  first_name: "Test",
  last_name: "User",
  role: "authenticated",
  status: "active",
  email_verified: true,
  locale: "en-US",
  created_at: "2024-01-01T00:00:00Z",
};

const TOOLS_LIST = {
  tools: [
    { name: "ping" },
    { name: "traceroute" },
    { name: "dns_lookup" },
    { name: "ssl_viewer" },
    { name: "mac_oui" },
  ],
};

const MAC_OUI_RESULTS = {
  result: {
    success: true,
    duration_ms: 12,
    error: null,
    data: {
      results: [
        {
          input: "001122334455",
          oui_display: "00:11:22:33:44:55",
          result: {
            oui_type: "MA-L",
            organization: "Acme Corp",
            address: "123 Main St, Anytown, USA",
            first_seen: "2024-01-15",
            last_seen: "2026-05-20",
          },
          ambiguous_extends_ma_m: false,
          ambiguous_extends_ma_s: false,
          history: [],
        },
        {
          input: "AABBCCDDEEFF",
          oui_display: "AA:BB:CC:DD:EE:FF",
          result: {
            oui_type: "MA-L",
            organization: "Global Tech Inc",
            address: "456 Oak Ave, Sometown, USA",
            first_seen: "2024-03-10",
            last_seen: "2026-05-19",
          },
          ambiguous_extends_ma_m: false,
          ambiguous_extends_ma_s: false,
          history: [],
        },
      ],
      rejected: [],
      parse_stats: { total_inputs: 2, valid: 2, rejected: 0, unique: 2 },
    },
  },
};

// ── Setup ─────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  // Mock all backend API calls so tests run without a real server.
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(AUTH_USER),
    }),
  );

  await page.route("**/api/v1/tools", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(TOOLS_LIST),
    }),
  );

  await page.route("**/api/v1/tools/mac_oui/execute", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MAC_OUI_RESULTS),
    }),
  );

  // Some rate-limiting or CSRF endpoints may be called — let them pass through silently.
  await page.route("**/api/v1/auth/csrf", (route) =>
    route.fulfill({ status: 200, body: "{}" }),
  );
});

// ── Tests ─────────────────────────────────────────────────────────────

test.describe("MAC OUI Lookup Page", () => {
  test("golden path: paste MAC addresses, execute, verify 2 result rows", async ({
    page,
  }) => {
    await page.goto("/mac-oui");
    await page.waitForLoadState("networkidle");

    // Page should have rendered
    await expect(page.getByRole("heading", { name: "MAC OUI Lookup" })).toBeVisible();
    await expect(page.getByRole("textbox")).toBeVisible();

    // Fill textarea with MAC addresses
    const text = [
      "Internet  10.0.0.1   0   00:11:22:33:44:55   ARPA   Vlan10",
      "Internet  10.0.0.2   0   aa:bb:cc:dd:ee:ff   ARPA   Vlan10",
    ].join("\n");
    await page.getByRole("textbox").fill(text);

    // Character counter should update
    await expect(page.locator("#mac-oui-charcount")).toContainText(
      /\/ 50[,.]?000/,
    );

    // Click Execute
    await page.getByRole("button", { name: /Lookup/i }).click();

    // Wait for the results table to appear
    const table = page.locator("table");
    await expect(table).toBeVisible({ timeout: 10000 });

    // Verify both rows appear
    const rows = table.locator("tbody tr");
    await expect(rows).toHaveCount(2);

    // Verify vendor names are displayed
    await expect(page.getByText("Acme Corp")).toBeVisible();
    await expect(page.getByText("Global Tech Inc")).toBeVisible();
  });

  test("empty state: text without MAC addresses shows no_results message", async ({
    page,
  }) => {
    await page.goto("/mac-oui");
    await page.waitForLoadState("networkidle");

    await page.getByRole("textbox").fill("Hello, world! No MAC here.");
    await page.getByRole("button", { name: /Lookup/i }).click();

    // Should show the no-results message (extraction finds nothing,
    // so no API call is made).
    await expect(
      page.getByText(/No MAC addresses or OUIs found/),
    ).toBeVisible({ timeout: 5000 });
  });

  test("copy global button copies TSV-formatted results", async ({ page }) => {
    await page.goto("/mac-oui");
    await page.waitForLoadState("networkidle");

    await page
      .getByRole("textbox")
      .fill("00:11:22:33:44:55 and aa:bb:cc:dd:ee:ff");
    await page.getByRole("button", { name: /Lookup/i }).click();

    // Wait for results
    await expect(page.locator("table")).toBeVisible({ timeout: 10000 });

    // Intercept clipboard writes so we can verify the TSV content
    // cross-browser (Firefox doesn't support clipboard-read/write permissions).
    await page.evaluate(() => {
      let captured = "";
      Object.defineProperty(navigator, "clipboard", {
        value: {
          writeText: (text: string) => {
            captured = text;
            return Promise.resolve();
          },
          readText: () => Promise.resolve(captured),
        },
        configurable: true,
      });
    });

    // Click the global copy button
    await page
      .getByRole("button", { name: /Copy all results/i })
      .click();

    // Read the captured clipboard content
    const clipboard = await page.evaluate(() =>
      navigator.clipboard.readText(),
    );
    expect(clipboard).toContain(
      "OUI\tVendor\tType\tFirst seen\tLast seen\tAddress",
    );
    expect(clipboard).toContain("Acme Corp");
    expect(clipboard).toContain("Global Tech Inc");
  });
});
