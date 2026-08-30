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
