import { expect, test } from "@playwright/test";

test("runs the full queue, browses finished claims and resets for a new run", async ({
  page,
  request,
}) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await page.getByRole("tab", { name: "Reset", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Reset the pilot" }),
  ).toBeVisible();
  const reset = page.getByRole("button", {
    name: "Reset all claims",
    exact: true,
  });
  await expect(reset).toBeDisabled();
  await page.getByLabel("Type RESET to confirm").fill("RESET");
  await reset.click();
  await expect(
    page.getByText("25 claims returned to waiting.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Queue (25)", exact: true }).click();
  const started = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/queue/run") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run queue", exact: true }).click();
  expect((await started).status()).toBe(202);
  await expect(
    page.getByRole("button", { name: "Queue running", exact: true }),
  ).toBeDisabled();
  await page.getByRole("tab", { name: "Reset", exact: true }).click();
  await expect(reset).toBeDisabled();
  const blocked = await request.post("/api/queue/reset", {
    data: { confirmation: "RESET" },
  });
  expect(blocked.status()).toBe(409);
  await page.getByRole("tab", { name: /Queue \(/ }).click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Queue running", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("Queue run complete", { exact: true }),
  ).toBeVisible({ timeout: 60_000 });
  await expect(
    page.getByText("25 of 25 attempted · 1 failed · 0 skipped", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Queue (2)", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Finished (23)", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Claims" }).getByRole("button"),
  ).toHaveCount(23);
  await expect(
    page.getByRole("heading", { name: "Finished claims", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /CLM-1001/ })).toContainText(
    "approve · $420.00",
  );
  await page.getByRole("button", { name: /CLM-1003/ }).click();
  await expect(
    page.getByRole("region", { name: "Decision", exact: true }),
  ).toContainText("decline");
  await page.screenshot({
    path: test.info().outputPath("finished-desktop.png"),
  });
  await page.getByRole("tab", { name: "Queue (2)", exact: true }).click();
  await page.getByRole("button", { name: /CLM-1002/ }).click();
  await expect(
    page.getByRole("button", { name: "Sign off and pay", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Reset", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.screenshot({
    path: test.info().outputPath("reset-mobile-dark.png"),
  });
  await page.getByLabel("Type RESET to confirm").fill("RESET");
  await reset.click();
  await expect(
    page.getByText("25 claims returned to waiting.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Finished (0)", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Queue (25)", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "Claims" }).getByRole("button"),
  ).toHaveCount(25);
  await page.getByRole("button", { name: "Run queue", exact: true }).click();
  await expect(
    page.getByText("Queue run complete", { exact: true }),
  ).toBeVisible({ timeout: 60_000 });
  await expect(
    page.getByText("25 of 25 attempted · 0 failed · 0 skipped", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Finished (24)", exact: true }),
  ).toBeVisible();
});
