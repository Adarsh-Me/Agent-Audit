/**
 * Single API module — every backend call goes through here.
 * Shapes spot-checked against backend/app/routers/{audit,report,remediations,delta,
 * stream,uploads,catalog}.py and app/revenue/risk_model.py (authoritative over SCHEMA.md
 * where they differ).
 */

export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/** SCHEMA §7 error envelope: {"error":{"code","message","details"}} */
export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;
  constructor(code: string, message: string, status: number, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError("E-NET", "Backend unreachable — is it running on port 8000?", 0);
  }
  if (!res.ok) {
    let code = `E${res.status}`;
    let message = res.statusText;
    let details: Record<string, unknown> = {};
    try {
      const body = (await res.json()) as { error?: { code?: string; message?: string; details?: Record<string, unknown> } };
      if (body?.error?.code) code = body.error.code;
      if (body?.error?.message) message = body.error.message;
      details = body.error?.details ?? {};
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(code, message, res.status, details);
  }
  return (await res.json()) as T;
}

/* ------------------------------------------------------------------ types */

export type RunStatus = "queued" | "running" | "done" | "partial" | "failed";
export type CatalogSource = "demo" | "upload" | "mirror";

/** Every measured figure carries its interval — no naked numbers. */
export interface CiNum {
  value: number;
  ci_low: number;
  ci_high: number;
}

export interface CreateAuditInput {
  catalog_source: CatalogSource;
  catalog_id?: string;
  gmv_inr?: number;
  /** present → verified re-run (E401 gate if remediations pending) */
  parent_run_id?: string;
}

export interface CreateAuditResponse {
  audit_id: string;
  status: RunStatus;
  trials_total: number;
}

export interface AuditStatusResponse {
  run_id: string;
  status: RunStatus;
  trials_done: number;
  trials_total: number | null;
  cost_usd: number;
  eta_s: number | null;
  parent_run_id: string | null;
  type: 'audit' | 'rerun';
  abort_reason?: string | null;
  merchant?: string | null;
  catalog_source?: string | null;
  started_at?: string | null;
  reason?: string | null;
}

export interface TrialTotals {
  total: number;
  parse_ok: number;
  null_allowed: number;
  forced: number;
}

export interface ModelMeta {
  id: string;
  version: string | null;
  parse_failure_rate: number;
}

export interface InvisibleSku {
  sku: string;
  share: CiNum;
}

export interface FramingProduct {
  sku: string;
  share_a: number;
  share_b: number;
  delta: number;
}

export interface PersonaNull {
  persona_id: string;
  null_rate: number;
}

export interface ScoreComponents {
  visibility: number;
  stability: number;
  position_indep: number;
  coverage: number;
  data_completeness: number;
}

/** GET /api/audit/{id}/metrics (§3.5 as actually returned by audit.py). */
export interface MetricsPayload {
  run_id: string;
  status: RunStatus;
  partial: boolean;
  trials: TrialTotals;
  hhi_norm: CiNum & { per_model?: Record<string, { value: number }> };
  position: {
    top3_capture: CiNum;
    lift: number;
    p_value: number;
    per_slot: number[];
  };
  framing: { mean_delta: CiNum; per_product: FramingProduct[] };
  coverage: { f_task: CiNum; nulls_by_persona: PersonaNull[] };
  stability: { matrix: Record<string, number>; mean: CiNum; band: string };
  invisible_skus: InvisibleSku[];
  score: CiNum & { components: ScoreComponents };
  models_meta: ModelMeta[];
  cost_usd: number;
  manifest_ref: string | null;
}

/** While queued the endpoint returns only the stub. */
export type MetricsResponse =
  | MetricsPayload
  | { run_id: string; status: "queued"; partial: false };

export interface LegibilityRow {
  sku: string;
  title: string;
  tier: "rich" | "medium" | "starved" | string;
  composite: number | null;
}

export interface RevenueInputsEcho {
  gmv_inr: { value: number; source: "user" | "demo-default"; note: string };
  s_agent: { value: number; source: string; note: string };
  f_task: {
    value: number;
    source: "measured";
    ci_low: number;
    ci_high: number;
    note: string;
  };
}

export interface RupeeRange {
  value: number;
  ci_low: number;
  ci_high: number;
  note?: string;
}

/** GET /api/revenue/{id} — risk_model.compute_revenue output. */
export interface RevenueResponse {
  run_id: string;
  status: RunStatus;
  inputs: RevenueInputsEcho;
  revenue_at_risk_inr: RupeeRange;
  honesty_note: string;
  recoverable_inr: RupeeRange | null;
  delta_f: CiNum | null;
}

export interface ReportResponse extends MetricsPayload {
  revenue_preview: RevenueResponse;
  legibility: LegibilityRow[];
}

