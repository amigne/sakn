import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

// Test 1: Desktop (1280px) — sidebar expanded
console.log("=== Desktop (1280px) ===");
await page.setViewportSize({ width: 1280, height: 800 });
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(500);
const navWidth = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Sidebar width:", navWidth, "(expect ~192 = w-48)");

// Click hamburger to collapse
await page.click('button[aria-label="Toggle sidebar"]');
await page.waitForTimeout(400);
const navWidth2 = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("After toggle, sidebar width:", navWidth2, "(expect ~56 = w-14)");

// Test 2: Tablet (900px) — sidebar collapsed by default
console.log("\n=== Tablet (900px) ===");
await page.setViewportSize({ width: 900, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
const navWidth3 = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Sidebar width:", navWidth3, "(expect ~56 = collapsed default)");

// Can still expand on tablet
await page.click('button[aria-label="Toggle sidebar"]');
await page.waitForTimeout(400);
const navWidth4 = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("After expand, sidebar width:", navWidth4, "(expect ~192)");

// Test 3: Mobile (500px) — sidebar hidden, hamburger opens overlay
console.log("\n=== Mobile (500px) ===");
await page.setViewportSize({ width: 500, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
const navVisible = await page.locator("nav").isVisible().catch(() => false);
console.log("Sidebar visible initially:", navVisible, "(expect false)");

// Click hamburger to open mobile sidebar
await page.click('button[aria-label="Toggle sidebar"]');
await page.waitForTimeout(400);
const navVisible2 = await page.locator("nav").isVisible();
console.log("Sidebar visible after toggle:", navVisible2, "(expect true)");
const overlayBg = await page.locator(".bg-black\\/50").isVisible();
console.log("Overlay backdrop visible:", overlayBg, "(expect true)");

// Click a tool link should close the overlay
await page.click('a[href="/traceroute"]');
await page.waitForTimeout(400);
const navVisible3 = await page.locator("nav").isVisible().catch(() => false);
console.log("Sidebar after navigating:", navVisible3, "(expect false = closed)");

await browser.close();
console.log("\nDone");
