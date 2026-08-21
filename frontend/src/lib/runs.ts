/** Run context in localStorage — powers global nav links and rerun linkage. */

const LAST_RUN_KEY = "agentaudit.lastRun";
const RERUN_PREFIX = "agentaudit.rerunOf.";

function safeGet(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode etc. */
  }
}

export function rememberRun(runId: string): void {
  safeSet(LAST_RUN_KEY, runId);
}

export function getLastRun(): string | null {
  return safeGet(LAST_RUN_KEY);
}

/** After creating a verified re-run, link parent → rerun for revenue/delta lookups. */
export function rememberRerun(parentRunId: string, rerunRunId: string): void {
  safeSet(RERUN_PREFIX + parentRunId, rerunRunId);
}

export function getRerunOf(parentRunId: string): string | null {
  return safeGet(RERUN_PREFIX + parentRunId);
}
