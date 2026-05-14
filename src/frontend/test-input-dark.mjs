import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(800);

// Switch to dark mode
const themeBtn = page.locator('button[aria-label*="Theme"]');
await themeBtn.click();
await themeBtn.click();
await page.waitForTimeout(300);

const isDark = await page.evaluate(() => document.documentElement.classList.contains("dark"));
console.log("html.dark:", isDark);

// Check color-scheme on number input
const countInput = page.locator('input[type="number"]').first();
const colorScheme = await countInput.evaluate(el => getComputedStyle(el).colorScheme);
console.log("Number input color-scheme:", colorScheme);

const bg = await countInput.evaluate(el => getComputedStyle(el).backgroundColor);
console.log("Number input background:", bg);

await browser.close();
