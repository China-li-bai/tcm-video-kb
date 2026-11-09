import type { PathsResponse, Subgraph } from "../types";

const base = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : "网络错误";
    throw new ApiError(message, null);
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* response was not JSON */
    }
    if (response.status >= 500 && detail.startsWith("HTTP")) {
      detail = import.meta.env.DEV
        ? `API 没有正常响应（HTTP ${response.status}）。确认 127.0.0.1:8000 上的服务已启动。`
        : `API 没有正常响应（HTTP ${response.status}）。`;
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export function fetchSubgraph(focus: string): Promise<Subgraph> {
  return getJson<Subgraph>(`/graph/subgraph?focus=${encodeURIComponent(focus)}`);
}

export function fetchPaths(focus: string): Promise<PathsResponse> {
  return getJson<PathsResponse>(`/graph/paths?focus=${encodeURIComponent(focus)}`);
}
