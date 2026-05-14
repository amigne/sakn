import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(800);

// Check card background in light mode
const card = page.locator(".card").first();
const lightBg = await card.evaluate(el => getComputedStyle(el).backgroundColor);
console.log("Light mode card bg:", lightBg);

// Switch to dark mode
await page.click('button[aria-label*="Theme"]');
await page.waitForTimeout(500);
const darkBg = await card.evaluate(el => getComputedStyle(el).backgroundColor);
console.log("Dark mode card bg:", darkBg);

// Check if html has dark class
const hasDark = await page.evaluate(() => document.documentElement.classList.contains("dark"));
console.log("html.dark:", hasDark);

await browser.close();
