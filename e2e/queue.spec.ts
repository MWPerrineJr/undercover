import { expect, test } from "@playwright/test";

test("plans a capped run, ticks the to-do list off and leaves the rest waiting", async ({
  page,
  request,
}) => {
  test.setTimeout(90_000);
  await page.goto("/");
  await page.getByRole("tab", { name: "Reset", exact: true }).click();
  const reset = page.getByRole("button", {
    name: "Reset all claims",
    exact: true,
  });
  await page.getByLabel("Type RESET to confirm").fill("RESET");
  await reset.click();
  await expect(
    page.getByText("25 claims returned to waiting.", { exact: true }),
  ).toBeVisible();

  await page.getByRole("tab", { name: "Queue (25)", exact: true }).click();
  await page.getByLabel("Claims in this run").fill("4");
  const started = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/queue/run") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run queue", exact: true }).click();
  expect((await started).status()).toBe(202);
  const todos = page.getByRole("region", { name: "The agent's to-do list" });
  await expect(todos.getByRole("listitem")).toHaveCount(4, { timeout: 20_000 });
  await expect(todos.getByText("in progress")).toHaveCount(1);

  const blocked = await request.post("/api/queue/reset", {
    data: { confirmation: "RESET" },
  });
  expect(blocked.status()).toBe(409);

  await page.reload();
  await expect(page.getByText("Worked 4 claims.", { exact: true })).toBeVisible(
    {
      timeout: 60_000,
    },
  );
  await expect(todos.getByText("done")).toHaveCount(4);
  await expect(todos.getByText("CLM-1003 worked")).toBeVisible();
  await expect(
    page.getByText("4 of 4 done · 0 left for a handler"),
  ).toBeVisible();

  await expect(
    page.getByRole("tab", { name: "Finished (3)", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Queue (22)", exact: true }).click();
  await page.getByRole("button", { name: /CLM-1002/ }).click();
  await expect(
    page.getByRole("button", { name: "Sign off and pay", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("queue-desktop.png"),
  });

  await page.getByRole("tab", { name: "Finished (3)", exact: true }).click();
  await page.getByRole("button", { name: /CLM-1003/ }).click();
  await expect(
    page.getByRole("region", { name: "Decision", exact: true }),
  ).toContainText("decline");
  await expect(page.getByText(/Manual sections/)).toBeVisible();
});
