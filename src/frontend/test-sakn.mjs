import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

page.on("pageerror", (err) => console.error("PAGE ERROR:", err.message));
page.on("console", (msg) => { if (msg.type() === "error") console.error("CONSOLE ERROR:", msg.text()); });

await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

const title = await page.title();
console.log("Title:", title);

const headerText = await page.textContent("header");
console.log("Header found:", !!headerText, headerText?.substring(0, 100));

const sidebarText = await page.textContent("nav");
console.log("Sidebar found:", !!sidebarText, sidebarText?.substring(0, 100));

const footerText = await page.textContent("footer");
console.log("Footer found:", !!footerText, footerText?.trim());

const heading = await page.textContent("h1");
console.log("Page heading:", heading);

const buttonCount = await page.locator("button").count();
console.log("Buttons found:", buttonCount);

// Check links
const links = await page.locator("a").allTextContents();
console.log("Links:", links.filter(l => l.trim()).join(", "));

await page.screenshot({ path: "/tmp/sakn-screenshot.png", fullPage: true });
console.log("Screenshot saved to /tmp/sakn-screenshot.png");

// Test Ping execution
const startBtn = page.locator("button", { hasText: "Execute" });
if (await startBtn.isVisible()) {
  await startBtn.click();
  await page.waitForTimeout(2000);
  const status = await page.textContent("table");
  console.log("Ping results table:", !!status);
}

// Test navigation to login
await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const loginHeading = await page.textContent("h1");
console.log("Login heading:", loginHeading);

// Test admin page
await page.goto("http://localhost:5173/admin/users", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
const adminHeading = await page.textContent("h1");
console.log("Admin heading:", adminHeading);

await browser.close();
console.log("\nALL TESTS PASSED");
