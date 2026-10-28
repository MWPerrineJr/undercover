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

import { original, approved, mockBackend } from "../tests/backend";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("loads the queue, all evidence, policy and customer history", async () => {
  mockBackend();
  render(<App />);
  expect(screen.getByRole("status").textContent).toContain("Loading");
  expect(
    await screen.findByRole("heading", { name: "Flight canceled" }),
  ).toBeDefined();
  expect(screen.getByText(original.story)).toBeDefined();
  expect(screen.getByText("Hotel paid: $420.00.")).toBeDefined();
  expect(screen.getByText("Earlier delay")).toBeDefined();
  expect(screen.getByText("Yes")).toBeDefined();
  expect(screen.getByText("No")).toBeDefined();
  expect(screen.getAllByText("None").length).toBeGreaterThan(0);
  expect(screen.getByText("Electronics Plus")).toBeDefined();
  expect(screen.getByText("Policy section 3: trip delay")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: /CLM-1002/ }));
  expect(
    await screen.findByRole("heading", { name: "Lost baggage" }),
  ).toBeDefined();
});

it("shows the read-only agent instructions and returns to the claim", async () => {
  mockBackend();
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Agent instructions" }));
  expect(
    await screen.findByText(
      "Look up the sections of the wording and the manual you need.",
    ),
  ).toBeDefined();
  expect(
    screen.getByRole("heading", { name: "Working a claim" }),
  ).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Claims workspace" }));
  expect(
    await screen.findByRole("button", { name: "Run agent" }),
  ).toBeDefined();
});

it("runs the agent, polls active work and stops polling after completion", async () => {
  const { claim, fetcher } = mockBackend();
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect(
    await screen.findByRole("button", { name: "Agent working" }),
  ).toHaveProperty("disabled", true);
  expect(await screen.findByText("Agent started")).toBeDefined();
  claim.running = false;
  claim.status = "decided";
  claim.decision = {
    ...{
      outcome: "refer",
      payout: "0",
      calculation: "0",
      explanation: "Needs evidence.",
      policy_sections: [11],
      manual_sections: [5],
    },
    outcome: "refer",
    payout: "0",
  };
  expect(await screen.findByText("refer", {}, { timeout: 2500 })).toBeDefined();
  const calls = fetcher.mock.calls.length;
  await act(async () => {
    await new Promise((resolve) => {
      setTimeout(resolve, 1200);
    });
  });
  expect(fetcher.mock.calls).toHaveLength(calls);
});

it("retains sign-off after a payment error and allows payment retry", async () => {
  const backend = mockBackend(approved);
  backend.failNextPayment();
  render(<App />);
  fireEvent.change(await screen.findByLabelText("Signing handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
  expect(await screen.findByRole("alert")).toBeDefined();
  expect(await screen.findByText("Signed off by Dana Whitfield")).toBeDefined();
  fireEvent.click(
    await screen.findByRole("button", { name: "Record payment" }),
  );
  expect(await screen.findByText(/Simulated payment recorded/)).toBeDefined();
  expect(screen.queryByRole("button", { name: "Record payment" })).toBeNull();
});

it("reports a run error and allows retry", async () => {
  const { fetcher } = mockBackend();
  render(<App />);
  const button = await screen.findByRole("button", { name: "Run agent" });
  fetcher.mockResolvedValueOnce(new Response("{}", { status: 409 }));
  fireEvent.click(button);
  expect(await screen.findByRole("alert")).toBeDefined();
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  expect(
    await screen.findByRole("button", { name: "Agent working" }),
  ).toBeDefined();
});

it("shows an empty queue", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation((path: string) =>
        Promise.resolve(
          Response.json(
            path === "/api/claims" ? [] : { running: false, total: 0 },
          ),
        ),
      ),
  );
  render(<App />);
  expect(await screen.findByText("No claims in the queue.")).toBeDefined();
});

it("reports queue failures and retries", async () => {
  const { fetcher } = mockBackend();
  fetcher.mockRejectedValueOnce(new Error("Offline"));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Offline Retry",
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(
    await screen.findByRole("heading", { name: "Flight canceled" }),
  ).toBeDefined();
});

it("reports claim loading failures and retries", async () => {
  const { fetcher, dispatch: originalFetch } = mockBackend();
  let failed = false;
  fetcher.mockImplementation(async (path, init) => {
    if (path === "/api/claims/CLM-1001" && !failed) {
      failed = true;
      return new Response("{}", { status: 500 });
    }
    return originalFetch(path, init);
  });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
  expect(
    await screen.findByRole("heading", { name: "Flight canceled" }),
  ).toBeDefined();
});

it("ignores a stale claim response after selecting another claim", async () => {
  const { fetcher, dispatch: originalFetch } = mockBackend();
  let resolve: ((response: Response) => void) | undefined;
  fetcher.mockImplementation(async (path, init) => {
    if (path === "/api/claims/CLM-1001")
      return await new Promise<Response>((done) => {
        resolve = done;
      });
    return originalFetch(path, init);
  });
  render(<App />);
  await waitFor(() => {
    expect(resolve).toBeDefined();
  });
  fireEvent.click(screen.getByRole("button", { name: /CLM-1002/ }));
  expect(
    await screen.findByRole("heading", { name: "Lost baggage" }),
  ).toBeDefined();
  await act(async () => {
    resolve?.(Response.json(original));
    await Promise.resolve();
  });
  expect(screen.queryByRole("heading", { name: "Flight canceled" })).toBeNull();
});
