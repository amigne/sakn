import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.on("pageerror", (err) => console.error("PAGE ERROR:", err.message));
page.on("console", (msg) => { if (msg.type() === "error") console.error("CONSOLE ERROR:", msg.text()); });

console.log("╔══════════════════════════════════════╗");
console.log("║   SAKN S2 —  Acceptance Tests       ║");
console.log("╚══════════════════════════════════════╝\n");

let failures = 0;
function check(name, ok, detail) {
  if (ok) console.log(`  ✅ ${name}${detail ? ": " + detail : ""}`);
  else { console.log(`  ❌ ${name}${detail ? ": " + detail : ""}`); failures++; }
}

// ── 1. Layout ──
console.log("1. Layout & Navigation");
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(800);

check("Page title", await page.title() === "SAKN — Network Diagnostic Tools");
check("Header visible", await page.locator("header").isVisible());
check("Header has SAKN", (await page.textContent("header"))?.includes("SAKN"));
check("Sidebar visible", await page.locator("nav").isVisible());
check("Sidebar has Ping", (await page.textContent("nav"))?.includes("Ping"));
check("Sidebar has Traceroute", (await page.textContent("nav"))?.includes("Traceroute"));
check("Sidebar has DNS", (await page.textContent("nav"))?.includes("DNS"));
check("Sidebar has TLS", (await page.textContent("nav"))?.includes("TLS"));
check("Footer visible", await page.locator("footer").isVisible());
check("Footer version", (await page.textContent("footer"))?.includes("v0.0.1"));
check("Ping page heading", await page.textContent("h1") === "Ping");

// ── 2. Tool pages ──
console.log("\n2. Tool Pages");
for (const [label, route, expected] of [
  ["Traceroute", "/traceroute", "Traceroute"],
  ["DNS Lookup", "/dns", "DNS Lookup"],
  ["TLS/SSL", "/ssl", "TLS/SSL Certificate Viewer"],
]) {
  await page.click(`a[href="${route}"]`);
  await page.waitForTimeout(400);
  const h1 = await page.textContent("h1");
  check(`${label} page`, h1 === expected, h1);
}

// ── 3. Ping execution ──
console.log("\n3. Tool Execution (Ping)");
await page.click('a[href="/ping"]');
await page.waitForTimeout(400);
const execBtn = page.locator("button", { hasText: "Execute" });
check("Execute button visible", await execBtn.isVisible());
await execBtn.click();
await page.waitForTimeout(3000);
const rows = await page.locator("table tr").count();
check("Results in table", rows > 5, `${rows} rows`);
const body = await page.textContent("body");
check("Summary rendered", body?.includes("Summary"), body?.includes("Summary") ? "found" : "missing");

// Table/Text toggle
await page.click('button:has-text("Text")');
await page.waitForTimeout(300);
const pres = await page.locator("pre").count();
check("Text view has content", pres > 0, `${pres} pre blocks`);

// ── 4. Auth pages ──
console.log("\n4. Auth Pages");
await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
check("Login page", await page.textContent("h1") === "Sign In");
check("Forgot password link", (await page.textContent("body"))?.includes("Forgot password?"));
check("Sign up link", (await page.textContent("body"))?.includes("Sign up"));

await page.goto("http://localhost:5173/register", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
check("Register page", await page.textContent("h1") === "Create Account");
check("Password checklist", (await page.textContent("body"))?.includes("Min 8 characters"));

await page.goto("http://localhost:5173/reset-password", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
check("Reset password page", await page.textContent("h1") === "Reset Password");

await page.goto("http://localhost:5173/verify-email-sent", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
check("Verify email sent page", (await page.textContent("body"))?.includes("Check Your Email"));

// ── 5. Account pages ──
console.log("\n5. Account Pages");
await page.goto("http://localhost:5173/account/preferences", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
check("Preferences page", await page.textContent("h1") === "Preferences");
check("Theme options visible", (await page.textContent("body"))?.includes("Light") && (await page.textContent("body"))?.includes("Dark"));

await page.goto("http://localhost:5173/account/sessions", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
check("Sessions page", await page.textContent("h1") === "Active Sessions");

await page.goto("http://localhost:5173/account/delete", { waitUntil: "networkidle" });
await page.waitForTimeout(300);
check("Delete account page", await page.textContent("h1") === "Delete Account");

// ── 6. Dev toolbar & admin ──
console.log("\n6. Admin (via Dev Toolbar)");
await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForTimeout(500);
// Activate admin role
await page.click('button:has-text("Dev:")');
await page.waitForTimeout(200);
await page.click('button:has-text(/^Admin$/)');
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

// ── 7. Dev toolbar: visitor mode ──
console.log("\n7. Visitor Mode");
await page.click('button:has-text("Dev:")');
await page.waitForTimeout(200);
await page.click('button:has-text("Visitor")');
await page.waitForTimeout(500);
check("Admin hidden for visitor", !(await page.textContent("nav"))?.includes("Administration"));
check("Sign In visible", (await page.textContent("header"))?.includes("Sign In"));

// ── Summary ──
console.log(`\n${'═'.repeat(40)}`);
if (failures === 0) {
  console.log("🎉 ALL TESTS PASSED");
} else {
  console.log(`⚠️  ${failures} TEST(S) FAILED`);
}

await browser.close();