export interface RemediationFix {
  field: "title" | "description" | "structured_data" | (string & {});
  before: string;
  after: string;
  rationale: string;
}

export type RemediationStatus = "pending" | "approved" | "rejected";

export interface RemediationRow {
  id: string;
  product_id: string;
  sku: string | null;
  title: string | null;
  status: RemediationStatus;
  reviewed_by: string | null;
  applied_at: string | null;
  fixes: RemediationFix[];
}

export interface RemediationListResponse {
  run_id: string;
  counts: { pending: number; approved: number; rejected: number };
  remediations: RemediationRow[];
}

export interface GenerateRemediationsResponse {
  run_id: string;
  created: number;
  not_flagged: number;
}

export interface MirrorResponse {
  mirror_catalog_id: string;
  parent_run_id: string;
}

export interface SkuChange {
  sku: string;
  share_before: number;
  share_after: number;
  abs_change: number;
}

/** GET /api/delta/{rerun_run_id} — delta.py (authoritative; ≠ SCHEMA §3.6 draft). */
export interface DeltaResponse {
  original_run_id: string;
  rerun_run_id: string;
  f_task: { before: CiNum; after: CiNum; delta: CiNum };
  score: { before: number; after: number };
  per_sku_changes: SkuChange[];
  recoverable_inr: RupeeRange | null;
  verdict: string;
  honest_note: string;
}

export interface UploadInvalidRow {
  row: number;
  code: string;
  message: string;
}

export interface UploadResponse {
  catalog_id: string;
  valid: number;
  invalid: UploadInvalidRow[];
}

export interface CatalogProduct {
  id: string;
  title: string;
  price_inr: number;
  description: string;
  image_url: string | null;
  page_url: string | null;
  tier: string;
  structured_data: Record<string, unknown> | null;
}

export interface CatalogResponse {
  catalog_id: string;
  source: string;
  version: number | null;
  count: number;
  products: CatalogProduct[];
}

/** GET /catalogs — every known catalog (demo seed + imported stores), newest first. */
export interface CatalogSummary {
  catalog_id: string;
  source: string;
  merchant: string | null;
  product_count: number;
  created_at: string | null;
}

export function listCatalogs(): Promise<{ catalogs: CatalogSummary[] }> {
  return request<{ catalogs: CatalogSummary[] }>("/catalogs");
}

/* --------------------------------------------------- payments (F8) */
/** POST /api/payments/link — routers/payments.py is authoritative.
 *  Replays carry idempotent_replay: true and re-fetch short_url live (may be ""
 *  only if Razorpay was unreachable at that moment). */
export interface PaymentLinkResponse {
  payment_id: string;
  razorpay_link_id: string;
  short_url: string;
  amount_inr: number;
  status: string;
  idempotent_replay?: boolean;
}

/** GET /api/payments/{run_id}/status — newest payment first. */
export interface PaymentRow {
  razorpay_link_id: string;
  amount_inr: number;
  status: string;
  captured_at: string | null;
}

export interface PaymentStatusResponse {
  run_id: string;
  payments: PaymentRow[];
  captured: boolean;
}

/* ------------------------------------------------ store import (Shopify) */

export interface StoreImportResponse {
  catalog_id: string;
  store_url: string;
  merchant: string;
  products: {
    valid: number;
    invalid: UploadInvalidRow[];
    capped_to: number | null;
    pages_fetched: number;
  };
  store_currency: string;
  fx: { rate: number; converted: boolean; note: string };
}

