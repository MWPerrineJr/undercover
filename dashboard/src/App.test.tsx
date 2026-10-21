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
import type { Claim, Summary } from "./types";

const original: Claim = {
  claim_id: "CLM-1001",
  customer_id: "CUS-1",
  policy_id: "POL-1",
  claim_type: "trip_delay",
  summary: "Flight canceled",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome",
  story: "My flight was canceled. I stayed at an airport hotel.",
  amount_claimed: "420",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 420 },
  ],
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "Hotel paid: $420.00." },
  ],
  status: "waiting",
  running: false,
  thread_id: null,
  decision: null,
  sign_off: null,
  payment: null,
};

function mockBackend(initial: Partial<Claim> = {}) {
  const claim: Claim = { ...original, ...initial };
  let failPayment = false;
  const request = async (input: string, init?: RequestInit) => {
    await Promise.resolve();
    const path = input.replace("/api", "");
    if (init?.method === "POST") {
      if (path.endsWith("/run")) {
        claim.running = true;
        claim.status = "in_progress";
        claim.thread_id = "thread-1";
      }
      if (path.endsWith("/sign-off")) claim.sign_off = { handler_id: "HND-01" };
      if (path.endsWith("/payment")) {
        if (failPayment) {
          failPayment = false;
          return new Response("{}", { status: 503 });
        }
        claim.payment = { amount: claim.decision?.payout ?? "0" };
        claim.status = "decided";
      }
      return Response.json({ thread_id: "thread-1" });
    }
    const summary: Summary = { ...claim, customer_name: "Maya Patel" };
    const routes: Record<string, unknown> = {
      "/claims": [
        summary,
        { ...summary, claim_id: "CLM-1002", customer_name: "Tom Becker" },
      ],
      "/claims/CLM-1001": claim,
      "/claims/CLM-1002": {
        ...claim,
        claim_id: "CLM-1002",
        summary: "Lost baggage",
      },
      "/policies/POL-1": {
        policy_id: "POL-1",
        plan: "premium",
        add_ons: [],
        trip: { destination: "Rome" },
        active: true,
        note: null,
      },
      "/customers/CUS-1": {
        name: "Maya Patel",
        previous_claims: [{ summary: "Earlier delay", amount_paid: 100 }],
        verified: false,
      },
      "/plans": {
        plans: [{ plan: "premium", trip_delay_max: 800 }],
        add_ons: [{ name: "Electronics Plus" }],
        deductible_applies_to: ["baggage", "emergency_medical"],
      },
      "/policy-wording": {
        version: "2026.1",
        text: "Policy section 3: trip delay",
      },
      "/instructions": {
        text: "Read the complete policy wording before deciding.",
      },
      "/handlers": [
        {
          handler_id: "HND-01",
          name: "Dana Whitfield",
          can_approve_over_limit: true,
        },
      ],
      "/claims/CLM-1001/activity": claim.thread_id
        ? [
            {
              id: 1,
              thread_id: claim.thread_id,
              message: "Agent started",
              created_at: "2026-06-24T10:00:00Z",
            },
          ]
        : [],
      "/claims/CLM-1002/activity": [],
    };
    return Response.json(routes[path] ?? {});
  };
  const fetcher = vi.fn(request);
  vi.stubGlobal("fetch", fetcher);
  return {
    claim,
    fetcher,
    dispatch: request,
    failNextPayment: () => {
      failPayment = true;
    },
  };
}

const approved: Partial<Claim> = {
  status: "waiting_for_sign_off",
  thread_id: "thread-1",
  decision: {
    outcome: "approve",
    payout: "1250",
    calculation: "Eligible $1,250.00",
    explanation: "Covered loss. See section 5.",
    policy_sections: [5, 10],
  },
};

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
      "Read the complete policy wording before deciding.",
    ),
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
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json([])));
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
