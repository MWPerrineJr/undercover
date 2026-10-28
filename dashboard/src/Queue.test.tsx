import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
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

it("retries a queue-start error, shows the to-do list and stops polling at the end", async () => {
  const { claim, progress, fetcher } = mockBackend();
  render(<App />);
  const run = await screen.findByRole("button", { name: "Run queue" });
  await waitFor(() => {
    expect(run).toHaveProperty("disabled", false);
  });
  fireEvent.change(screen.getByLabelText("Claims in this run"), {
    target: { value: "2" },
  });
  fetcher.mockResolvedValueOnce(new Response("{}", { status: 409 }));
  fireEvent.click(run);
  expect(await screen.findByRole("alert")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Run queue" }));
  expect(
    await screen.findByRole("button", { name: "Queue running" }),
  ).toHaveProperty("disabled", true);
  expect(
    fetcher.mock.calls.some(
      ([path, init]) =>
        path === "/api/queue/run" && init?.body === JSON.stringify({ cap: 2 }),
    ),
  ).toBe(true);
  const todos = screen.getByRole("region", {
    name: "The agent's to-do list",
  });
  expect(await within(todos).findByText("Rome flight canceled")).toBeDefined();
  expect(within(todos).getByText("in progress")).toBeDefined();
  expect(screen.getByText(/0 of 2 done/)).toBeDefined();
  Object.assign(progress, {
    status: "finished",
    summary: "Worked 2 claims: one approved, one referred.",
    worked: 2,
    todos: [
      {
        claim_id: "CLM-1001",
        title: "Rome flight canceled",
        state: "done",
        note: "CLM-1001 approve $420.00 paid",
      },
      {
        claim_id: "CLM-1002",
        title: "Lost baggage in Lisbon",
        state: "left_for_handler",
        note: "Failed twice",
      },
    ],
  });
  claim.running = false;
  expect(
    await screen.findByText(
      "Worked 2 claims: one approved, one referred.",
      {},
      { timeout: 2500 },
    ),
  ).toBeDefined();
  expect(screen.getByText("CLM-1001 approve $420.00 paid")).toBeDefined();
  expect(screen.getByText("left for a handler")).toBeDefined();
  expect(screen.getByText(/1 of 2 done · 1 left for a handler/)).toBeDefined();
  const calls = fetcher.mock.calls.length;
  await act(async () => {
    await new Promise((resolve) => {
      setTimeout(resolve, 1200);
    });
  });
  expect(fetcher.mock.calls).toHaveLength(calls);
});

it("loads a run that is already under way", async () => {
  const { progress } = mockBackend();
  Object.assign(progress, {
    run_id: "run-1",
    cap: 2,
    worked: 1,
    status: "running",
    todos: [
      {
        claim_id: "CLM-1001",
        title: "Rome flight canceled",
        state: "in_progress",
        note: null,
      },
    ],
  });
  render(<App />);
  expect(
    await screen.findByRole("button", { name: "Queue running" }),
  ).toHaveProperty("disabled", true);
  expect(screen.getByLabelText("Claims in this run")).toHaveProperty(
    "disabled",
    true,
  );
  expect(screen.getByText("Rome flight canceled")).toBeDefined();
  fireEvent.click(screen.getByRole("tab", { name: "Reset" }));
  expect(
    await screen.findByRole("button", { name: "Reset all claims" }),
  ).toHaveProperty("disabled", true);
});

it("shows a claim that failed twice as left for a handler", async () => {
  const { claim } = mockBackend();
  Object.assign(claim, { attempts: 2, left_for_handler: true });
  render(<App />);
  const queue = await screen.findByRole("navigation", { name: "Claims" });
  expect(
    within(queue).getByRole("button", { name: /CLM-1001/ }).textContent,
  ).toContain("left for a handler");
  expect(
    within(queue).getByRole("button", { name: /CLM-1002/ }).textContent,
  ).toContain("waiting");
});
