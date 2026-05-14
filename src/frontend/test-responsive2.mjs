import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

// Test 1: Desktop — hamburger in sidebar, not in header
console.log("=== 1. Desktop: hamburger in sidebar ===");
await page.setViewportSize({ width: 1280, height: 800 });
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(500);
const headerBtns = await page.locator("header button[aria-label='Toggle sidebar']").count();
const sidebarBtns = await page.locator("nav button[aria-label='Toggle sidebar']").count();
console.log("Hamburger in header:", headerBtns, "(expect 0)");
console.log("Hamburger in sidebar:", sidebarBtns, "(expect 1)");

// Test 2: Tablet, expand, resize within tablet → stays expanded
console.log("\n=== 2. Tablet: resize within breakpoint ===");
await page.setViewportSize({ width: 900, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
let navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Tablet default width:", navW, "(expect 56 = collapsed)");

// Expand
await page.locator("nav button[aria-label='Toggle sidebar']").click();
await page.waitForTimeout(400);
navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("After expand:", navW, "(expect 192)");

// Resize within tablet range
await page.setViewportSize({ width: 850, height: 800 });
await page.waitForTimeout(400);
navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("After resize to 850px:", navW, "(expect 192 = stays expanded)");

// Test 3: Tablet → Desktop transition auto-expands
console.log("\n=== 3. Tablet → Desktop: auto-expand ===");
await page.setViewportSize({ width: 900, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Tablet default:", navW, "(expect 56 = collapsed)");

await page.setViewportSize({ width: 1280, height: 800 });
await page.waitForTimeout(500);
navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Desktop after transition:", navW, "(expect 192 = auto-expanded)");

// Test 4: Desktop → Tablet transition auto-collapses
console.log("\n=== 4. Desktop → Tablet: auto-collapse ===");
await page.setViewportSize({ width: 1280, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Desktop default:", navW, "(expect 192)");

await page.setViewportSize({ width: 900, height: 800 });
await page.waitForTimeout(500);
navW = await page.locator("nav").evaluate(el => el.offsetWidth);
console.log("Tablet after transition:", navW, "(expect 56 = auto-collapsed)");

// Test 5: Mobile — hamburger in header
console.log("\n=== 5. Mobile: hamburger in header ===");
await page.setViewportSize({ width: 500, height: 800 });
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(500);
const headerBtnsMob = await page.locator("header button[aria-label='Toggle sidebar']").count();
console.log("Hamburger in header:", headerBtnsMob, "(expect 1)");
const mobileNav = await page.locator("nav").isVisible().catch(() => false);
console.log("Sidebar visible:", mobileNav, "(expect false)");

// Open mobile sidebar
await page.click("header button[aria-label='Toggle sidebar']");
await page.waitForTimeout(400);
const mobileNav2 = await page.locator("nav").isVisible();
console.log("Sidebar after toggle:", mobileNav2, "(expect true)");

await browser.close();
