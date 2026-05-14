import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(800);

const themeBtn = page.locator('button[aria-label*="Theme"]');
console.log("Theme button aria-label:", await themeBtn.getAttribute("aria-label"));
console.log("Initial html.dark:", await page.evaluate(() => document.documentElement.classList.contains("dark")));

// Click once: system → light
await themeBtn.click();
await page.waitForTimeout(300);
console.log("After click 1, aria-label:", await themeBtn.getAttribute("aria-label"));
console.log("After click 1, html.dark:", await page.evaluate(() => document.documentElement.classList.contains("dark")));

// Click twice: light → dark
await themeBtn.click();
await page.waitForTimeout(300);
console.log("After click 2, aria-label:", await themeBtn.getAttribute("aria-label"));
console.log("After click 2, html.dark:", await page.evaluate(() => document.documentElement.classList.contains("dark")));

const card = page.locator(".card").first();
const darkBg = await card.evaluate(el => getComputedStyle(el).backgroundColor);
console.log("Dark mode card bg:", darkBg);

await browser.close();
