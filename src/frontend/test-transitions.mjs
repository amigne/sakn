import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

// Tablet → Mobile
console.log("=== Tablet → Mobile ===");
await page.setViewportSize({ width: 900, height: 800 });
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(500);
let navVisible = await page.locator("nav").isVisible();
let headerHam = await page.locator("header button[aria-label='Toggle sidebar']").count();
console.log("Tablet: nav visible:", navVisible, "header hamburger:", headerHam);

await page.setViewportSize({ width: 500, height: 800 });
await page.waitForTimeout(600);
navVisible = await page.locator("nav").isVisible().catch(() => false);
headerHam = await page.locator("header button[aria-label='Toggle sidebar']").count();
console.log("Mobile: nav visible:", navVisible, "(expect false)");
console.log("Mobile: header hamburger:", headerHam, "(expect 1)");
const mbOverlay = await page.locator(".bg-black\\/50").isVisible().catch(() => false);
console.log("Mobile: overlay:", mbOverlay, "(expect false)");
console.log("Transition clean:", !navVisible && headerHam === 1 && !mbOverlay ? "OK" : "FAIL");

// Mobile → Tablet  
console.log("\n=== Mobile → Tablet ===");
await page.setViewportSize({ width: 500, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
// Open mobile sidebar first
await page.click("header button[aria-label='Toggle sidebar']");
await page.waitForTimeout(300);
let mobileNavOpen = await page.locator("nav").isVisible();
console.log("Mobile: sidebar open:", mobileNavOpen);

await page.setViewportSize({ width: 900, height: 800 });
await page.waitForTimeout(600);
navVisible = await page.locator("nav").isVisible();
headerHam = await page.locator("header button[aria-label='Toggle sidebar']").count();
const navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Tablet: nav visible:", navVisible, "width:", navW, "(expect 56 = collapsed)");
console.log("Tablet: header hamburger:", headerHam, "(expect 0)");
const hamInNav = await page.locator("nav button[aria-label='Toggle sidebar']").count();
console.log("Tablet: hamburger in nav:", hamInNav, "(expect 1)");
console.log("Transition clean:", navVisible && navW < 100 && headerHam === 0 && hamInNav === 1 ? "OK" : "FAIL");

await browser.close();
