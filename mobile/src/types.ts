export type Coordinate = {
  latitude: number;
  longitude: number;
};

export type Building = {
  id: string;
  name: string;
  short_name: string;
  building_number: string | null;
  abbreviation: string | null;
  point: Coordinate;
  route_point: Coordinate;
};

export type Route = {
  origin_id: string;
  destination_id: string;
  distance_m: number;
  duration_seconds: number;
  geometry: Coordinate[];
};

export type GeoJsonPosition = [number, number];

export type TreeShadowGeoJson = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties: Record<string, string>;
    geometry: {
      type: "MultiPolygon";
      coordinates: GeoJsonPosition[][][];
    };
  }>;
};

export type TreeShadowMap = {
  bucket_start: string;
  bucket_minutes: number;
  daylight: boolean;
  shadow_azimuth_degrees: number | null;
  shadow_count: number;
  geojson: TreeShadowGeoJson;
};
