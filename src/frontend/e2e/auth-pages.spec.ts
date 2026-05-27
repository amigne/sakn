import { test, expect } from "@playwright/test";

test.describe("Auth Pages", () => {
  test("login page shows sign in form", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });


    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
    await expect(page.getByText("Forgot password?")).toBeVisible();
    await expect(page.getByText("Sign up")).toBeVisible();
  });

  test("register page shows create account form", async ({ page }) => {
    await page.goto("/register", { waitUntil: "networkidle" });


    await expect(page.getByRole("heading", { name: /create account/i })).toBeVisible();
    await expect(page.getByText("Min 8 characters")).toBeVisible();
  });

  test("reset password page loads", async ({ page }) => {
    await page.goto("/reset-password", { waitUntil: "networkidle" });


    await expect(page.getByRole("heading", { name: /reset password/i })).toBeVisible();
  });

  test("verify email sent page loads", async ({ page }) => {
    await page.goto("/verify-email-sent", { waitUntil: "networkidle" });


    await expect(page.getByText("Check Your Email")).toBeVisible();
  });
});

test.describe("Account Pages", () => {
  test("preferences page loads with theme options", async ({ page }) => {
    await page.goto("/account/preferences", { waitUntil: "networkidle" });


    await expect(page.getByRole("heading", { name: /profile/i, level: 1 })).toBeVisible();
    await expect(page.getByText("Light")).toBeVisible();
    await expect(page.getByText("Dark")).toBeVisible();
  });

  test("sessions page loads", async ({ page }) => {
    // Mock the sessions API: the backend is running in full-stack CI and
    // returns 401 (no auth cookie), which triggers a redirect to /login
    // via the api.ts interceptor.  Without this mock the test would never
    // see the sessions heading.
    await page.route("**/api/v1/sessions", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ sessions: [] }),
      });
    });

    await page.goto("/account/sessions", { waitUntil: "networkidle" });


    await expect(page.getByRole("heading", { name: /active sessions/i })).toBeVisible();
  });

  test("delete account page loads", async ({ page }) => {
    await page.goto("/account/delete", { waitUntil: "networkidle" });


    await expect(page.getByRole("heading", { name: /delete account/i })).toBeVisible();
  });
});
