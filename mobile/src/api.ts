import type { Building, BuildingShadowMap, Route, TreeShadowMap } from "./types";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export async function getBuildings(): Promise<Building[]> {
  return parseResponse<Building[]>(await fetch(`${API_URL}/buildings`));
}

export async function getRoute(originId: string, destinationId: string): Promise<Route> {
  const response = await fetch(`${API_URL}/routes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin_id: originId, destination_id: destinationId }),
  });
  return parseResponse<Route>(response);
}

export async function getTreeShadowMap(at: Date): Promise<TreeShadowMap> {
  const timestamp = encodeURIComponent(at.toISOString());
  return parseResponse<TreeShadowMap>(
    await fetch(`${API_URL}/shade/tree-shadows/map?at=${timestamp}`),
  );
}

export async function getBuildingShadowMap(at: Date): Promise<BuildingShadowMap> {
  const timestamp = encodeURIComponent(at.toISOString());
  return parseResponse<BuildingShadowMap>(
    await fetch(`${API_URL}/shade/building-shadows/map?at=${timestamp}`),
  );
}
