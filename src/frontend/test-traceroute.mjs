import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto("http://localhost:5173/traceroute", { waitUntil: "networkidle" });
await page.waitForTimeout(800);

// Start a test with 3 probes
await page.click('button:has-text("Trace")');
await page.waitForTimeout(3000);

// Count probe columns in table header
const headers = await page.locator("th").allTextContents();
console.log("Headers during test:", headers);

// Change probes to 5 while test is running (but it's done)
const probesInput = page.locator('input[type="number"]').nth(2);
await probesInput.fill("5");
await page.waitForTimeout(500);

// Check headers again - should still show 3 probes (captured at start)
const headersAfter = await page.locator("th").allTextContents();
console.log("Headers after changing input:", headersAfter);

// Now start a new test
await page.click('button:has-text("Reset")');
await page.waitForTimeout(300);
await page.click('button:has-text("Trace")');
await page.waitForTimeout(3000);

const headersNew = await page.locator("th").allTextContents();
console.log("Headers for new test with 5 probes:", headersNew);

await browser.close();
