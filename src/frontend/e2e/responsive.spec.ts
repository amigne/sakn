import { test, expect } from "@playwright/test";

test.describe("Responsive", () => {
  test("desktop: sidebar expanded by default, hamburger in sidebar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

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

    await page.click('button[aria-label="Toggle sidebar"]');
    await expect.poll(async () => {
      return await page.locator("nav").evaluate((el) => el.offsetWidth);
    }).toBeLessThan(100); // collapsed
  });

  test("tablet: sidebar collapsed by default", async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    const navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeLessThan(100);
  });

  test("tablet: can expand sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    await page.click('button[aria-label="Toggle sidebar"]');
    await expect.poll(async () => {
      return await page.locator("nav").evaluate((el) => el.offsetWidth);
    }).toBeGreaterThan(100);
  });

  test("tablet: resize within breakpoint keeps sidebar state", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    await page.locator("nav button[aria-label='Toggle sidebar']").click();
    await expect.poll(async () => {
      return await page.locator("nav").evaluate((el) => el.offsetWidth);
    }).toBeGreaterThan(100);

    // Resize within tablet range
    await page.setViewportSize({ width: 850, height: 800 });
    await expect.poll(async () => {
      return await page.locator("nav").evaluate((el) => el.offsetWidth);
    }).toBeGreaterThan(100); // stays expanded
  });

  test("mobile: hamburger in header, sidebar hidden initially", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 500, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    const headerHam = await page
      .locator("header button[aria-label='Toggle sidebar']")
      .count();
    expect(headerHam).toBe(1);

    await expect(page.locator("nav")).not.toBeVisible();
  });

  test("mobile: hamburger opens overlay sidebar", async ({ page }) => {
    await page.setViewportSize({ width: 500, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    await page.click("header button[aria-label='Toggle sidebar']");
    await expect(page.locator("nav")).toBeVisible();
  });

  test("tablet-to-desktop transition auto-expands sidebar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    let navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeLessThan(100); // collapsed on tablet

    await page.setViewportSize({ width: 1280, height: 800 });
    await expect.poll(async () => {
      return await page.locator("nav").evaluate((el) => el.offsetWidth);
    }).toBeGreaterThan(100); // auto-expanded on desktop
  });

  test("desktop-to-tablet transition auto-collapses sidebar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    let navWidth = await page
      .locator("nav")
      .evaluate((el) => el.offsetWidth);
    expect(navWidth).toBeGreaterThan(100); // expanded on desktop

    await page.setViewportSize({ width: 900, height: 800 });
    await expect.poll(async () => {
      return await page.locator("nav").evaluate((el) => el.offsetWidth);
    }).toBeLessThan(100); // auto-collapsed on tablet
  });

  test("mobile-to-tablet transitions cleanly", async ({ page }) => {
    await page.setViewportSize({ width: 500, height: 800 });
    await page.goto("/", { waitUntil: "networkidle" });

    // Open mobile sidebar
    await page.click("header button[aria-label='Toggle sidebar']");
    await expect(page.locator("nav")).toBeVisible();

    // Transition to tablet
    await page.setViewportSize({ width: 900, height: 800 });
    await expect(page.locator("nav")).toBeVisible();

    await expect(page.locator("header button[aria-label='Toggle sidebar']")).toHaveCount(0);
  });
});
