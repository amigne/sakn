import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.on("pageerror", (err) => console.error("PAGE ERROR:", err.message));

await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(1000);

// Debug dev toolbar
console.log("=== Dev Toolbar Debug ===");
const devBtn = page.locator("button", { hasText: "Dev:" });
console.log("Dev button visible:", await devBtn.isVisible());
console.log("Dev button text:", await devBtn.textContent());

await devBtn.click();
await page.waitForTimeout(500);

// Check if dropdown appeared
const body = await page.textContent("body");
console.log("Body after click includes 'Admin':", body?.includes("Admin"));

// List all buttons
const buttons = await page.locator("button").allTextContents();
console.log("All buttons:", buttons);

// Click Admin option using a more specific selector
const adminOption = page.locator("button", { hasText: /^Admin$/ });
console.log("Admin option found:", await adminOption.count());
if (await adminOption.count() > 0) {
  await adminOption.first().click();
  await page.waitForTimeout(500);
  
  const adminSection = page.locator("text=Administration");
  console.log("Admin section visible after click:", await adminSection.isVisible());
}

await page.screenshot({ path: "/tmp/sakn-debug.png", fullPage: true });
console.log("Screenshot saved");

await browser.close();
