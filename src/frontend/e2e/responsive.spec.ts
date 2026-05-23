import { test, expect } from "@playwright/test";

test.describe("Responsive", () => {
  test("desktop: sidebar expanded by default, hamburger in sidebar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const headerHam = await page
      .locator("header button[aria-label='Toggle sidebar']")
      .count();
    const sidebarHam = await page
      .locator("nav button[aria-label='Toggle sidebar']")
      .count();
    expect(headerHam).toBe(0);
    expect(sidebarHam).toBe(1);

    const navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeGreaterThan(100); // expanded
  });

  test("desktop: can collapse sidebar via hamburger", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await page.click('button[aria-label="Toggle sidebar"]');
    await page.waitForTimeout(400);

    const navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeLessThan(100); // collapsed
  });

  test("tablet: sidebar collapsed by default", async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeLessThan(100);
  });

  test("tablet: can expand sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await page.click('button[aria-label="Toggle sidebar"]');
    await page.waitForTimeout(400);

    const navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeGreaterThan(100);
  });

  test("tablet: resize within breakpoint keeps sidebar state", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await page.locator("nav button[aria-label='Toggle sidebar']").click();
    await page.waitForTimeout(400);

    // Resize within tablet range
    await page.setViewportSize({ width: 850, height: 800 });
    await page.waitForTimeout(400);

    const navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeGreaterThan(100); // stays expanded
  });

  test("mobile: hamburger in header, sidebar hidden initially", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 500, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    const headerHam = await page
      .locator("header button[aria-label='Toggle sidebar']")
      .count();
    expect(headerHam).toBe(1);

    const navVisible = await page.locator("nav").isVisible();
    expect(navVisible).toBe(false);
  });

  test("mobile: hamburger opens overlay sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 500, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await page.click("header button[aria-label='Toggle sidebar']");
    await page.waitForTimeout(400);

    await expect(page.locator("nav")).toBeVisible();
  });

  test("tablet-to-desktop transition auto-expands sidebar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    let navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeLessThan(100); // collapsed on tablet

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.waitForTimeout(600);

    navWidth = await page.locator("nav").evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeGreaterThan(100); // auto-expanded on desktop
  });

  test("desktop-to-tablet transition auto-collapses sidebar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    let navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeGreaterThan(100); // expanded on desktop

    await page.setViewportSize({ width: 900, height: 800 });
    await page.waitForTimeout(600);

    navWidth = await page.locator("nav").evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeLessThan(100); // auto-collapsed on tablet
  });

  test("mobile-to-tablet transitions cleanly", async ({ page }) => {
    await page.setViewportSize({ width: 500, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    // Open mobile sidebar
    await page.click("header button[aria-label='Toggle sidebar']");
    await page.waitForTimeout(300);
    expect(await page.locator("nav").isVisible()).toBe(true);

    // Transition to tablet
    await page.setViewportSize({ width: 900, height: 800 });
    await page.waitForTimeout(600);

    const navVisible = await page.locator("nav").isVisible();
    const headerHam = await page
      .locator("header button[aria-label='Toggle sidebar']")
      .count();
    expect(navVisible).toBe(true);
    expect(headerHam).toBe(0); // hamburger moves to sidebar
  });
});
