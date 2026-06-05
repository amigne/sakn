import { expect, test } from "@playwright/test";

/**
 * Secret Generator — E2E tests (CI-safe, no backend required).
 *
 * The secret generator is a frontend-only tool. All secrets are
 * generated client-side via the Web Crypto API. No backend execution
 * endpoint is ever called.
 *
 * All auth/tools-list API calls are intercepted and mocked so the
 * tests run fully self-contained.
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
    { name: "secret_generator" },
  ],
};

// ── Network tracking ──────────────────────────────────────────────────

/** Track whether a forbidden backend call was made. */
function trackForbiddenRequests(page: import("@playwright/test").Page) {
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/tools/secret_generator/execute")) {
      console.error(`[SECURITY] Unexpected backend call: ${request.method()} ${request.url()}`);
    }
  });
}

// ── Setup ─────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  // Mock auth
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(AUTH_USER),
    }),
  );

  // Mock tools list — must include secret_generator for sidebar/guard
  await page.route("**/api/v1/tools", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(TOOLS_LIST),
    }),
  );

  // Mock CSRF
  await page.route("**/api/v1/auth/csrf", (route) => route.fulfill({ status: 200, body: "{}" }));

  // Track any forbidden backend execute calls
  trackForbiddenRequests(page);
});

// ── Tests ─────────────────────────────────────────────────────────────

test.describe("Secret Generator Page", () => {
  test("renders mode tabs and regenerates a password", async ({ page }) => {
    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    // Page heading should be visible
    await expect(page.getByRole("heading", { name: "Secret Generator" })).toBeVisible();

    // Mode tabs should be present
    await expect(page.getByRole("tab", { name: "Password" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Token" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Hex" })).toBeVisible();

    // Regenerate button should be present
    await expect(page.getByRole("button", { name: /Regenerate/i })).toBeVisible();

    // Click Regenerate to generate a password
    await page.getByRole("button", { name: /Regenerate/i }).click();

    // A textarea with the generated secret should appear
    const secretTextarea = page.locator("textarea[readonly]");
    await expect(secretTextarea).toBeVisible();
    const secretValue = await secretTextarea.inputValue();
    expect(secretValue.length).toBeGreaterThan(0);

    // Strength indicator should be visible
    await expect(page.getByText(/Weak|Fair|Strong|Very strong/)).toBeVisible();

    // Entropy info should be present
    await expect(page.getByText(/characters/)).toBeVisible();
    await expect(page.getByText(/bits/)).toBeVisible();
  });

  test("generates different secrets on regenerate", async ({ page }) => {
    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /Regenerate/i }).click();
    const secret1 = await page.locator("textarea[readonly]").inputValue();

    await page.getByRole("button", { name: /Regenerate/i }).click();
    const secret2 = await page.locator("textarea[readonly]").inputValue();

    expect(secret1).not.toBe(secret2);
  });

  test("switches to token mode and generates a token", async ({ page }) => {
    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    // Click the Token tab
    await page.getByRole("tab", { name: "Token" }).click();

    // Password charsets should no longer be visible
    await expect(page.getByText(/Uppercase/)).not.toBeVisible();

    // Click Regenerate in token mode
    await page.getByRole("button", { name: /Regenerate/i }).click();

    // A token should be generated
    const secretValue = await page.locator("textarea[readonly]").inputValue();
    expect(secretValue.length).toBeGreaterThan(0);
    // Tokens use base64url: only A-Za-z0-9-_
    expect(/^[A-Za-z0-9\-_]+$/.test(secretValue)).toBe(true);
  });

  test("switches to hex mode and generates a hex secret", async ({ page }) => {
    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    // Click the Hex tab
    await page.getByRole("tab", { name: "Hex" }).click();

    // Password charsets should no longer be visible
    await expect(page.getByText(/Uppercase/)).not.toBeVisible();

    // Click Regenerate in hex mode
    await page.getByRole("button", { name: /Regenerate/i }).click();

    const secretValue = await page.locator("textarea[readonly]").inputValue();
    expect(secretValue.length).toBeGreaterThan(0);
    // Hex output should only contain hex chars
    expect(/^[0-9a-f]+$/.test(secretValue)).toBe(true);
  });

  test("copies the secret to clipboard", async ({ page }) => {
    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    // Generate a secret first
    await page.getByRole("button", { name: /Regenerate/i }).click();
    await expect(page.locator("textarea[readonly]")).toBeVisible();

    // Grant clipboard permission and intercept writeText
    await page.evaluate(() => {
      let _clipboard = "";
      Object.defineProperty(navigator, "clipboard", {
        value: {
          writeText: (text: string) => {
            _clipboard = text;
            return Promise.resolve();
          },
          readText: () => Promise.resolve(_clipboard),
        },
        writable: true,
        configurable: true,
      });
    });

    // Click Copy
    await page.getByRole("button", { name: /Copy/i }).click();

    // "Copied!" toast should appear
    await expect(page.getByText("Copied!")).toBeVisible();

    // Auto-clear notice should show 30s countdown
    await expect(page.getByText(/Clipboard will be cleared/)).toBeVisible();
  });

  test("shows validation error when no charset selected", async ({ page }) => {
    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    // Uncheck all charset toggles
    const toggles = page.locator('[role="switch"]');
    const count = await toggles.count();
    for (let i = 0; i < count; i++) {
      // Only click if checked (data-state="checked")
      const state = await toggles.nth(i).getAttribute("data-state");
      if (state === "checked") {
        await toggles.nth(i).click();
      }
    }

    // Try to generate
    await page.getByRole("button", { name: /Regenerate/i }).click();

    // Validation error should appear
    await expect(page.getByText(/At least one character set/)).toBeVisible();
  });

  test("resets clears the result", async ({ page }) => {
    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    // Generate a secret
    await page.getByRole("button", { name: /Regenerate/i }).click();
    await expect(page.locator("textarea[readonly]")).toBeVisible();

    // Click Reset
    await page.getByRole("button", { name: /Reset/i }).click();

    // Secret textarea should no longer be visible
    await expect(page.locator("textarea[readonly]")).not.toBeVisible();
  });

  test("no backend execute request is emitted (client-side only)", async ({ page }) => {
    const executeCalls: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/tools/secret_generator/execute")) {
        executeCalls.push(request.url());
      }
    });

    await page.goto("/secret-generator");
    await page.waitForLoadState("networkidle");

    // Generate multiple times
    await page.getByRole("button", { name: /Regenerate/i }).click();
    await page.getByRole("button", { name: /Regenerate/i }).click();

    // Switch to token mode and generate
    await page.getByRole("tab", { name: "Token" }).click();
    await page.getByRole("button", { name: /Regenerate/i }).click();

    // Switch to hex mode and generate
    await page.getByRole("tab", { name: "Hex" }).click();
    await page.getByRole("button", { name: /Regenerate/i }).click();

    // No execute calls should have been made
    expect(executeCalls.length).toBe(0);
  });
});
