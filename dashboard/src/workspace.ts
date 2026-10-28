import { useCallback, useEffect, useState } from "react";
import { api, useResource } from "./api";
import type { QueueRun, Summary } from "./types";

async function loadWorkspace(signal: AbortSignal) {
  const [claims, progress] = await Promise.all([
    api<Summary[]>("/claims", signal),
    api<QueueRun>("/queue", signal),
  ]);
  return { claims, progress };
}

export function useWorkspace() {
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => {
    setRevision((value) => value + 1);
  }, []);
  const { data, error } = useResource(loadWorkspace, revision);
  const running =
    data !== null &&
    (data.progress.running || data.claims.some((claim) => claim.running));
  const claims = data?.claims ?? null;
  const progress = data?.progress ?? null;
  const total = claims?.length ?? 0;
  const finishedCount =
    claims?.filter((claim) => claim.status === "decided").length ?? 0;
  const queueCount = total - finishedCount;
  const firstClaim =
    claims?.find((claim) => claim.status !== "decided")?.claim_id ?? "";
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(refresh, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [running, refresh]);
  return {
    claims,
    progress,
    total,
    finishedCount,
    queueCount,
    firstClaim,
    loading: data === null,
    error,
    revision,
    refresh,
    running,
  };
}
