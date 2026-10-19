import { createHmac } from "node:crypto";
import { expect, test } from "@playwright/test";
import { ADMIN, api, signInStaff, token, unique } from "./helpers.js";

/** RFC 6238 code for a base32 secret, `steps` periods from now. */
function totp(secret, steps = 0) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/=+$/, "")) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000) + steps));
  const hmac = createHmac("sha1", key).update(counter).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  return String((hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

test("staff member turns on two-step sign-in, then needs a code; an admin resets it", async ({ page, browser }) => {
  const admin = await token("admin", "admin123");
  const username = `e2e.mfa${unique()}`;
  const user = await api("/api/users", { token: admin, method: "POST",
    body: { username, password: "Clinic-Pass-2026", role: "admin", display_name: "E2E Two Step" } });

  await signInStaff(page, username, "Clinic-Pass-2026");
  await page.getByRole("button", { name: "My account" }).click();
  await page.getByRole("button", { name: "Set up two-step sign-in" }).click();
  await expect(page.getByRole("img", { name: "QR code for your authenticator app" })).toBeVisible();
  const secret = (await page.locator("p.mono.break").innerText()).trim();
  await page.getByLabel("Code from the app").fill(totp(secret));
  await page.getByRole("button", { name: "Turn on" }).click();
  await expect(page.getByText("Two-step sign-in is on.")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();

  // Password alone is no longer enough in the staff app...
  await signInStaff(page, username, "Clinic-Pass-2026");
  await expect(page.getByLabel("Authentication code")).toBeVisible();
  await page.getByLabel("Authentication code").fill("000000");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByText("That code isn't right.")).toBeVisible();
  await page.getByLabel("Authentication code").fill(totp(secret, 1));
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();

  // ...nor in the admin console.
  const consolePage = await (await browser.newContext()).newPage();
  await consolePage.goto(`${ADMIN}/login`);
  await consolePage.getByLabel("Staff ID").fill(username);
  await consolePage.getByLabel("Password").fill("Clinic-Pass-2026");
  await consolePage.getByRole("button", { name: "Sign in" }).click();
  await expect(consolePage.getByRole("heading", { name: "Two-step sign-in" })).toBeVisible();
  await expect.poll(() => Math.floor(Date.now() / 30000), { timeout: 35_000, intervals: [1000] })
    .toBeGreaterThan(Math.floor(Date.now() / 30000)); // codes are single-use: wait for a fresh one
  await consolePage.getByLabel("Authentication code").fill(totp(secret, 1));
  await consolePage.getByRole("button", { name: "Verify" }).click();
  await expect(consolePage.getByRole("heading", { name: "Overview" })).toBeVisible();

  // Lost phone: an admin resets it and the password works on its own again.
  expect(await api(`/api/users/${user.id}/reset-mfa`, { token: admin, method: "POST" })).toEqual({ reset: true });
  const fresh = await api("/api/auth/login", { method: "POST", body: { unique_id: username, password: "Clinic-Pass-2026" } });
  expect(fresh.access).toBeTruthy();
});
