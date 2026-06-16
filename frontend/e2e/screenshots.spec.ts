import { test, expect } from "@playwright/test";

test("dashboard renders with 3D background and health stats", async ({ page }) => {
  test.setTimeout(30000);
  await page.goto("http://localhost:3000");
  await page.waitForSelector("text=ClinicalSafe NIM", { timeout: 20000 });
  await expect(page.locator("h2:has-text('Clinical narratives')")).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/dashboard.png", fullPage: true });
});

test("keys page renders", async ({ page }) => {
  test.setTimeout(30000);
  await page.goto("http://localhost:3000/keys");
  await page.waitForSelector("text=Add NVIDIA API Key", { timeout: 20000 });
  await page.screenshot({ path: "e2e/screenshots/keys.png", fullPage: true });
});

test("summarize page renders", async ({ page }) => {
  test.setTimeout(30000);
  await page.goto("http://localhost:3000/summarize");
  await page.waitForSelector("text=Clinical Safety Table", { timeout: 20000 });
  await page.screenshot({ path: "e2e/screenshots/summarize.png", fullPage: true });
});

test("summarize end-to-end through UI", async ({ page }) => {
  test.setTimeout(90000);
  await page.goto("http://localhost:3000/summarize");
  await page.waitForSelector("button:has-text('Summarize with NIM')", { timeout: 10000 });
  await page.click("button:has-text('Summarize with NIM')");
  await page.waitForSelector("text=NIM Summary", { timeout: 75000 });
  await expect(page.locator("text=Verified").first()).toBeVisible();
  await page.screenshot({ path: "e2e/screenshots/summarize-result.png", fullPage: true });
});
