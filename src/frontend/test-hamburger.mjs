import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

// Desktop: hamburger in sidebar, left-aligned, with "Minimize menu" label
console.log("=== Desktop ===");
await page.setViewportSize({ width: 1280, height: 800 });
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(500);
const sidebarText = await page.locator("nav").textContent();
console.log("Sidebar has 'Minimize menu':", sidebarText.includes("Minimize menu"));
console.log("Header hamburger count:", await page.locator("header button[aria-label='Toggle sidebar']").count(), "(expect 0)");

// Tablet: same, hamburger in sidebar
console.log("\n=== Tablet ===");
await page.setViewportSize({ width: 900, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
console.log("Sidebar hamburger count:", await page.locator("nav button[aria-label='Toggle sidebar']").count(), "(expect 1)");
console.log("Header hamburger count:", await page.locator("header button[aria-label='Toggle sidebar']").count(), "(expect 0)");

// Mobile: hamburger only in header
console.log("\n=== Mobile ===");
await page.setViewportSize({ width: 500, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
console.log("Header hamburger count:", await page.locator("header button[aria-label='Toggle sidebar']").count(), "(expect 1)");

// Open mobile sidebar — no hamburger inside it
await page.click("header button[aria-label='Toggle sidebar']");
await page.waitForTimeout(400);
const mobileNavHasToggle = await page.locator("nav button[aria-label='Toggle sidebar']").count();
console.log("Mobile sidebar has hamburger:", mobileNavHasToggle, "(expect 0)");
console.log("Mobile sidebar visible:", await page.locator("nav").isVisible());

await browser.close();
