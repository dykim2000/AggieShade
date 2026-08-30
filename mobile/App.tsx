import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  InteractionManager,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import MapView, { Geojson, Marker, Polyline } from "react-native-maps";

import { getBuildings, getRoute, getTreeShadowMap } from "./src/api";
import type { Building, Route, TreeShadowGeoJson, TreeShadowMap } from "./src/types";

const MAROON = "#500000";
const GREEN = "#287052";
const COMMON_PLACE_IDS = ["msc", "evans", "zachry", "kyle", "academic", "sbisa"];
const TAMU_REGION = {
  latitude: 30.6168,
  longitude: -96.3411,
  latitudeDelta: 0.014,
  longitudeDelta: 0.012,
};

type SearchField = "origin" | "destination";

type ShadowOverlayProps = {
  geojson: TreeShadowGeoJson;
};

const ShadowOverlay = memo(function ShadowOverlay({ geojson }: ShadowOverlayProps) {
  return (
    <Geojson
      fillColor="rgba(35, 54, 47, 0.20)"
      geojson={geojson}
      strokeColor="rgba(35, 54, 47, 0.32)"
      strokeWidth={0.5}
      tappable={false}
      zIndex={1}
    />
  );
});

function formatDistance(meters: number): string {
  return meters < 1000 ? `${meters} m` : `${(meters / 1000).toFixed(1)} km`;
}

function formatDuration(seconds: number): string {
  return `${Math.max(1, Math.round(seconds / 60))} min`;
}

