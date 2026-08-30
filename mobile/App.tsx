import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";
import MapView, { Marker, Polyline } from "react-native-maps";

import { getBuildings, getRoute } from "./src/api";
import type { Building, Route } from "./src/types";

const MAROON = "#500000";
const GREEN = "#287052";
const TAMU_REGION = {
  latitude: 30.6168,
  longitude: -96.3411,
  latitudeDelta: 0.014,
  longitudeDelta: 0.012,
};

function formatDistance(meters: number): string {
  return meters < 1000 ? `${meters} m` : `${(meters / 1000).toFixed(1)} km`;
}

function formatDuration(seconds: number): string {
  return `${Math.max(1, Math.round(seconds / 60))} min`;
}

type BuildingRowProps = {
  label: string;
  buildings: Building[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function BuildingRow({ label, buildings, selectedId, onSelect }: BuildingRowProps) {
  return (
    <View style={styles.selectorGroup}>
      <Text style={styles.selectorLabel}>{label}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
        {buildings.map((building) => {
          const selected = selectedId === building.id;
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected }}
              key={building.id}
              onPress={() => onSelect(building.id)}
              style={[styles.chip, selected && styles.chipSelected]}
            >
              <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{building.short_name}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

export default function App() {
  const mapRef = useRef<MapView>(null);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [originId, setOriginId] = useState<string | null>(null);
  const [destinationId, setDestinationId] = useState<string | null>(null);
  const [route, setRoute] = useState<Route | null>(null);
  const [loading, setLoading] = useState(true);
  const [routing, setRouting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBuildings()
      .then((items) => {
        setBuildings(items);
        setOriginId(items[0]?.id ?? null);
        setDestinationId(items[1]?.id ?? null);
      })
      .catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : "Could not load campus buildings");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (route?.geometry.length) {
      mapRef.current?.fitToCoordinates(route.geometry, {
        edgePadding: { top: 90, right: 55, bottom: 80, left: 55 },
        animated: true,
      });
    }
  }, [route]);

  const canRoute = Boolean(originId && destinationId && originId !== destinationId && !routing);
  const selectedBuildings = useMemo(
    () => buildings.filter((building) => building.id === originId || building.id === destinationId),
    [buildings, destinationId, originId],
  );

  async function requestRoute() {
    if (!originId || !destinationId || originId === destinationId) return;
    setRouting(true);
    setError(null);
    try {
      setRoute(await getRoute(originId, destinationId));
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Could not calculate the route");
    } finally {
      setRouting(false);
    }
  }

  function selectOrigin(id: string) {
    setOriginId(id);
    setRoute(null);
    if (id === destinationId) setDestinationId(null);
  }

  function selectDestination(id: string) {
    setDestinationId(id);
    setRoute(null);
    if (id === originId) setOriginId(null);
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>TEXAS A&M CAMPUS</Text>
          <Text style={styles.title}>AggieShade</Text>
        </View>
        <View style={styles.milestoneBadge}>
          <Text style={styles.milestoneText}>MILESTONE 1</Text>
        </View>
      </View>

      <View style={styles.mapShell}>
        <MapView ref={mapRef} style={styles.map} initialRegion={TAMU_REGION}>
          {selectedBuildings.map((building) => (
            <Marker
              key={building.id}
              coordinate={building.route_point}
              title={building.short_name}
              description={building.name}
              pinColor={building.id === originId ? GREEN : MAROON}
            />
          ))}
          {route && (
            <Polyline coordinates={route.geometry} strokeColor={MAROON} strokeWidth={6} lineCap="round" />
          )}
        </MapView>
        {route && (
          <View style={styles.routeCard}>
            <Text style={styles.routeCardLabel}>FASTEST WALK</Text>
            <Text style={styles.routeCardValue}>
              {formatDuration(route.duration_seconds)} · {formatDistance(route.distance_m)}
            </Text>
          </View>
        )}
      </View>

      <View style={styles.panel}>
        {loading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator color={MAROON} />
            <Text style={styles.muted}>Loading campus buildings…</Text>
          </View>
        ) : (
          <>
            <BuildingRow label="Start" buildings={buildings} selectedId={originId} onSelect={selectOrigin} />
            <BuildingRow
              label="Destination"
              buildings={buildings}
              selectedId={destinationId}
              onSelect={selectDestination}
            />
            {error && <Text style={styles.error}>{error}</Text>}
            <Pressable
              accessibilityRole="button"
              disabled={!canRoute}
              onPress={requestRoute}
              style={({ pressed }) => [
                styles.routeButton,
                !canRoute && styles.routeButtonDisabled,
                pressed && styles.pressed,
              ]}
            >
              {routing ? <ActivityIndicator color="white" /> : <Text style={styles.routeButtonText}>Find walking route</Text>}
            </Pressable>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#F8F6F1" },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  eyebrow: { color: GREEN, fontSize: 11, fontWeight: "700", letterSpacing: 1.4 },
  title: { color: MAROON, fontSize: 30, fontWeight: "800", letterSpacing: -0.7 },
  milestoneBadge: {
    borderColor: "#D7C8B9",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  milestoneText: { color: "#6F6258", fontSize: 10, fontWeight: "700", letterSpacing: 0.8 },
  mapShell: {
    flex: 1,
    marginHorizontal: 14,
    borderRadius: 22,
    overflow: "hidden",
    backgroundColor: "#E8E3D8",
  },
  map: { flex: 1 },
  routeCard: {
    position: "absolute",
    top: 14,
    left: 14,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  routeCardLabel: { color: GREEN, fontSize: 10, fontWeight: "800", letterSpacing: 1 },
  routeCardValue: { color: MAROON, fontSize: 18, fontWeight: "800", marginTop: 2 },
  panel: { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 12, gap: 12 },
  selectorGroup: { gap: 6 },
  selectorLabel: { color: "#62574D", fontSize: 12, fontWeight: "700" },
  chipRow: { gap: 8, paddingRight: 16 },
  chip: {
    borderColor: "#D7C8B9",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 13,
    paddingVertical: 8,
    backgroundColor: "white",
  },
  chipSelected: { borderColor: MAROON, backgroundColor: MAROON },
  chipText: { color: "#4B433D", fontSize: 13, fontWeight: "600" },
  chipTextSelected: { color: "white" },
  loadingRow: { minHeight: 80, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  muted: { color: "#746A62" },
  error: { color: "#A32626", fontSize: 13 },
  routeButton: {
    minHeight: 48,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: MAROON,
  },
  routeButtonDisabled: { opacity: 0.45 },
  routeButtonText: { color: "white", fontSize: 15, fontWeight: "800" },
  pressed: { opacity: 0.8 },
});
