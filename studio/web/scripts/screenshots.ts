/**
 * Captures the screenshots used in the README and on the project page.
 *   npx vite build --mode pages --outDir dist-pages && python -m http.server 8794 -d dist-pages
 *   npx tsx scripts/screenshots.ts [http://localhost:8794/]
 * Uses an installed Edge or Chrome through playwright-core; nothing is downloaded.
 */
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { chromium, type Page } from "playwright-core";

const BASE = process.argv[2] ?? "http://localhost:8794/";
const OUT = resolve(import.meta.dirname, "../../../docs/assets/studio");
mkdirSync(OUT, { recursive: true });

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
async function shot(page: Page, name: string, opts: { fullPage?: boolean; clip?: { x: number; y: number; width: number; height: number } } = {}) {
  await wait(700);
  await page.screenshot({ path: resolve(OUT, `${name}.png`), ...opts });
  console.log("  ", name);
}
const nav = async (page: Page, label: string) => {
  await page.getByRole("link", { name: label, exact: true }).first().click();
  await wait(900);
};

const browser = await chromium.launch({ channel: "msedge" }).catch(() => chromium.launch({ channel: "chrome" }));
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: "dark", reducedMotion: "no-preference" });
const page = await ctx.newPage();

// 1. landing: the live hero
await page.goto(BASE);
await wait(9000);
await shot(page, "landing");

// 2. lab: Guardian preset, played to the end
await page.goto(`${BASE}#/lab`);
await wait(800);
await page.getByRole("combobox", { name: "Preset" }).click();
await page.getByRole("option", { name: /Guardian with downranking/ }).click();
await page.getByRole("button", { name: /Run with counterfactual twins/ }).click();
await wait(2000);
await page.getByRole("button", { name: "Pause" }).click().catch(() => {});
for (let i = 0; i < 9; i++) await page.getByRole("button", { name: "Next round" }).click();
await wait(1500);
await shot(page, "lab");
await page.getByRole("tab", { name: "Labelled" }).click();
await shot(page, "lab_moderation");

// 3. counterfactuals: fork the attacked twin, timing curve; tall viewport (the page scrolls inside main)
await page.getByRole("tab", { name: "Attacked" }).click();
await nav(page, "Counterfactuals");
await page.getByRole("button", { name: "Branch" }).click();
await page.getByRole("button", { name: /Run \d+ simulations/ }).click();
await wait(5000);
await page.setViewportSize({ width: 1440, height: 1900 });
await wait(1200);
await shot(page, "counterfactuals", { clip: { x: 0, y: 0, width: 1440, height: 1490 } });
await page.setViewportSize({ width: 1440, height: 900 });

// 4. sweeps
await nav(page, "Sweeps");
await page.getByRole("button", { name: "Run sweep" }).click();
await wait(6000);
await shot(page, "sweeps");

// 5. cascade: a 120-agent engagement-ranked society at its last round
await nav(page, "Lab");
await page.getByRole("combobox", { name: "Preset" }).click();
await page.getByRole("option", { name: /Engagement-ranked feed/ }).click();
await page.getByRole("button", { name: /Run with counterfactual twins/ }).click();
await wait(1500);
await page.getByRole("button", { name: "Pause" }).click().catch(() => {});
for (let i = 0; i < 16; i++) await page.getByRole("button", { name: "Next round" }).click();
await page.getByRole("tab", { name: "Cascade" }).click();
await wait(1200);
await shot(page, "cascade");

// 6. the feed with each agent's belief-desire-intention trace, then one agent across the twins
await nav(page, "Lab");
await page.getByRole("combobox", { name: "Preset" }).click();
await page.getByRole("option", { name: /Prebunking from round 1/ }).click();
await page.getByRole("button", { name: /Run with counterfactual twins/ }).click();
await wait(1500);
await page.getByRole("button", { name: "Pause" }).click().catch(() => {});
await page.getByRole("tab", { name: "Attacked" }).click();
for (let i = 0; i < 6; i++) await page.getByRole("button", { name: "Next round" }).click();
await page.getByRole("tab", { name: "Feed" }).click();
await wait(1000);
const honest = page.locator("article").filter({ hasNot: page.getByText("operation", { exact: true }) });
await page.locator("article").first().getByRole("button", { name: "Reasoning" }).click();
await honest.nth(0).getByRole("button", { name: "Reasoning" }).click();
await wait(600);
await shot(page, "feed_reasoning");
await honest.nth(0).locator("button.font-semibold").click();
await wait(1000);
await shot(page, "agent_inspector");
await page.getByRole("tab", { name: "Log" }).click();
await page.getByRole("button", { name: "Save" }).click();
await wait(1500);

// 7. command palette
await page.keyboard.press("Control+k");
await wait(500);
await page.keyboard.type("pre");
await shot(page, "command_palette");
await page.keyboard.press("Escape");

// 8. library, settings, method
await nav(page, "Library");
await shot(page, "library");
await page.getByRole("link", { name: "Settings", exact: true }).click();
await wait(900);
await shot(page, "settings");
await nav(page, "Method");
await shot(page, "method");

// 9. phone
const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
const pp = await phone.newPage();
await pp.goto(BASE);
await wait(7000);
await pp.screenshot({ path: resolve(OUT, "phone.png") });
console.log("   phone");

await browser.close();
