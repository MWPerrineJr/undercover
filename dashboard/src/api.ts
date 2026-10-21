import { useEffect, useState } from "react";
import type { Claim, Details } from "./types";

export async function api<T>(
  path: string,
  signal?: AbortSignal,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    signal,
    ...(body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
  });
  if (!response.ok) {
    throw new Error(
      `Request failed (${String(response.status)}). Please retry.`,
    );
  }
  return (await response.json()) as T;
}

export async function loadDetails(
  id: string,
  signal: AbortSignal,
): Promise<Details> {
  const claim = await api<Claim>(`/claims/${id}`, signal);
  const [policy, customer, plans, wording, handlers, activity] =
    await Promise.all([
      api<Details["policy"]>(`/policies/${claim.policy_id}`, signal),
      api<Details["customer"]>(`/customers/${claim.customer_id}`, signal),
      api<Details["plans"]>("/plans", signal),
      api<Details["wording"]>("/policy-wording", signal),
      api<Details["handlers"]>("/handlers", signal),
      api<Details["activity"]>(`/claims/${id}/activity`, signal),
    ]);
  return { claim, policy, customer, plans, wording, handlers, activity };
}

export function useResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  revision: number,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    async function update() {
      try {
        const result = await load(controller.signal);
        if (!controller.signal.aborted) {
          setData(result);
          setError("");
        }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : "Unable to load records.",
          );
        }
      }
    }
    void update();
    return () => {
      controller.abort();
    };
  }, [load, revision]);
  return { data, error };
}