function formatBucketTime(bucketStart: string): string {
  return new Date(bucketStart).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatShadeStatus(
  loading: boolean,
  failed: boolean,
  shadowMap: TreeShadowMap | null,
): string {
  if (loading) return "Loading current tree shade…";
  if (failed || !shadowMap) return "Tree shade unavailable";
  const bucketTime = formatBucketTime(shadowMap.bucket_start);
  return shadowMap.daylight
    ? `${shadowMap.shadow_count.toLocaleString()} tree shadows · ${bucketTime}`
    : `Nighttime · no tree shadows · ${bucketTime}`;
}

function buildingMatchScore(building: Building, query: string): number | null {
  const search = query.trim().toLocaleLowerCase();
  if (!search) return null;
  const values = [
    building.name,
    building.short_name,
    building.abbreviation,
    building.building_number,
    building.id,
  ]
    .filter((value): value is string => Boolean(value))
    .map((value) => value.toLocaleLowerCase());

  if (values.some((value) => value === search)) return 0;
  if (values.some((value) => value.startsWith(search))) return 1;
  if (values.some((value) => value.split(/\s+/).some((word) => word.startsWith(search)))) {
    return 2;
  }
  return values.some((value) => value.includes(search)) ? 3 : null;
}

function buildingDetails(building: Building): string {
  const details = [
    building.short_name !== building.name ? building.short_name : null,
    building.building_number ? `Building ${building.building_number}` : null,
  ];
  return details.filter((value): value is string => Boolean(value)).join(" · ");
}

type SearchInputProps = {
  active: boolean;
  field: SearchField;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onFocus: (field: SearchField) => void;
};

function SearchInput({ active, field, label, value, onChange, onFocus }: SearchInputProps) {
  return (
    <View style={styles.searchGroup}>
      <Text style={styles.searchLabel}>{label}</Text>
      <View style={[styles.searchShell, active && styles.searchShellActive]}>
        <View style={[styles.fieldBadge, field === "origin" ? styles.originBadge : styles.destinationBadge]}>
          <Text style={styles.fieldBadgeText}>{field === "origin" ? "A" : "B"}</Text>
        </View>
        <TextInput
          accessibilityLabel={`Search ${label.toLocaleLowerCase()}`}
          autoCorrect={false}
          clearButtonMode="while-editing"
          onChangeText={onChange}
          onFocus={() => onFocus(field)}
          placeholder="Search TAMU buildings"
          placeholderTextColor="#9A9087"
          returnKeyType="search"
          selectTextOnFocus
          style={styles.searchInput}
          value={value}
        />
      </View>
    </View>
  );
}

export default function App() {
  const mapRef = useRef<MapView>(null);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [originId, setOriginId] = useState<string | null>(null);
  const [destinationId, setDestinationId] = useState<string | null>(null);
  const [originQuery, setOriginQuery] = useState("");
  const [destinationQuery, setDestinationQuery] = useState("");
  const [activeField, setActiveField] = useState<SearchField>("destination");
  const [route, setRoute] = useState<Route | null>(null);
  const [loading, setLoading] = useState(true);
  const [routing, setRouting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [treeShadowMap, setTreeShadowMap] = useState<TreeShadowMap | null>(null);
  const [shadeLoading, setShadeLoading] = useState(true);
  const [shadeError, setShadeError] = useState(false);

  useEffect(() => {
    getBuildings()
      .then((items) => {
        setBuildings(items);
        setOriginId(items[0]?.id ?? null);
        setDestinationId(items[1]?.id ?? null);
        setOriginQuery(items[0]?.name ?? "");
        setDestinationQuery(items[1]?.name ?? "");
      })
      .catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : "Could not load campus buildings");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    let active = true;
    let refreshTimer: ReturnType<typeof setInterval> | undefined;

    async function refreshShadows() {
      try {
        const result = await getTreeShadowMap(new Date());
        if (active) {
          setTreeShadowMap(result);
          setShadeError(false);
        }
      } catch {
        if (active) {
          setTreeShadowMap(null);
          setShadeError(true);
        }
      } finally {
        if (active) setShadeLoading(false);
      }
    }

    const interactionTask = InteractionManager.runAfterInteractions(() => {
      void refreshShadows();
      refreshTimer = setInterval(() => void refreshShadows(), 15 * 60 * 1_000);
    });
    return () => {
      active = false;
      interactionTask.cancel();
      if (refreshTimer) clearInterval(refreshTimer);
    };
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
  const commonPlaces = useMemo(
    () =>
      COMMON_PLACE_IDS.map((id) => buildings.find((building) => building.id === id)).filter(
        (building): building is Building => Boolean(building),
      ),
    [buildings],
  );
  const activeQuery = activeField === "origin" ? originQuery : destinationQuery;
  const matchingBuildings = useMemo(
    () =>
      buildings
        .map((building) => ({ building, score: buildingMatchScore(building, activeQuery) }))
        .filter((match): match is { building: Building; score: number } => match.score !== null)
        .sort(
          (left, right) =>
            left.score - right.score || left.building.name.localeCompare(right.building.name),
        )
        .map((match) => match.building),
    [activeQuery, buildings],
  );
  const searchResults = matchingBuildings.slice(0, 8);
  const shadeStatus = formatShadeStatus(shadeLoading, shadeError, treeShadowMap);

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

  function updateQuery(field: SearchField, value: string) {
    setActiveField(field);
    setRoute(null);
    setError(null);
    if (field === "origin") {
      setOriginQuery(value);
      setOriginId(null);
    } else {
      setDestinationQuery(value);
      setDestinationId(null);
    }
  }

  function selectBuilding(building: Building, field: SearchField = activeField) {
    setRoute(null);
    setError(null);
    if (field === "origin") {
      setOriginId(building.id);
      setOriginQuery(building.name);
      if (building.id === destinationId) {
        setDestinationId(null);
        setDestinationQuery("");
      }
    } else {
      setDestinationId(building.id);
      setDestinationQuery(building.name);
      if (building.id === originId) {
        setOriginId(null);
        setOriginQuery("");
      }
    }
  }

  const activeSelectionId = activeField === "origin" ? originId : destinationId;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>TEXAS A&M CAMPUS</Text>
          <Text style={styles.title}>AggieShade</Text>
        </View>
        <View style={styles.milestoneBadge}>
          <Text style={styles.milestoneText}>WALKING ROUTES</Text>
        </View>
      </View>

      <View style={styles.content}>
        <View style={styles.mapShell}>
          <MapView ref={mapRef} style={styles.map} initialRegion={TAMU_REGION}>
            {treeShadowMap?.shadow_count ? <ShadowOverlay geojson={treeShadowMap.geojson} /> : null}
            {selectedBuildings.map((building) => (
              <Marker
                key={building.id}
                coordinate={building.route_point}
                title={building.short_name}
                description={building.name}
                pinColor={building.id === originId ? GREEN : MAROON}
                zIndex={5}
              />
            ))}
            {route && (
              <Polyline
                coordinates={route.geometry}
                strokeColor={MAROON}
                strokeWidth={6}
                lineCap="round"
                zIndex={4}
              />
            )}
          </MapView>
          {route && (
            <View style={styles.routeCard}>
              <Text style={styles.routeCardLabel}>PEDESTRIAN ROUTE</Text>
              <Text style={styles.routeCardValue}>
                {formatDuration(route.duration_seconds)} · {formatDistance(route.distance_m)}
              </Text>
            </View>
          )}
          <View pointerEvents="none" style={styles.shadeCard}>
            {shadeLoading ? (
              <ActivityIndicator color={GREEN} size="small" />
            ) : (
              <View
                style={[
                  styles.shadeDot,
                  (shadeError || !treeShadowMap?.daylight) && styles.shadeDotInactive,
                ]}
              />
            )}
            <Text numberOfLines={1} style={styles.shadeText}>
              {shadeStatus}
            </Text>
          </View>
        </View>

        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          keyboardVerticalOffset={0}
          style={styles.selectionArea}
        >
          {loading ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={MAROON} />
              <Text style={styles.muted}>Loading campus buildings…</Text>
            </View>
          ) : (
            <>
              <ScrollView
                contentContainerStyle={styles.panel}
                keyboardDismissMode="interactive"
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
                style={styles.panelScroll}
              >
                <View style={styles.sectionHeading}>
                  <Text style={styles.sectionTitle}>Plan your walk</Text>
                  <Text style={styles.sectionHint}>{buildings.length} campus buildings</Text>
                </View>

                <SearchInput
                  active={activeField === "origin"}
                  field="origin"
                  label="Starting point"
                  onChange={(value) => updateQuery("origin", value)}
                  onFocus={setActiveField}
                  value={originQuery}
                />
                <SearchInput
                  active={activeField === "destination"}
                  field="destination"
                  label="Destination"
                  onChange={(value) => updateQuery("destination", value)}
                  onFocus={setActiveField}
                  value={destinationQuery}
                />

                {activeQuery.trim() && !activeSelectionId && (
                  <View style={styles.resultsSection}>
                    <Text style={styles.resultsLabel}>
                      {matchingBuildings.length} {matchingBuildings.length === 1 ? "match" : "matches"} for{" "}
                      {activeField === "origin" ? "starting point" : "destination"}
                    </Text>
                    {searchResults.length ? (
                      searchResults.map((building) => (
                        <Pressable
                          accessibilityRole="button"
                          key={building.id}
                          onPress={() => selectBuilding(building)}
                          style={({ pressed }) => [styles.resultRow, pressed && styles.pressed]}
                        >
                          <View style={styles.resultPin} />
                          <View style={styles.resultCopy}>
                            <Text numberOfLines={1} style={styles.resultName}>
                              {building.name}
                            </Text>
                            <Text numberOfLines={1} style={styles.resultDescription}>
                              {buildingDetails(building)}
                            </Text>
                          </View>
                          <Text style={styles.resultAction}>Choose</Text>
                        </Pressable>
                      ))
                    ) : (
                      <Text style={styles.noResults}>No matching campus buildings</Text>
                    )}
                  </View>
                )}

                <View style={styles.commonSection}>
                  <View style={styles.commonHeading}>
                    <Text style={styles.commonTitle}>Common places</Text>
                    <Text style={styles.commonTarget}>
                      Choosing for {activeField === "origin" ? "Start" : "Destination"}
                    </Text>
                  </View>
                  <ScrollView
                    horizontal
                    showsHorizontalScrollIndicator={false}
                    contentContainerStyle={styles.chipRow}
                    keyboardShouldPersistTaps="handled"
                  >
                    {commonPlaces.map((building) => {
                      const selected = building.id === activeSelectionId;
                      return (
                        <Pressable
                          accessibilityRole="button"
                          accessibilityState={{ selected }}
                          key={building.id}
                          onPress={() => selectBuilding(building)}
                          style={[styles.chip, selected && styles.chipSelected]}
                        >
                          <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
                            {building.short_name}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </ScrollView>
                </View>
              </ScrollView>

              <View style={styles.actionArea}>
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
                  {routing ? (
                    <ActivityIndicator color="white" />
                  ) : (
                    <Text style={styles.routeButtonText}>Find Route</Text>
                  )}
                </Pressable>
              </View>
            </>
          )}
        </KeyboardAvoidingView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#F8F6F1" },
  content: { flex: 1 },
  header: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  eyebrow: { color: GREEN, fontSize: 10, fontWeight: "700", letterSpacing: 1.4 },
  title: { color: MAROON, fontSize: 28, fontWeight: "800", letterSpacing: -0.7 },
  milestoneBadge: {
    borderColor: "#D7C8B9",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  milestoneText: { color: "#6F6258", fontSize: 9, fontWeight: "700", letterSpacing: 0.7 },
  mapShell: {
    height: "38%",
    minHeight: 205,
    marginHorizontal: 14,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "#E8E3D8",
  },
  map: { flex: 1 },
  routeCard: {
    position: "absolute",
    top: 12,
    left: 12,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderRadius: 13,
    paddingHorizontal: 13,
    paddingVertical: 9,
  },
  routeCardLabel: { color: GREEN, fontSize: 9, fontWeight: "800", letterSpacing: 1 },
  routeCardValue: { color: MAROON, fontSize: 17, fontWeight: "800", marginTop: 2 },
  shadeCard: {
    position: "absolute",
    right: 10,
    bottom: 10,
    left: 10,
    minHeight: 30,
    borderRadius: 10,
    paddingHorizontal: 10,
    backgroundColor: "rgba(255,255,255,0.94)",
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
  },
  shadeDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: GREEN },
  shadeDotInactive: { backgroundColor: "#9A9087" },
  shadeText: { flex: 1, color: "#4B433D", fontSize: 10, fontWeight: "700" },
  selectionArea: { flex: 1, marginTop: 6 },
  panelScroll: { flex: 1 },
  panel: { paddingHorizontal: 16, paddingTop: 10, paddingBottom: 12, gap: 11 },
  sectionHeading: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" },
  sectionTitle: { color: "#2F2924", fontSize: 18, fontWeight: "800" },
  sectionHint: { color: "#7B7168", fontSize: 11 },
  searchGroup: { gap: 5 },
  searchLabel: { color: "#62574D", fontSize: 11, fontWeight: "700" },
  searchShell: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: "#D7C8B9",
    borderRadius: 14,
    backgroundColor: "white",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 11,
  },
  searchShellActive: { borderColor: MAROON, borderWidth: 2, paddingHorizontal: 10 },
  fieldBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 9,
  },
  originBadge: { backgroundColor: GREEN },
  destinationBadge: { backgroundColor: MAROON },
  fieldBadgeText: { color: "white", fontSize: 11, fontWeight: "800" },
  searchInput: { flex: 1, color: "#2F2924", fontSize: 15, paddingVertical: 10 },
  resultsSection: {
    borderWidth: 1,
    borderColor: "#E1D8CF",
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: "white",
  },
  resultsLabel: {
    color: "#746A62",
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
    paddingHorizontal: 12,
    paddingTop: 9,
    paddingBottom: 5,
    textTransform: "uppercase",
  },
  resultRow: {
    minHeight: 49,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#E8E1DA",
  },
  resultPin: { width: 8, height: 8, borderRadius: 4, backgroundColor: GREEN, marginRight: 10 },
  resultCopy: { flex: 1, paddingVertical: 7 },
  resultName: { color: "#332D28", fontSize: 14, fontWeight: "700" },
  resultDescription: { color: "#81766D", fontSize: 11, marginTop: 1 },
  resultAction: { color: MAROON, fontSize: 11, fontWeight: "800", marginLeft: 8 },
  noResults: { color: "#81766D", fontSize: 13, paddingHorizontal: 12, paddingVertical: 14 },
  commonSection: { gap: 7 },
  commonHeading: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  commonTitle: { color: "#62574D", fontSize: 12, fontWeight: "800" },
  commonTarget: { color: GREEN, fontSize: 10, fontWeight: "700" },
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
  actionArea: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#DED5CC",
    backgroundColor: "#F8F6F1",
    gap: 6,
  },
  loadingRow: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10 },
  muted: { color: "#746A62" },
  error: { color: "#A32626", fontSize: 12 },
  routeButton: {
    minHeight: 48,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: MAROON,
  },
  routeButtonDisabled: { opacity: 0.45 },
  routeButtonText: { color: "white", fontSize: 15, fontWeight: "800" },
  pressed: { opacity: 0.75 },
});
