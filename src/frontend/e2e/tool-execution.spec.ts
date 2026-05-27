import { test, expect } from "@playwright/test";

test.describe("Tool Execution", () => {
  test("executes ping and displays results in table", async ({ page }) => {
    await page.goto("/ping", { waitUntil: "networkidle" });

    await page.getByPlaceholder("8.8.8.8").fill("1.1.1.1");
    const execBtn = page.locator("button", { hasText: "Execute" });
    await execBtn.click();
    await expect(page.locator("table tr").first()).toBeVisible({ timeout: 15000 });

    const rows = await page.locator("table tr").count();
    expect(rows).toBeGreaterThan(0);

    await expect(page.getByText("Summary")).toBeVisible({ timeout: 15000 });
  });

  test("text view toggle shows raw output", async ({ page }) => {
    await page.goto("/ping", { waitUntil: "networkidle" });

    await page.getByPlaceholder("8.8.8.8").fill("1.1.1.1");
    await page.locator("button", { hasText: "Execute" }).click();
    await expect(page.locator("table tr").first()).toBeVisible({ timeout: 15000 });

    const textBtn = page.locator("button", { hasText: /text/i });
    await expect(textBtn).toBeVisible();
    await textBtn.click();
    // After toggle, the <pre> replaces the <table> in the DOM.
    await expect(page.locator("pre").first()).toBeAttached({ timeout: 5000 });
  });
});
