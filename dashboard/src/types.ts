export type Json =
  string | number | boolean | null | Json[] | { [key: string]: Json };
export type BusinessRecord = Record<string, Json>;
export type Status =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";
export interface Decision {
  outcome: "approve" | "decline" | "refer";
  payout: string;
  calculation: string;
  explanation: string;
  policy_sections: number[];
  manual_sections: number[];
}
export interface Summary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  amount_claimed: string;
  status: Status;
  running: boolean;
  decision: Decision | null;
  payment: { amount: string } | null;
}
export interface Claim {
  claim_id: string;
  customer_id: string;
  policy_id: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  story: string;
  amount_claimed: string;
  items: { description: string; category: string; amount: number }[];
  documents: { name: string; type: string; content: string }[];
  status: Status;
  running: boolean;
  thread_id: string | null;
  decision: Decision | null;
  sign_off: { handler_id: string } | null;
  payment: { amount: string } | null;
}
export interface Handler {
  handler_id: string;
  name: string;
  can_approve_over_limit: boolean;
}
export interface Activity {
  id: number;
  thread_id: string;
  message: string;
  kind: "step" | "read";
  created_at: string;
}
export interface Instructions {
  name: string;
  title: string;
  text: string;
}
export interface Details {
  claim: Claim;
  policy: BusinessRecord;
  customer: BusinessRecord;
  plans: {
    plans: BusinessRecord[];
    add_ons: BusinessRecord[];
    deductible_applies_to: string[];
  };
  wording: { text: string; version: string };
  handlers: Handler[];
  activity: Activity[];
}

export interface QueueRun {
  running: boolean;
  total: number;
  processed: number;
  failed: number;
  skipped: number;
  current_claim_id: string | null;
  message: string;
}
export type WorkspaceTab = "queue" | "finished" | "reset";
