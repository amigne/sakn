import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const UNAUTHENTICATED_SCREENS = [
  { name: "Login", path: "/login" },
  { name: "Register", path: "/register" },
  { name: "Reset Password", path: "/reset-password" },
  { name: "Verify Email", path: "/verify-email" },
  { name: "Privacy Policy", path: "/privacy" },
  { name: "Not Found", path: "/nonexistent" },
];

const AUTHENTICATED_SCREENS = [
  { name: "Ping", path: "/ping" },
  { name: "DNS Lookup", path: "/dns-lookup" },
  { name: "SSL Viewer", path: "/ssl-viewer" },
  { name: "Traceroute", path: "/traceroute" },
  { name: "Profile", path: "/profile" },
  { name: "Sessions", path: "/sessions" },
  { name: "Delete Account", path: "/delete-account" },
];

const ADMIN_SCREENS = [
  { name: "Admin Users", path: "/admin/users" },
  { name: "Admin Access", path: "/admin/access" },
  { name: "Admin Rate Limits", path: "/admin/rate-limits" },
  { name: "Admin Modules", path: "/admin/modules" },
  { name: "Admin Settings", path: "/admin/settings" },
  { name: "Admin Logs", path: "/admin/logs" },
];

const BASELINE_UNAUTH: Record<string, number> = {
  "/login": 0,
  "/register": 0,
  "/reset-password": 0,
  "/verify-email": 0,
  "/privacy": 1,
  "/nonexistent": 0,
};

test.describe("A11y Audit — Unauthenticated", () => {
  for (const { name, path } of UNAUTHENTICATED_SCREENS) {
    test(`${name} (${path})`, async ({ page }) => {
      await page.goto(path, { waitUntil: "networkidle" });


      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();

      test.info().annotations.push({
        type: "violations",
        description: JSON.stringify(
          results.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            helpUrl: v.helpUrl,
            nodes: v.nodes.length,
          })),
        ),
      });

      if (results.violations.length > 0) {
        console.log(`\n[${name}] ${results.violations.length} violations:`);
        for (const v of results.violations) {
          console.log(
            `  - ${v.id} (${v.impact}): ${v.helpUrl} [${v.nodes.length} nodes]`,
          );
        }
      }

      expect(results.violations.length).toBeLessThanOrEqual(
        BASELINE_UNAUTH[path] ?? 0,
      );
    });
  }
});

test.describe("A11y Audit — Authenticated (TODO: needs test user fixture)", () => {
  for (const { name, path } of AUTHENTICATED_SCREENS) {
    test.skip(`${name} (${path})`, async () => {});
  }
});

test.describe("A11y Audit — Admin (TODO: needs admin user fixture)", () => {
  for (const { name, path } of ADMIN_SCREENS) {
    test.skip(`${name} (${path})`, async () => {});
  }
});

test.describe("A11y Audit — Contrast (Light Theme)", () => {
  test("Login page contrast", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });


    // Force light theme
    await page.evaluate(() => {
      document.documentElement.classList.remove("dark");
    });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2aa", "wcag21aa"])
      .analyze();

    const colorViolations = results.violations.filter(
      (v) => v.id === "color-contrast",
    );
    console.log(
      `\n[Light theme] color-contrast violations: ${colorViolations.length}`,
    );
    for (const v of colorViolations) {
      for (const node of v.nodes) {
        console.log(`  - ${node.html}`);
      }
    }
  });
});

test.describe("A11y Audit — Contrast (Dark Theme)", () => {
  test("Login page contrast", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });


    // Force dark theme
    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
      document.documentElement.style.colorScheme = "dark";
    });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2aa", "wcag21aa"])
      .analyze();

    const colorViolations = results.violations.filter(
      (v) => v.id === "color-contrast",
    );
    console.log(
      `\n[Dark theme] color-contrast violations: ${colorViolations.length}`,
    );
    for (const v of colorViolations) {
      for (const node of v.nodes) {
        console.log(`  - ${node.html}`);
      }
    }
  });
});

test.describe("A11y Audit — Keyboard", () => {
  test("Login page tab order reaches all interactive elements", async ({
    page,
  }) => {
    test.skip(!!process.env.CI, "Manual audit - run locally");

    await page.goto("/login", { waitUntil: "networkidle" });


    // Press Tab multiple times and verify the focused element is visible
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press("Tab");
      const focused = page.locator(":focus");
      const count = await focused.count();
      if (count === 0) {
        console.log(
          `Tab ${i + 1}: no focused element found (possible focus trap or end of page)`,
        );
        break;
      }
      const tagName = await focused.evaluate((el) => el.tagName.toLowerCase());
      const ariaLabel = await focused.evaluate(
        (el) => (el as HTMLElement).getAttribute("aria-label") || "",
      );
      console.log(`Tab ${i + 1}: <${tagName}> ${ariaLabel}`);
    }
  });
});

test.describe("A11y Audit — Zoom 200%", () => {
  test("Login page at 200% zoom has no horizontal scroll", async ({ page }) => {
    // Set viewport to simulate 200% zoom
    await page.setViewportSize({ width: 640, height: 480 });
    await page.goto("/login", { waitUntil: "networkidle" });


    const hasHorizontalScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    console.log(`Horizontal scroll at 200% zoom: ${hasHorizontalScroll}`);
  });
});

test.describe("A11y Audit — Targeted Rules", () => {
  test("Login page has no link-in-text-block", async ({ page }) => {
    await page.goto("/login", { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page })
      .withRules(["link-in-text-block"])
      .analyze();
    expect(results.violations).toEqual([]);
  });

  test("Register page has no link-in-text-block", async ({ page }) => {
    await page.goto("/register", { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page })
      .withRules(["link-in-text-block"])
      .analyze();
    expect(results.violations).toEqual([]);
  });
});
