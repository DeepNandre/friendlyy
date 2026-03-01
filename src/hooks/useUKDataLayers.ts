/**
 * useUKDataLayers - Hooks for fetching UK crime and food hygiene data
 *
 * Per architecture decisions:
 * - Issue 3A: Fetch from frontend directly (no backend proxy)
 * - Issue 7A: Always fetch latest available date from /crimes-street-dates
 * - Issue 12A: Use React Query for caching (staleTime: 5 min)
 */

import { useQuery } from "@tanstack/react-query";

// ==================== Types ====================

export interface CrimePoint {
  category: string;
  latitude: number;
  longitude: number;
  street?: string;
  month: string;
}

export interface CrimeData {
  total: number;
  byCategory: Record<string, number>;
  points: CrimePoint[];
}

export interface FoodEstablishment {
  name: string;
  rating: string; // "0" - "5" or "Pass" / "Exempt"
  ratingDate?: string;
  address?: string;
  latitude: number;
  longitude: number;
  businessType?: string;
}

export interface FoodHygieneData {
  total: number;
  avgRating: number;
  establishments: FoodEstablishment[];
}

// ==================== API Fetchers ====================

/**
 * Fetch the latest available crime data month from UK Police API
 */
async function fetchLatestCrimeDate(): Promise<string> {
  const response = await fetch("https://data.police.uk/api/crimes-street-dates");

  if (!response.ok) {
    throw new Error(`Crime dates API error: ${response.status}`);
  }

  const dates = await response.json();
  // dates is array like [{ "date": "2024-09" }, ...] - first is latest
  if (!dates || dates.length === 0) {
    throw new Error("No crime data dates available");
  }

  return dates[0].date;
}

/**
 * Fetch street-level crime data near a location
 */
async function fetchCrimeData(lat: number, lng: number): Promise<CrimeData> {
  // First get the latest available month (Issue 7A)
  const latestDate = await fetchLatestCrimeDate();

  const url = `https://data.police.uk/api/crimes-street/all-crime?lat=${lat}&lng=${lng}&date=${latestDate}`;
  const response = await fetch(url);

  // Handle 503 (too many results) gracefully
  if (response.status === 503) {
    console.warn("[CrimeData] Too many results, returning empty");
    return { total: 0, byCategory: {}, points: [] };
  }

  if (!response.ok) {
    throw new Error(`Crime API error: ${response.status}`);
  }

  const crimes = await response.json();

  // Parse and aggregate data
  const byCategory: Record<string, number> = {};
  const points: CrimePoint[] = [];

  for (const crime of crimes) {
    const category = crime.category || "other";
    byCategory[category] = (byCategory[category] || 0) + 1;

    const crimeLat = parseFloat(crime.location?.latitude);
    const crimeLng = parseFloat(crime.location?.longitude);

    if (!isNaN(crimeLat) && !isNaN(crimeLng)) {
      points.push({
        category,
        latitude: crimeLat,
        longitude: crimeLng,
        street: crime.location?.street?.name,
        month: crime.month,
      });
    }
  }

  return {
    total: crimes.length,
    byCategory,
    points,
  };
}

/**
 * Fetch food hygiene ratings near a location
 */
async function fetchFoodHygieneData(
  lat: number,
  lng: number
): Promise<FoodHygieneData> {
  const url = new URL("https://api.ratings.food.gov.uk/Establishments");
  url.searchParams.set("longitude", lng.toString());
  url.searchParams.set("latitude", lat.toString());
  url.searchParams.set("maxDistanceLimit", "1"); // 1 mile radius
  url.searchParams.set("pageSize", "30");
  url.searchParams.set("sortOptionKey", "distance");

  const response = await fetch(url.toString(), {
    headers: {
      "x-api-version": "2", // Required header - silent fail without it
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`FSA API error: ${response.status}`);
  }

  const data = await response.json();
  const establishments: FoodEstablishment[] = [];
  let ratingSum = 0;
  let ratingCount = 0;

  for (const est of data.establishments || []) {
    const estLat = parseFloat(est.geocode?.latitude);
    const estLng = parseFloat(est.geocode?.longitude);

    if (isNaN(estLat) || isNaN(estLng)) continue;

    const rating = est.RatingValue || "Unknown";

    establishments.push({
      name: est.BusinessName || "Unknown",
      rating,
      ratingDate: est.RatingDate,
      address: [est.AddressLine1, est.PostCode].filter(Boolean).join(", "),
      latitude: estLat,
      longitude: estLng,
      businessType: est.BusinessType,
    });

    // Calculate average (only for numeric ratings)
    const numRating = parseInt(rating, 10);
    if (!isNaN(numRating) && numRating >= 0 && numRating <= 5) {
      ratingSum += numRating;
      ratingCount++;
    }
  }

  return {
    total: establishments.length,
    avgRating: ratingCount > 0 ? ratingSum / ratingCount : 0,
    establishments,
  };
}

// ==================== React Query Hooks ====================

/**
 * Hook to fetch crime data near a location
 *
 * Uses React Query with 5-minute stale time for caching (Issue 12A)
 */
export function useCrimeData(lat: number | null, lng: number | null) {
  return useQuery({
    queryKey: ["crime", lat, lng],
    queryFn: () => fetchCrimeData(lat!, lng!),
    enabled: lat !== null && lng !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes - crime data doesn't change fast
    retry: 1, // Only retry once on failure
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to fetch food hygiene data near a location
 *
 * Uses React Query with 5-minute stale time for caching (Issue 12A)
 */
export function useFoodHygieneData(lat: number | null, lng: number | null) {
  return useQuery({
    queryKey: ["foodHygiene", lat, lng],
    queryFn: () => fetchFoodHygieneData(lat!, lng!),
    enabled: lat !== null && lng !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

// ==================== Helper: Crime Category Colors ====================

export const CRIME_CATEGORY_COLORS: Record<string, string> = {
  "anti-social-behaviour": "#fbbf24", // yellow
  burglary: "#f97316", // orange
  robbery: "#ef4444", // red
  "violent-crime": "#b91c1c", // dark red
  "vehicle-crime": "#a855f7", // purple
  shoplifting: "#3b82f6", // blue
  drugs: "#22c55e", // green
  "other-theft": "#6b7280", // grey
  "public-order": "#f59e0b", // amber
  "criminal-damage-arson": "#dc2626", // red-600
  "possession-of-weapons": "#7c2d12", // dark brown
  other: "#9ca3af", // gray
};

// ==================== Helper: Food Rating Colors ====================

export function getFoodRatingColor(rating: string): string {
  switch (rating) {
    case "5":
      return "#22c55e"; // bright green
    case "4":
      return "#4ade80"; // green
    case "3":
      return "#fbbf24"; // yellow
    case "2":
      return "#f97316"; // orange
    case "1":
      return "#f97316"; // red-orange
    case "0":
      return "#ef4444"; // red
    default:
      return "#6b7280"; // grey for Pass/Exempt/Unknown
  }
}
