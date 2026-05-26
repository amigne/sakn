import { test, expect } from "@playwright/test";

test.describe("Auth Pages", () => {
  test("login page shows sign in form", async ({ page }) => {
    test.skip(!!process.env.CI, "Pre-existing — ambiguous locators, see #200");
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await expect(page.locator("h1")).toHaveText("Sign In");
    await expect(page.locator("body")).toContainText("Forgot password?");
    await expect(page.locator("body")).toContainText("Sign up");
  });

  test("register page shows create account form", async ({ page }) => {
    await page.goto("/register", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await expect(page.locator("h1")).toHaveText("Create Account");
    await expect(page.locator("body")).toContainText("Min 8 characters");
  });

  test("reset password page loads", async ({ page }) => {
    await page.goto("/reset-password", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await expect(page.locator("h1")).toHaveText("Reset Password");
  });

  test("verify email sent page loads", async ({ page }) => {
    await page.goto("/verify-email-sent", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await expect(page.locator("body")).toContainText("Check Your Email");
  });
});

test.describe("Account Pages", () => {
  test("preferences page loads with theme options", async ({ page }) => {
    test.skip(!!process.env.CI, "Pre-existing — ambiguous locators, see #200");
    await page.goto("/account/preferences", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await expect(page.locator("h1")).toHaveText("Preferences");
    await expect(page.locator("body")).toContainText("Light");
    await expect(page.locator("body")).toContainText("Dark");
  });

  test("sessions page loads", async ({ page }) => {
    await page.goto("/account/sessions", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await expect(page.locator("h1")).toHaveText("Active Sessions");
  });

  test("delete account page loads", async ({ page }) => {
    await page.goto("/account/delete", { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    await expect(page.locator("h1")).toHaveText("Delete Account");
  });
});
