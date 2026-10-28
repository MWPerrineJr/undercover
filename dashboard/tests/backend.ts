import { vi } from "vitest";
import type { Claim, QueueRun, Summary } from "../src/types";

export const original: Claim = {
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
export const approved: Partial<Claim> = {
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
const idle: QueueRun = {
  running: false,
  total: 0,
  processed: 0,
  failed: 0,
  skipped: 0,
  current_claim_id: null,
  message: "Ready to run waiting claims",
};

export function mockBackend(initial: Partial<Claim> = {}) {
  const claim: Claim = { ...original, ...initial };
  const second: Claim = {
    ...original,
    claim_id: "CLM-1002",
    summary: "Lost baggage",
  };
  const progress: QueueRun = { ...idle };
  let failPayment = false;
  function mutate(path: string) {
    if (path === "/queue/run") {
      Object.assign(progress, {
        running: true,
        total: 2,
        current_claim_id: claim.claim_id,
        message: "Reviewing waiting claims",
      });
      claim.running = true;
      claim.status = "in_progress";
      claim.thread_id = "thread-1";
    }
    if (path === "/queue/reset") {
      Object.assign(claim, original);
      Object.assign(second, original, {
        claim_id: "CLM-1002",
        summary: "Lost baggage",
      });
      Object.assign(progress, idle);
      return Response.json({ reset_claims: 2 });
    }
    if (path.startsWith("/claims/") && path.endsWith("/run")) {
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
  const request = async (input: string, init?: RequestInit) => {
    await Promise.resolve();
    const path = input.replace("/api", "");
    if (init?.method === "POST") return mutate(path);
    const summaries: Summary[] = [
      { ...claim, customer_name: "Maya Patel" },
      { ...second, customer_name: "Tom Becker" },
    ];
    const routes: Record<string, unknown> = {
      "/claims": summaries,
      "/queue": progress,
      "/claims/CLM-1001": claim,
      "/claims/CLM-1002": second,
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
    second,
    progress,
    fetcher,
    dispatch: request,
    failNextPayment: () => {
      failPayment = true;
    },
  };
}
