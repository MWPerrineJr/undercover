import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { approved, mockBackend } from "../tests/backend";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("separates finished claims from sign-off-pending claims and opens their evidence", async () => {
  const { second } = mockBackend(approved);
  Object.assign(second, {
    ...approved,
    status: "decided",
    payment: { amount: "1250" },
  });
  render(<App />);
  expect(await screen.findByRole("tab", { name: "Queue (1)" })).toBeDefined();
  expect(screen.queryByRole("button", { name: /CLM-1002/ })).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "Finished (1)" }));
  expect(
    await screen.findByRole("heading", { name: "Lost baggage" }),
  ).toBeDefined();
  expect(
    screen.getByRole("button", { name: /CLM-1002/ }).textContent,
  ).toContain("approve · $1,250.00");
  expect(screen.queryByRole("button", { name: /CLM-1001/ })).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "Queue (1)" }));
  expect(
    await screen.findByRole("button", { name: "Sign off and pay" }),
  ).toBeDefined();
});

it("shows the empty finished tab and supports arrow, home and end navigation", async () => {
  mockBackend();
  render(<App />);
  const queue = await screen.findByRole("tab", { name: "Queue (2)" });
  fireEvent.keyDown(queue, { key: "ArrowRight" });
  expect(await screen.findByText("No finished claims yet.")).toBeDefined();
  expect(document.activeElement).toBe(
    screen.getByRole("tab", { name: "Finished (0)" }),
  );
  fireEvent.keyDown(document.activeElement ?? queue, { key: "End" });
  expect(
    screen.getByRole("heading", { name: "Reset the pilot" }),
  ).toBeDefined();
  fireEvent.keyDown(screen.getByRole("tab", { name: "Reset" }), {
    key: "Home",
  });
  expect(
    screen
      .getByRole("tab", { name: "Queue (2)" })
      .getAttribute("aria-selected"),
  ).toBe("true");
  fireEvent.keyDown(queue, { key: "ArrowLeft" });
  expect(
    screen.getByRole("heading", { name: "Reset the pilot" }),
  ).toBeDefined();
  fireEvent.keyDown(screen.getByRole("tab", { name: "Reset" }), {
    key: "Escape",
  });
  expect(
    screen.getByRole("heading", { name: "Reset the pilot" }),
  ).toBeDefined();
});

it("retries a queue-start error, polls progress and stops once all attempts finish", async () => {
  const { claim, progress, fetcher } = mockBackend();
  render(<App />);
  const run = await screen.findByRole("button", { name: "Run queue" });
  await waitFor(() => {
    expect(run).toHaveProperty("disabled", false);
  });
  fetcher.mockResolvedValueOnce(new Response("{}", { status: 409 }));
  fireEvent.click(run);
  expect(await screen.findByRole("alert")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Run queue" }));
  expect(
    await screen.findByRole("button", { name: "Queue running" }),
  ).toHaveProperty("disabled", true);
  expect(screen.getByText(/0 of 2 attempted/)).toBeDefined();
  Object.assign(progress, {
    running: false,
    processed: 2,
    failed: 1,
    skipped: 1,
    current_claim_id: null,
    message: "Queue run complete",
  });
  claim.running = false;
  expect(
    await screen.findByText("Queue run complete", {}, { timeout: 2500 }),
  ).toBeDefined();
  expect(
    screen.getByText(/2 of 2 attempted · 1 failed · 1 skipped/),
  ).toBeDefined();
  const calls = fetcher.mock.calls.length;
  await act(async () => {
    await new Promise((resolve) => {
      setTimeout(resolve, 1200);
    });
  });
  expect(fetcher.mock.calls).toHaveLength(calls);
});

it("loads persisted active queue progress even between individual claims", async () => {
  const { progress } = mockBackend();
  Object.assign(progress, { running: true, total: 2, processed: 1 });
  render(<App />);
  expect(
    await screen.findByRole("button", { name: "Queue running" }),
  ).toHaveProperty("disabled", true);
  expect(screen.getByText(/1 of 2 attempted/)).toBeDefined();
  fireEvent.click(screen.getByRole("tab", { name: "Reset" }));
  expect(
    await screen.findByRole("button", { name: "Reset all claims" }),
  ).toHaveProperty("disabled", true);
});
