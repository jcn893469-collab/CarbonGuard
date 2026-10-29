const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
export const apiBaseUrl = (
  configuredApiBaseUrl ?? (import.meta.env.PROD ? "" : "http://127.0.0.1:8000")
).replace(/\/+$/, "");

const API_TIMEOUT_MS = 15_000;

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, API_TIMEOUT_MS);
  const abortFromCaller = () => controller.abort();
  options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  if (options.signal?.aborted) abortFromCaller();

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (timedOut) {
      throw new Error("The CarbonGuard API request timed out. Please try again.");
    }
    if (error instanceof TypeError) {
      throw new Error(
        "Unable to reach the CarbonGuard API. Check its availability and URL.",
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function fetchApiHealth(signal) {
  const response = await fetchWithTimeout(`${apiBaseUrl}/api/health`, { signal });

  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}`);
  }

  const payload = await response.json();
  if (
    !payload ||
    typeof payload !== "object" ||
    payload.status !== "healthy" ||
    typeof payload.application !== "string" ||
    typeof payload.version !== "string"
  ) {
    throw new Error("The CarbonGuard health response was invalid.");
  }
  return payload;
}

async function requestApi(path, options = {}) {
  const response = await fetchWithTimeout(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const responseText = await response.text();
  let payload = null;
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch {
      payload = responseText;
    }
  }

  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => `${item.loc?.join(".")}: ${item.msg}`).join("; ")
      : detail || payload || `Request failed with HTTP ${response.status}`;
    throw new Error(String(message));
  }
  return payload;
}

export function listApplications({ signal } = {}) {
  return requestApi("/api/applications?limit=100", { signal });
}

export function listApplicationWorkloads(applicationId, { signal } = {}) {
  return requestApi(`/api/applications/${applicationId}/workloads`, { signal });
}

export function createWorkload(applicationId, workload) {
  return requestApi(`/api/applications/${applicationId}/workloads`, {
    method: "POST",
    body: JSON.stringify(workload),
  });
}

export function listWorkloadRuns(applicationId, { signal } = {}) {
  const path = applicationId
    ? `/api/applications/${applicationId}/workload-runs?limit=100`
    : "/api/workload-runs?limit=100";
  return requestApi(path, { signal });
}

export function getApplicationAnalyticsDetail(applicationId, { signal } = {}) {
  return requestApi(`/api/analytics/applications/${applicationId}`, { signal });
}

export function simulateWorkload(parameters) {
  return requestApi("/api/workloads/simulate", {
    method: "POST",
    body: JSON.stringify(parameters),
  });
}

export function createApplication(name) {
  return requestApi("/api/applications", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function createApplicationRecord(application) {
  return requestApi("/api/applications", {
    method: "POST",
    body: JSON.stringify(application),
  });
}

export function updateApplication(applicationId, application) {
  return requestApi(`/api/applications/${applicationId}`, {
    method: "PUT",
    body: JSON.stringify(application),
  });
}

export function deleteApplication(applicationId) {
  return requestApi(`/api/applications/${applicationId}`, {
    method: "DELETE",
  });
}

export function listBudgetPolicies() {
  return requestApi("/api/budget-policies");
}

export function createBudgetPolicy(policy) {
  return requestApi("/api/budget-policies", {
    method: "POST",
    body: JSON.stringify(policy),
  });
}

export function updateBudgetPolicy(policyId, changes) {
  return requestApi(`/api/budget-policies/${policyId}`, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
}

export function deleteBudgetPolicy(policyId) {
  return requestApi(`/api/budget-policies/${policyId}`, { method: "DELETE" });
}

export function evaluateBudgetPolicy(policyId) {
  return requestApi(`/api/budget-policies/${policyId}/evaluate`, {
    method: "POST",
  });
}

export function getApplicationBudgetStatus(applicationId) {
  return requestApi(`/api/applications/${applicationId}/budget-status`);
}

function makeQuery(params) {
  return new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null),
  ).toString();
}

export async function getAnalyticsOverview({ signal } = {}) {
  const payload = await requestApi("/api/analytics/overview", { signal });
  if (
    !payload ||
    typeof payload !== "object" ||
    !Array.isArray(payload.applications) ||
    !payload.policy_status_counts ||
    !Number.isFinite(payload.all_time_completed_workload_run_count) ||
    !Number.isFinite(payload.all_time_estimated_energy_kwh) ||
    !Number.isFinite(payload.all_time_estimated_emissions_kg_co2e)
  ) {
    throw new Error("The analytics overview response was incomplete.");
  }
  return payload;
}

export async function getAnalyticsTrend({
  start,
  end,
  interval,
  applicationId,
  signal,
}) {
  const query = makeQuery({
    start,
    end,
    interval,
    application_id: applicationId || undefined,
  });
  const payload = await requestApi(`/api/analytics/trends?${query}`, { signal });
  if (
    !payload ||
    typeof payload !== "object" ||
    !Array.isArray(payload.buckets) ||
    !["daily", "weekly", "monthly"].includes(payload.interval)
  ) {
    throw new Error("The analytics trend response was incomplete.");
  }
  return payload;
}

export async function getAnalyticsWorkloads({
  start,
  end,
  applicationId,
  signal,
} = {}) {
  const query = makeQuery({
    start,
    end,
    application_id: applicationId || undefined,
  });
  const payload = await requestApi(`/api/analytics/workloads?${query}`, { signal });
  if (
    !payload ||
    typeof payload !== "object" ||
    !Array.isArray(payload.applications) ||
    !Array.isArray(payload.runs) ||
    !payload.status_counts ||
    typeof payload.status_counts !== "object"
  ) {
    throw new Error("The workload analytics response was incomplete.");
  }
  return payload;
}


export async function downloadAnalyticsReport({ start, end, applicationId }) {
  const query = makeQuery({
    start,
    end,
    application_id: applicationId || undefined,
  });
  const response = await fetchWithTimeout(
    `${apiBaseUrl}/api/analytics/export.csv?${query}`,
  );
  if (!response.ok) {
    const responseText = await response.text();
    let payload = null;
    try {
      payload = responseText ? JSON.parse(responseText) : null;
    } catch {
      payload = null;
    }
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : `Report download failed with HTTP ${response.status}`;
    throw new Error(
      detail,
    );
  }
  if (!response.headers.get("Content-Type")?.startsWith("text/csv")) {
    throw new Error("The report endpoint returned an unexpected response.");
  }
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename =
    disposition.match(/filename="([^"]+)"/)?.[1] || "carbonguard-report.csv";
  return { blob: await response.blob(), filename };
}
