import { memo, type RefObject, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  InteractionManager,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { Gesture, GestureDetector, GestureHandlerRootView } from "react-native-gesture-handler";
import MapView, { Geojson, Marker, Polyline } from "react-native-maps";
import Animated, {
  cancelAnimation,
  Easing,
  runOnJS,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { getBuildings, getBuildingShadowMap, getRoute, getTreeShadowMap } from "./src/api";
import type {
  Building,
  BuildingShadowGeoJson,
  BuildingShadowMap,
  Route,
  TreeShadowGeoJson,
  TreeShadowMap,
} from "./src/types";

const MAROON = "#500000";
const GREEN = "#287052";
const SHEET_TOP = 68;
const SHEET_PEEK_HEIGHT = 380;
const SHEET_MINIMIZED_HEIGHT = 92;
const SHEET_BOTTOM_OVERSCAN = 128;
const SHEET_TRANSITION_DURATION = 264;
const COMMON_PLACE_IDS = ["msc", "evans", "zachry", "kyle", "academic", "sbisa"];
const ABSOLUTE_FILL = { position: "absolute" as const, top: 0, right: 0, bottom: 0, left: 0 };
const TAMU_REGION = {
  latitude: 30.6168,
  longitude: -96.3411,
  latitudeDelta: 0.014,
  longitudeDelta: 0.012,
};

type SearchField = "origin" | "destination";

type TreeShadowOverlayProps = {
  geojson: TreeShadowGeoJson;
};

const TreeShadowOverlay = memo(function TreeShadowOverlay({ geojson }: TreeShadowOverlayProps) {
  return (
    <Geojson
      fillColor="rgba(35, 86, 64, 0.22)"
      geojson={geojson}
      strokeColor="rgba(35, 86, 64, 0.38)"
      strokeWidth={0.5}
      tappable={false}
      zIndex={2}
    />
  );
});

type BuildingShadowOverlayProps = {
  geojson: BuildingShadowGeoJson;
};

const BuildingShadowOverlay = memo(function BuildingShadowOverlay({
  geojson,
}: BuildingShadowOverlayProps) {
  return (
    <Geojson
      fillColor="rgba(76, 72, 91, 0.25)"
      geojson={geojson}
      strokeColor="rgba(76, 72, 91, 0.42)"
      strokeWidth={0.65}
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
  expanded: boolean;
  field: SearchField;
  inputRef: RefObject<TextInput | null>;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onFocus: (field: SearchField) => void;
  onOpen: (field: SearchField) => void;
};

function SearchInput({
  active,
  expanded,
  field,
  inputRef,
  label,
  value,
  onChange,
  onFocus,
  onOpen,
}: SearchInputProps) {
  return (
    <View style={styles.searchGroup}>
      <Text style={styles.searchLabel}>{label}</Text>
      <View style={[styles.searchShell, active && styles.searchShellActive]}>
        <View style={[styles.fieldBadge, field === "origin" ? styles.originBadge : styles.destinationBadge]}>
          <Text style={styles.fieldBadgeText}>{field === "origin" ? "A" : "B"}</Text>
        </View>
        <TextInput
          accessibilityLabel={`Search ${label.toLocaleLowerCase()}`}
          accessible={expanded}
          autoCorrect={false}
          clearButtonMode="while-editing"
          editable={expanded}
          onChangeText={onChange}
          onFocus={() => onFocus(field)}
          placeholder="Search TAMU buildings"
          placeholderTextColor="#9A9087"
          returnKeyType="search"
          ref={inputRef}
          selectTextOnFocus
          style={styles.searchInput}
          value={value}
        />
        {!expanded && (
          <Pressable
            accessibilityLabel={`Edit ${label.toLocaleLowerCase()}`}
            accessibilityRole="button"
            onPress={() => onOpen(field)}
            style={styles.searchOpenTarget}
          />
        )}
      </View>
    </View>
  );
}

type SearchResultsProps = {
  field: SearchField;
  matchingBuildings: Building[];
  onSelect: (building: Building) => void;
  query: string;
  results: Building[];
};

function SearchResults({
  field,
  matchingBuildings,
  onSelect,
  query,
  results,
}: SearchResultsProps) {
  if (!query.trim()) return null;
  return (
    <View style={styles.resultsSection}>
      <Text style={styles.resultsLabel}>
        {matchingBuildings.length} {matchingBuildings.length === 1 ? "match" : "matches"} for{" "}
        {field === "origin" ? "starting point" : "destination"}
      </Text>
      {results.length ? (
        results.map((building) => (
          <Pressable
            accessibilityHint={`Sets the ${field === "origin" ? "starting point" : "destination"}`}
            accessibilityRole="button"
            key={building.id}
            onPress={() => onSelect(building)}
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
          </Pressable>
        ))
      ) : (
        <Text style={styles.noResults}>No matching campus buildings</Text>
      )}
    </View>
  );
}

export default function App() {
  const { height: windowHeight } = useWindowDimensions();
  const estimatedSheetHeight = Math.max(
    SHEET_PEEK_HEIGHT + SHEET_BOTTOM_OVERSCAN,
    windowHeight - SHEET_TOP + SHEET_BOTTOM_OVERSCAN,
  );
  const estimatedCollapsedOffset = Math.max(
    0,
    estimatedSheetHeight - SHEET_BOTTOM_OVERSCAN - SHEET_PEEK_HEIGHT,
  );
  const mapRef = useRef<MapView>(null);
  const originInputRef = useRef<TextInput>(null);
  const destinationInputRef = useRef<TextInput>(null);
  const sheetTranslateY = useSharedValue(estimatedCollapsedOffset);
  const sheetDragStart = useSharedValue(estimatedCollapsedOffset);
  const sheetScrollOffset = useSharedValue(0);
  const sheetGestureOffset = useSharedValue(0);
  const sheetWasDragged = useSharedValue(false);
  const pendingFocusRef = useRef<SearchField | null>(null);
  const routeRequestIdRef = useRef(0);
  const [sheetHeight, setSheetHeight] = useState(0);
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
  const [buildingShadowMap, setBuildingShadowMap] = useState<BuildingShadowMap | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [lobbyMinimized, setLobbyMinimized] = useState(false);
  const collapsedOffset = Math.max(
    0,
    (sheetHeight || estimatedSheetHeight) - SHEET_BOTTOM_OVERSCAN - SHEET_PEEK_HEIGHT,
  );
  const minimizedOffset = Math.max(
    collapsedOffset,
    (sheetHeight || estimatedSheetHeight) - SHEET_BOTTOM_OVERSCAN - SHEET_MINIMIZED_HEIGHT,
  );

  const loadCampusBuildings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await getBuildings();
      setBuildings(items);
      setOriginId(items[0]?.id ?? null);
      setDestinationId(items[1]?.id ?? null);
      setOriginQuery(items[0]?.name ?? "");
      setDestinationQuery(items[1]?.name ?? "");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Could not load campus buildings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCampusBuildings();
  }, [loadCampusBuildings]);

  useEffect(() => {
    if (!searchOpen) {
      sheetTranslateY.value = lobbyMinimized ? minimizedOffset : collapsedOffset;
    }
  }, [collapsedOffset, lobbyMinimized, minimizedOffset, searchOpen, sheetTranslateY]);

  useEffect(() => {
    if (!searchOpen) return;
    sheetTranslateY.value = withTiming(0, {
      duration: SHEET_TRANSITION_DURATION,
      easing: Easing.out(Easing.cubic),
    }, (finished) => {
      if (!finished) return;
      runOnJS(focusPendingInput)();
    });

    function focusPendingInput() {
      const field = pendingFocusRef.current;
      pendingFocusRef.current = null;
      if (!field) return;
      const inputRef = field === "origin" ? originInputRef : destinationInputRef;
      requestAnimationFrame(() => inputRef.current?.focus());
    }

    return () => cancelAnimation(sheetTranslateY);
  }, [searchOpen, sheetTranslateY]);

  useEffect(() => {
    let active = true;
    let refreshTimer: ReturnType<typeof setInterval> | undefined;

    async function refreshShadows() {
      const requestedAt = new Date();
      const [treeResult, buildingResult] = await Promise.allSettled([
        getTreeShadowMap(requestedAt),
        getBuildingShadowMap(requestedAt),
      ]);
      if (!active) return;

      if (treeResult.status === "fulfilled") {
        setTreeShadowMap(treeResult.value);
      } else {
        setTreeShadowMap(null);
      }

      if (buildingResult.status === "fulfilled") {
        setBuildingShadowMap(buildingResult.value);
      } else {
        setBuildingShadowMap(null);
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
        edgePadding: { top: 150, right: 48, bottom: SHEET_MINIMIZED_HEIGHT + 24, left: 48 },
        animated: true,
      });
    }
  }, [route]);

  const canRoute = Boolean(originId && destinationId && originId !== destinationId && !routing);
  const originBuilding = useMemo(
    () => buildings.find((building) => building.id === originId) ?? null,
    [buildings, originId],
  );
  const destinationBuilding = useMemo(
    () => buildings.find((building) => building.id === destinationId) ?? null,
    [buildings, destinationId],
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
  async function requestRoute() {
    if (!originId || !destinationId || originId === destinationId) return;
    const requestId = routeRequestIdRef.current + 1;
    routeRequestIdRef.current = requestId;
    minimizeSheet();
    setRouting(true);
    setError(null);
    try {
      const nextRoute = await getRoute(originId, destinationId, "shadiest", new Date());
      if (requestId === routeRequestIdRef.current) setRoute(nextRoute);
    } catch (requestError: unknown) {
      if (requestId === routeRequestIdRef.current) {
        setError(requestError instanceof Error ? requestError.message : "Could not calculate the route");
      }
    } finally {
      if (requestId === routeRequestIdRef.current) setRouting(false);
    }
  }

  function updateQuery(field: SearchField, value: string) {
    routeRequestIdRef.current += 1;
    setRouting(false);
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

  function dismissKeyboard() {
    originInputRef.current?.blur();
    destinationInputRef.current?.blur();
    Keyboard.dismiss();
  }

  function expandSheet(field?: SearchField) {
    if (field) setActiveField(field);
    setLobbyMinimized(false);
    cancelAnimation(sheetTranslateY);
    if (!searchOpen) {
      pendingFocusRef.current = field ?? null;
      setSearchOpen(true);
      return;
    }
    if (field) pendingFocusRef.current = null;
    sheetTranslateY.value = withTiming(0, {
      duration: SHEET_TRANSITION_DURATION,
      easing: Easing.out(Easing.cubic),
    });
  }

  function openSearch(field: SearchField) {
    expandSheet(field);
  }

  function closeSearch() {
    dismissKeyboard();
    pendingFocusRef.current = null;
    setLobbyMinimized(false);
    cancelAnimation(sheetTranslateY);
    sheetTranslateY.value = withTiming(collapsedOffset, {
      duration: SHEET_TRANSITION_DURATION,
      easing: Easing.out(Easing.cubic),
    }, (finished) => {
      if (finished) {
        sheetScrollOffset.value = 0;
        runOnJS(setSearchOpen)(false);
      }
    });
  }

  function minimizeSheet() {
    dismissKeyboard();
    pendingFocusRef.current = null;
    setLobbyMinimized(true);
    cancelAnimation(sheetTranslateY);
    sheetTranslateY.value = withTiming(minimizedOffset, {
      duration: SHEET_TRANSITION_DURATION,
      easing: Easing.out(Easing.cubic),
    }, (finished) => {
      if (finished) {
        sheetScrollOffset.value = 0;
        runOnJS(setSearchOpen)(false);
      }
    });
  }

  function selectBuilding(building: Building, field: SearchField = activeField) {
    routeRequestIdRef.current += 1;
    setRouting(false);
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

  const resultsScrollGesture = useMemo(() => Gesture.Native(), []);
  const sheetGesture = useMemo(
    () =>
      Gesture.Pan()
        .activeOffsetY([-5, 5])
        .failOffsetX([-12, 12])
        .simultaneousWithExternalGesture(resultsScrollGesture)
        .onBegin(() => {
          cancelAnimation(sheetTranslateY);
          sheetDragStart.value = sheetTranslateY.value;
          sheetGestureOffset.value = 0;
          sheetWasDragged.value = false;
        })
        .onUpdate((gesture) => {
          if (searchOpen && sheetScrollOffset.value > 0) {
            sheetGestureOffset.value = gesture.translationY;
            return;
          }
          sheetWasDragged.value = true;
          const dragDistance = gesture.translationY - sheetGestureOffset.value;
          const nextPosition = sheetDragStart.value + dragDistance;
          sheetTranslateY.value = Math.max(0, Math.min(minimizedOffset, nextPosition));
        })
        .onEnd((gesture) => {
          if (!sheetWasDragged.value) return;
          const movingUp = gesture.velocityY < -350;
          const movingDown = gesture.velocityY > 350;

          if (!searchOpen) {
            const startedMinimized = sheetDragStart.value > collapsedOffset + 24;
            const belowLobbyMidpoint =
              sheetTranslateY.value > (collapsedOffset + minimizedOffset) * 0.5;

            if (movingDown || (!movingUp && belowLobbyMidpoint)) {
              runOnJS(setLobbyMinimized)(true);
              sheetTranslateY.value = withTiming(minimizedOffset, {
                duration: SHEET_TRANSITION_DURATION,
                easing: Easing.out(Easing.cubic),
              });
            } else if (startedMinimized) {
              runOnJS(setLobbyMinimized)(false);
              sheetTranslateY.value = withTiming(collapsedOffset, {
                duration: SHEET_TRANSITION_DURATION,
                easing: Easing.out(Easing.cubic),
              });
            } else {
              runOnJS(expandSheet)();
            }
            return;
          }

          const aboveMidpoint = sheetTranslateY.value < collapsedOffset * 0.5;
          if (movingUp || (!movingDown && aboveMidpoint)) {
            runOnJS(expandSheet)();
          } else {
            runOnJS(closeSearch)();
          }
        }),
    [
      collapsedOffset,
      minimizedOffset,
      resultsScrollGesture,
      searchOpen,
      sheetDragStart,
      sheetGestureOffset,
      sheetScrollOffset,
      sheetTranslateY,
      sheetWasDragged,
    ],
  );

  const sheetAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: sheetTranslateY.value }],
  }));
  const resultsScrollHandler = useAnimatedScrollHandler((event) => {
    sheetScrollOffset.value = event.contentOffset.y;
  });

  const activeSelectionId = activeField === "origin" ? originId : destinationId;

  return (
    <GestureHandlerRootView style={styles.appRoot}>
      <StatusBar backgroundColor="transparent" barStyle="dark-content" translucent />
      <MapView
        initialRegion={TAMU_REGION}
        onPress={minimizeSheet}
        ref={mapRef}
        style={styles.map}
      >
        {buildingShadowMap?.shadow_count ? (
          <BuildingShadowOverlay geojson={buildingShadowMap.geojson} />
        ) : null}
        {treeShadowMap?.shadow_count ? (
          <TreeShadowOverlay geojson={treeShadowMap.geojson} />
        ) : null}
        <Polyline
          coordinates={route?.geometry ?? []}
          strokeColor="rgba(255,255,255,0.96)"
          strokeWidth={9}
          lineCap="round"
          lineJoin="round"
          zIndex={20}
        />
        <Polyline
          coordinates={route?.geometry ?? []}
          strokeColor={MAROON}
          strokeWidth={5}
          lineCap="round"
          lineJoin="round"
          zIndex={21}
        />
        <Marker
          key="origin-marker"
          coordinate={originBuilding?.route_point ?? TAMU_REGION}
          title={originBuilding?.short_name}
          description={originBuilding?.name}
          opacity={originBuilding ? 1 : 0}
          pinColor={GREEN}
          zIndex={30}
        />
        <Marker
          key="destination-marker"
          coordinate={destinationBuilding?.route_point ?? TAMU_REGION}
          title={destinationBuilding?.short_name}
          description={destinationBuilding?.name}
          opacity={destinationBuilding ? 1 : 0}
          pinColor={MAROON}
          zIndex={31}
        />
      </MapView>

      <SafeAreaView pointerEvents="box-none" style={styles.safeAreaOverlay}>
        <View pointerEvents="box-none" style={styles.content}>
          <View pointerEvents="none" style={styles.header}>
            <View>
              <Text style={styles.eyebrow}>TEXAS A&M CAMPUS</Text>
              <Text style={styles.title}>AggieShade</Text>
            </View>
          </View>

          {route && (
            <View pointerEvents="none" style={styles.routeCard}>
              <Text style={styles.routeCardLabel}>SHADIEST ROUTE</Text>
              <Text style={styles.routeCardValue}>
                {formatDuration(route.duration_seconds)} · {formatDistance(route.distance_m)}
              </Text>
              <Text style={styles.routeCardShade}>
                {route.daylight
                  ? `${route.shade_percentage.toFixed(0)}% shaded · ${formatDistance(route.shaded_distance_m)} in shade`
                  : "Nighttime · shade routing inactive"}
              </Text>
            </View>
          )}

          <GestureDetector gesture={sheetGesture}>
            <Animated.View
              onLayout={(event) => setSheetHeight(event.nativeEvent.layout.height)}
              style={[styles.selectionArea, sheetAnimatedStyle]}
            >
            <View style={styles.sheetDragArea}>
              <Pressable
                accessibilityHint={searchOpen ? "Returns to the map" : "Shows places and search results"}
                accessibilityLabel={searchOpen ? "Collapse route planner" : "Expand route planner"}
                accessibilityRole="button"
                onPress={() => (searchOpen ? closeSearch() : expandSheet())}
                style={({ pressed }) => [styles.sheetHeaderButton, pressed && styles.sheetHeaderPressed]}
              >
                <View style={styles.sheetHandle} />
                <View style={styles.sheetHeadingRow}>
                  <View>
                    <Text style={styles.sheetEyebrow}>ROUTE PLANNER</Text>
                    <Text style={styles.sheetTitle}>Plan your walk</Text>
                  </View>
                </View>
              </Pressable>
            </View>

            <KeyboardAvoidingView
              behavior={Platform.OS === "ios" ? "padding" : undefined}
              enabled={Platform.OS === "ios"}
              keyboardVerticalOffset={0}
              pointerEvents="box-none"
              style={styles.keyboardPanel}
            >
              {loading ? (
                <View style={styles.loadingRow}>
                  <ActivityIndicator color={MAROON} />
                  <Text style={styles.muted}>Loading campus buildings…</Text>
                </View>
              ) : (
                <>
                  <View style={styles.routeForm}>
                    <SearchInput
                      active={activeField === "origin"}
                      expanded={searchOpen}
                      field="origin"
                      inputRef={originInputRef}
                      label="Starting point"
                      onChange={(value) => updateQuery("origin", value)}
                      onFocus={openSearch}
                      onOpen={openSearch}
                      value={originQuery}
                    />
                    <SearchInput
                      active={activeField === "destination"}
                      expanded={searchOpen}
                      field="destination"
                      inputRef={destinationInputRef}
                      label="Destination"
                      onChange={(value) => updateQuery("destination", value)}
                      onFocus={openSearch}
                      onOpen={openSearch}
                      value={destinationQuery}
                    />

                    <View style={styles.actionArea}>
                      {error && <Text numberOfLines={2} style={styles.error}>{error}</Text>}
                      <View style={styles.actionButtons}>
                        {!buildings.length && error ? (
                          <Pressable
                            accessibilityRole="button"
                            onPress={() => void loadCampusBuildings()}
                            style={({ pressed }) => [styles.routeButton, pressed && styles.pressed]}
                          >
                            <Text style={styles.routeButtonText}>Retry Connection</Text>
                          </Pressable>
                        ) : (
                          <>
                            {searchOpen && (
                              <Pressable
                                accessibilityRole="button"
                                onPress={closeSearch}
                                style={({ pressed }) => [styles.doneButton, pressed && styles.pressed]}
                              >
                                <Text style={styles.doneButtonText}>Done</Text>
                              </Pressable>
                            )}
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
                          </>
                        )}
                      </View>
                    </View>
                  </View>

                  {searchOpen && (
                    <GestureDetector gesture={resultsScrollGesture}>
                    <Animated.ScrollView
                      contentContainerStyle={styles.expandedContent}
                      keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
                      keyboardShouldPersistTaps="handled"
                      onScroll={resultsScrollHandler}
                      scrollEventThrottle={16}
                      showsVerticalScrollIndicator={false}
                      style={styles.panelScroll}
                    >
                      <View style={styles.commonSection}>
                        <View style={styles.commonHeading}>
                          <Text style={styles.commonTitle}>Common Places</Text>
                          <Text style={styles.commonTarget}>
                            For {activeField === "origin" ? "Start" : "Destination"}
                          </Text>
                        </View>
                        <ScrollView
                          horizontal
                          contentContainerStyle={styles.chipRow}
                          keyboardShouldPersistTaps="handled"
                          showsHorizontalScrollIndicator={false}
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

                      <SearchResults
                        field={activeField}
                        matchingBuildings={matchingBuildings}
                        onSelect={(building) => selectBuilding(building, activeField)}
                        query={activeQuery}
                        results={searchResults}
                      />
                      <Pressable
                        accessibilityElementsHidden
                        importantForAccessibility="no-hide-descendants"
                        onPress={dismissKeyboard}
                        style={styles.dismissArea}
                      />
                    </Animated.ScrollView>
                    </GestureDetector>
                  )}
                </>
              )}
            </KeyboardAvoidingView>
            </Animated.View>
          </GestureDetector>
        </View>
      </SafeAreaView>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  appRoot: { flex: 1, backgroundColor: "#E8E3D8" },
  safeAreaOverlay: { ...ABSOLUTE_FILL },
  content: { flex: 1 },
  map: { ...ABSOLUTE_FILL },
  header: {
    position: "absolute",
    top: 8,
    left: 14,
    zIndex: 10,
    minHeight: 58,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(80,0,0,0.14)",
    borderRadius: 18,
    backgroundColor: "rgba(255,255,255,0.95)",
    alignItems: "center",
    shadowColor: "#2F2924",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.14,
    shadowRadius: 10,
    elevation: 5,
  },
  eyebrow: { color: GREEN, fontSize: 10, fontWeight: "700", letterSpacing: 1.4 },
  title: { color: MAROON, fontSize: 24, fontWeight: "800", letterSpacing: -0.6 },
  routeCard: {
    position: "absolute",
    top: 78,
    left: 14,
    zIndex: 9,
    backgroundColor: "rgba(255,255,255,0.96)",
    borderRadius: 14,
    paddingHorizontal: 13,
    paddingVertical: 9,
    minWidth: 190,
    shadowColor: "#2F2924",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 7,
    elevation: 4,
  },
  routeCardLabel: { color: GREEN, fontSize: 9, fontWeight: "800", letterSpacing: 1 },
  routeCardValue: { color: MAROON, fontSize: 17, fontWeight: "800", marginTop: 2 },
  routeCardShade: { color: "#62574D", fontSize: 11, fontWeight: "700", marginTop: 3 },
  selectionArea: {
    position: "absolute",
    top: SHEET_TOP,
    right: 0,
    bottom: -SHEET_BOTTOM_OVERSCAN,
    left: 0,
    zIndex: 100,
    elevation: 20,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    backgroundColor: "#F8F6F1",
    shadowColor: "#2F2924",
    shadowOffset: { width: 0, height: -5 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
  },
  sheetDragArea: { borderTopLeftRadius: 28, borderTopRightRadius: 28 },
  sheetHeaderButton: {
    minHeight: 68,
    paddingTop: 9,
    paddingHorizontal: 18,
    paddingBottom: 8,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
  },
  sheetHeaderPressed: { backgroundColor: "rgba(80,0,0,0.035)" },
  sheetHandle: {
    alignSelf: "center",
    width: 46,
    height: 5,
    borderRadius: 999,
    backgroundColor: "#C9C0B8",
  },
  sheetHeadingRow: {
    marginTop: 7,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sheetEyebrow: { color: GREEN, fontSize: 9, fontWeight: "800", letterSpacing: 1.1 },
  sheetTitle: { marginTop: 1, color: "#2F2924", fontSize: 23, fontWeight: "800", letterSpacing: -0.5 },
  keyboardPanel: { flex: 1 },
  routeForm: { paddingHorizontal: 16, paddingTop: 3, paddingBottom: 8, gap: 8 },
  panelScroll: { flex: 1 },
  expandedContent: {
    flexGrow: 1,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 30,
    gap: 12,
  },
  searchGroup: { gap: 3 },
  searchLabel: { color: "#62574D", fontSize: 11, fontWeight: "700" },
  searchShell: {
    minHeight: 46,
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
  searchOpenTarget: { ...ABSOLUTE_FILL, zIndex: 1, borderRadius: 14 },
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
  dismissArea: { flex: 1, minHeight: 40 },
  actionArea: { gap: 5 },
  actionButtons: { flexDirection: "row", gap: 8 },
  doneButton: {
    minHeight: 46,
    borderWidth: 1,
    borderColor: MAROON,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18,
    backgroundColor: "white",
  },
  doneButtonText: { color: MAROON, fontSize: 14, fontWeight: "800" },
  loadingRow: {
    height: SHEET_PEEK_HEIGHT - 68,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
  },
  muted: { color: "#746A62" },
  error: { color: "#A32626", fontSize: 11, lineHeight: 14 },
  routeButton: {
    flex: 1,
    minHeight: 46,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: MAROON,
  },
  routeButtonDisabled: { opacity: 0.45 },
  routeButtonText: { color: "white", fontSize: 15, fontWeight: "800" },
  pressed: { opacity: 0.75 },
});
