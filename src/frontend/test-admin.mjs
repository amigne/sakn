import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.on("pageerror", (err) => console.error("PAGE ERROR:", err.message));

let failures = 0;
function check(name, ok, detail) {
  if (ok) console.log(`  ✅ ${name}${detail ? ": " + detail : ""}`);
  else { console.log(`  ❌ ${name}${detail ? ": " + detail : ""}`); failures++; }
}

console.log("6. Admin (via Dev Toolbar)");
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(500);

// Click the dev toolbar button to open dropdown
await page.click("button:has-text('Dev:')");
await page.waitForTimeout(300);

// Click the Admin option (exact match)
const buttons = await page.locator("button").allTextContents();
console.log("Buttons:", buttons.filter(b => ["Live","Visitor","User","Admin"].includes(b.trim())));

await page.click("button:has-text('Admin')");
await page.waitForTimeout(500);
check("Admin section in sidebar", (await page.textContent("nav"))?.includes("Administration"));

const adminPages = [
  ["/admin/users", "User Management"],
  ["/admin/access", "Access Rights"],
  ["/admin/rate-limits", "Rate Limits"],
  ["/admin/modules", "Module Activation"],
  ["/admin/settings", "Global Settings"],
  ["/admin/logs", "Log Viewer"],
];
for (const [route, expected] of adminPages) {
  await page.goto(`http://localhost:5173${route}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  const h1 = await page.textContent("h1");
  check(`Admin: ${route}`, h1 === expected, h1);
}

// Visitor mode
console.log("\n7. Visitor Mode");
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
await page.click("button:has-text('Dev:')");
await page.waitForTimeout(200);
await page.click("button:has-text('Visitor')");
await page.waitForTimeout(500);
check("Admin hidden for visitor", !(await page.textContent("nav"))?.includes("Administration"));
check("Sign In visible", (await page.textContent("header"))?.includes("Sign In"));

console.log(`\n${failures === 0 ? "✅ ALL ADMIN TESTS PASSED" : `❌ ${failures} FAILURES`}`);
await browser.close();
