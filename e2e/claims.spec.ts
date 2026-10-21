import { expect, test } from "@playwright/test";

test("shows the seeded queue, complete evidence and the exact read-only instructions", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("navigation", { name: "Claims" }).getByRole("button"),
  ).toHaveCount(25);
  await expect(
    page.getByRole("heading", { name: "The customer's account" }),
  ).toBeVisible();
  await expect(
    page.locator("summary").filter({ hasText: "Hotel receipt" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Hotel Aurelia Fiumicino. Guest: Maya Patel/),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Customer and claim history" }),
  ).toBeVisible();
  await expect(page.getByText("POL-2001", { exact: true })).toBeVisible();
  await page.getByText("Policy wording · 2026.1", { exact: true }).click();
  await expect(page.locator(".wording")).toContainText(
    "## 10. How we work out your payment",
  );
  const response = await request.get("/api/instructions");
  const instructions = (await response.json()) as { text: string };
  await page
    .getByRole("button", { name: "Agent instructions", exact: true })
    .click();
  await expect(page.locator(".instructions pre")).toHaveText(instructions.text);
  await expect(page.getByRole("textbox")).toHaveCount(0);
});

test("approves a normal claim with visible activity and one persisted payment", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Agent working", exact: true }),
  ).toBeDisabled();
  const decision = page.getByRole("region", { name: "Decision", exact: true });
  await expect(decision.getByText(/Simulated payment recorded/)).toBeVisible();
  await expect(decision).toContainText("$420.00");
  await expect(decision).toContainText("Policy sections 3, 10");
  await expect(
    page.getByRole("region", { name: "Agent activity" }),
  ).toContainText("Run finished");
  await page.reload();
  await page.getByRole("tab", { name: /Finished/ }).click();
  await expect(decision.getByText(/Simulated payment recorded/)).toBeVisible();
  const result = (await (await request.get("/api/claims/CLM-1001")).json()) as {
    thread_id: string;
  };
  const duplicate = await request.post("/api/claims/CLM-1001/payment", {
    data: { thread_id: result.thread_id, amount: "420.00" },
  });
  expect(duplicate.status()).toBe(409);
});

test("blocks direct over-limit payment then accepts handler sign-off", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /CLM-1002/ }).click();
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign off and pay", exact: true }),
  ).toBeVisible();
  const result = (await (await request.get("/api/claims/CLM-1002")).json()) as {
    thread_id: string;
    payment: unknown;
  };
  expect(result.payment).toBeNull();
  const blocked = await request.post("/api/claims/CLM-1002/payment", {
    data: { thread_id: result.thread_id, amount: "1250.00" },
  });
  expect(blocked.status()).toBe(409);
  await expect(
    page.getByRole("region", { name: "Agent activity" }),
  ).toContainText("Tool result: HTTP 409");
  await page.getByLabel("Signing handler").selectOption("HND-02");
  await page
    .getByRole("button", { name: "Sign off and pay", exact: true })
    .click();
  const decision = page.getByRole("region", { name: "Decision", exact: true });
  await expect(decision).toContainText("Signed off by Marcus Oyelaran");
  await expect(decision.getByText(/Simulated payment recorded/)).toBeVisible();
  await expect(decision).toContainText("$1,250.00");
});

for (const [id, outcome] of [
  ["CLM-1003", "decline"],
  ["CLM-1004", "refer"],
]) {
  test(`records ${outcome} without a payment`, async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: new RegExp(id) }).click();
    await page.getByRole("button", { name: "Run agent", exact: true }).click();
    const decision = page.getByRole("region", {
      name: "Decision",
      exact: true,
    });
    await expect(decision.locator(".outcome")).toContainText(outcome);
    await expect(decision).toContainText("Policy sections 3, 10");
    await expect(decision.getByText(/Simulated payment/)).toHaveCount(0);
    await expect(decision.getByRole("button")).toHaveCount(0);
  });
}

test("shows a failed run and retries without duplicating work", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /CLM-1005/ }).click();
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Agent activity" }),
  ).toContainText("Run failed:");
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "Decision", exact: true })
      .getByText(/Simulated payment recorded/),
  ).toBeVisible();
});

for (const colorScheme of ["light", "dark"] as const) {
  for (const width of [390, 1440]) {
    test(`supports ${colorScheme} mode at ${String(width)}px without overflow`, async ({
      page,
    }) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.setViewportSize({ width, height: 1000 });
      await page.emulateMedia({ colorScheme });
      await page.goto("/");
      await expect(
        page.getByRole("heading", { name: "Decision", exact: true }),
      ).toBeVisible();
      await page.keyboard.press("Tab");
      await expect(
        page.getByRole("link", { name: /UnderCover/ }),
      ).toBeFocused();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: test.info().outputPath(`${colorScheme}-${String(width)}.png`),
        fullPage: true,
      });
      expect(errors).toEqual([]);
    });
  }
}