/** POST /api/stores/import — public Shopify products.json feed → auditable catalog. */
export function importStore(input: {
  url: string;
  store_currency: "INR" | "USD" | "EUR" | "GBP";
  max_products?: number;
}): Promise<StoreImportResponse> {
  return request<StoreImportResponse>("/api/stores/import", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/* ------------------------------------------------ runs dashboard */

export interface RunSummaryRow {
  run_id: string;
  type: "audit" | "rerun";
  status: RunStatus;
  abort_reason: string | null;
  cost_usd: number;
  trials_total: number;
  trials_recorded: number;
  started_at: string | null;
  completed_at: string | null;
  parent_run_id: string | null;
  catalog: {
    id: string;
    source: CatalogSource | null;
    merchant: string | null;
    products: number | null;
  };
  fixes_needed: number;
  summary: {
    score: number;
    f_task: number;
    top3_capture: number;
    parse_ok: number;
    models: Record<string, { attempts: number; parse_ok: number }>;
    note: string;
  } | null;
}

/** GET /api/runs — recent-run outcomes with failure reasons and mid-data summaries. */
export function listRuns(limit = 10): Promise<{ runs: RunSummaryRow[] }> {
  return request<{ runs: RunSummaryRow[] }>(`/api/runs?limit=${limit}`);
}

/* -------------------------------------------------------------- SSE events */

export interface SseProgressEvent {
  done: number;
  total: number;
  cost_usd: number;
  ts?: number;
}

export interface SseTrialEvent {
  model: string;
  persona_id: string;
  condition: string;
  choice: string | null;
  latency_ms: number;
  parse_ok: boolean;
  ts?: number;
}

export interface SseCostCapEvent {
  done: number;
  total: number;
  cost_usd: number;
}

export interface SseCompleteEvent {
  run_id: string;
  status: Exclude<RunStatus, "queued" | "running">;
  abort_reason?: string | null;
}

/* ---------------------------------------------------------------- calls */

export function createAudit(input: CreateAuditInput): Promise<CreateAuditResponse> {
  return request<CreateAuditResponse>("/api/audit", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getAudit(runId: string): Promise<AuditStatusResponse> {
  return request<AuditStatusResponse>(`/api/audit/${encodeURIComponent(runId)}`);
}

export function getMetrics(runId: string): Promise<MetricsResponse> {
  return request<MetricsResponse>(`/api/audit/${encodeURIComponent(runId)}/metrics`);
}

export function getReport(runId: string): Promise<ReportResponse> {
  return request<ReportResponse>(`/api/report/${encodeURIComponent(runId)}`);
}

export function getRevenue(
  runId: string,
  opts: { s_agent: number; gmv_inr?: number; delta_run_id?: string },
): Promise<RevenueResponse> {
  const q = new URLSearchParams({ s_agent: String(opts.s_agent) });
  if (opts.gmv_inr !== undefined) q.set("gmv_inr", String(opts.gmv_inr));
  if (opts.delta_run_id) q.set("delta_run_id", opts.delta_run_id);
  return request<RevenueResponse>(
    `/api/revenue/${encodeURIComponent(runId)}?${q.toString()}`,
  );
}

export function generateRemediations(runId: string): Promise<GenerateRemediationsResponse> {
  return request<GenerateRemediationsResponse>(
    `/api/remediations/${encodeURIComponent(runId)}/generate`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

export function listRemediations(runId: string): Promise<RemediationListResponse> {
  return request<RemediationListResponse>(
    `/api/remediations?run_id=${encodeURIComponent(runId)}`,
  );
}

export function reviewRemediation(
  remId: string,
  status: "approved" | "rejected",
): Promise<{ id: string; status: RemediationStatus }> {
  return request(`/api/remediations/${encodeURIComponent(remId)}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function buildMirror(runId: string): Promise<MirrorResponse> {
  return request<MirrorResponse>(`/api/remediations/${encodeURIComponent(runId)}/mirror`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getDelta(rerunRunId: string): Promise<DeltaResponse> {
  return request<DeltaResponse>(`/api/delta/${encodeURIComponent(rerunRunId)}`);
}

export async function uploadCatalog(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/uploads`, { method: "POST", body: form });
  } catch {
    throw new ApiError("E-NET", "Backend unreachable — is it running on port 8000?", 0);
  }
  if (!res.ok) {
    let code = `E${res.status}`;
    let message = res.statusText;
    try {
      const body = (await res.json()) as { error?: { code?: string; message?: string } };
      if (body?.error?.code) code = body.error.code;
      if (body?.error?.message) message = body.error.message;
    } catch {
      /* noop */
    }
    throw new ApiError(code, message, res.status);
  }
  return (await res.json()) as UploadResponse;
}

export function getCatalog(catalogId?: string): Promise<CatalogResponse> {
  return request<CatalogResponse>(
    catalogId ? `/catalog?catalog_id=${encodeURIComponent(catalogId)}` : "/catalog",
  );
}

export function createPaymentLink(
  runId: string,
  sku: string,
): Promise<PaymentLinkResponse> {
  return request<PaymentLinkResponse>("/api/payments/link", {
    method: "POST",
    body: JSON.stringify({ run_id: runId, sku }),
  });
}

export function getPaymentStatus(runId: string): Promise<PaymentStatusResponse> {
  return request<PaymentStatusResponse>(
    `/api/payments/${encodeURIComponent(runId)}/status`,
  );
}

/** SSE stream URL for a run (consumed with EventSource). */
export function streamUrl(runId: string): string {
  return `${API_BASE}/api/stream/${encodeURIComponent(runId)}`;
}

export interface EvidenceQuote {
  model: string;
  persona_id: string;
  condition?: string;
  text: string;
}

export interface EvidenceProduct {
  sku: string;
  picks: number;
  quotes: EvidenceQuote[];
}

export interface EvidenceResponse {
  run_id: string;
  status: string;
  products: EvidenceProduct[];
  declines: EvidenceQuote[];
}

/** Verbatim LLM reasoning grouped by chosen SKU (Agent Evidence Panel). */
export function getEvidence(runId: string): Promise<EvidenceResponse> {
  return request<EvidenceResponse>(`/api/evidence/${encodeURIComponent(runId)}`);
}
