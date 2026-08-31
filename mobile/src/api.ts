import type {
  Building,
  BuildingShadowMap,
  Route,
  RoutePreference,
  TreeShadowMap,
} from "./types";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 10_000;

async function request(url: string, options?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("The AggieShade server did not respond. Check that the backend is running.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export async function getBuildings(): Promise<Building[]> {
  return parseResponse<Building[]>(await request(`${API_URL}/buildings`));
}

export async function getRoute(
  originId: string,
  destinationId: string,
  preference: RoutePreference,
  at: Date,
): Promise<Route> {
  const response = await request(`${API_URL}/routes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin_id: originId,
      destination_id: destinationId,
      preference,
      at: at.toISOString(),
    }),
  });
  return parseResponse<Route>(response);
}

export async function getTreeShadowMap(at: Date): Promise<TreeShadowMap> {
  const timestamp = encodeURIComponent(at.toISOString());
  return parseResponse<TreeShadowMap>(
    await request(`${API_URL}/shade/tree-shadows/map?at=${timestamp}`),
  );
}

export async function getBuildingShadowMap(at: Date): Promise<BuildingShadowMap> {
  const timestamp = encodeURIComponent(at.toISOString());
  return parseResponse<BuildingShadowMap>(
    await request(`${API_URL}/shade/building-shadows/map?at=${timestamp}`),
  );
}
