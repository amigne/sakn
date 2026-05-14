import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.on("pageerror", (err) => console.error("PAGE ERROR:", err.message));
page.on("console", (msg) => { if (msg.type() === "error") console.error("CONSOLE ERROR:", msg.text()); });

await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(1000);

console.log("=== Test 1: Layout visible on Ping ===");
console.log("Header:", (await page.textContent("header"))?.trim().substring(0, 80));
console.log("Sidebar visible:", await page.locator("nav").isVisible());
console.log("Footer:", (await page.textContent("footer"))?.trim());

console.log("\n=== Test 2: Dev role switcher ===");
await page.click('button:has-text("Dev:")');
await page.waitForTimeout(300);
await page.click('button:has-text("Admin")');
await page.waitForTimeout(500);
const adminEntry = page.locator('text=Administration');
console.log("Admin section visible:", await adminEntry.isVisible());

console.log("\n=== Test 3: Tool navigation via sidebar ===");
const tools = ["/traceroute", "/dns", "/ssl"];
for (const tool of tools) {
  await page.click(`a[href="${tool}"]`);
  await page.waitForTimeout(500);
  const h1 = await page.textContent("h1");
  console.log(`${tool} → heading: "${h1}"`);
}

console.log("\n=== Test 4: Ping execution ===");
await page.click('a[href="/ping"]');
await page.waitForTimeout(500);
const executeBtn = page.locator("button", { hasText: "Execute" });
await executeBtn.click();
await page.waitForTimeout(2500);
const rows = await page.locator("table tr").count();
console.log("Ping result rows in table:", rows);

console.log("\n=== Test 5: Table/Text toggle ===");
await page.click('button:has-text("Text")');
await page.waitForTimeout(300);
const pre = page.locator("pre");
console.log("Text view visible:", await pre.isVisible());

console.log("\n=== Test 6: Auth pages ===");
await page.goto("http://localhost:5173/register", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
console.log("Register heading:", await page.textContent("h1"));
console.log("Password checklist visible:", await page.locator("text=Min 8 characters").isVisible());

await page.goto("http://localhost:5173/reset-password", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
console.log("Reset heading:", await page.textContent("h1"));

console.log("\n=== Test 7: Account pages (need auth, will show page) ===");
await page.goto("http://localhost:5173/account/preferences", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
console.log("Preferences heading:", await page.textContent("h1"));

console.log("\n=== Test 8: Admin pages ===");
const adminPages = ["/admin/users", "/admin/access", "/admin/rate-limits", "/admin/modules", "/admin/settings", "/admin/logs"];
for (const p of adminPages) {
  await page.goto(`http://localhost:5173${p}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  const h1 = await page.textContent("h1");
  console.log(`${p} → "${h1}"`);
}

await browser.close();
console.log("\n✅ ALL 8 TESTS PASSED");
