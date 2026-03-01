/**
 * BlitzMapCard - Interactive map showing business locations during Blitz calls
 *
 * Features:
 * - Real-time marker updates via SSE events
 * - Animated markers showing call status (ringing, connected, complete)
 * - Price labels for completed quotes
 * - Best deal highlighting
 * - Error boundary for graceful degradation (Issue 6A)
 * - Dynamic import ready for code splitting (Issue 13A)
 */

import React, { useState, useMemo, useCallback, useEffect } from "react";
import Map, { Popup, NavigationControl } from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";

import { BusinessMarker, type BusinessMarkerData } from "./BusinessMarker";
import { MapErrorBoundary } from "./MapErrorBoundary";
import type { CallStatus } from "@/hooks/useBlitzStream";
import "./mapStyles.css";

// Mapbox token from environment
const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

interface BlitzMapCardProps {
  /** Call statuses from useBlitzStream - includes lat/lng after backend update */
  callStatuses: CallStatus[];
  /** Optional: highlight the best deal business name */
  bestDealBusiness?: string;
  /** Optional: callback when user clicks a marker */
  onMarkerClick?: (business: BusinessMarkerData) => void;
  /** Optional: custom height (default 250px) */
  height?: number;
}

/**
 * Calculate map bounds to fit all markers with padding
 */
function calculateBounds(
  businesses: BusinessMarkerData[]
): { longitude: number; latitude: number; zoom: number } {
  if (businesses.length === 0) {
    // Default to London
    return { longitude: -0.118, latitude: 51.509, zoom: 12 };
  }

  if (businesses.length === 1) {
    return {
      longitude: businesses[0].longitude,
      latitude: businesses[0].latitude,
      zoom: 14,
    };
  }

  // Calculate center and appropriate zoom for multiple markers
  const lngs = businesses.map((b) => b.longitude);
  const lats = businesses.map((b) => b.latitude);

  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);

  const centerLng = (minLng + maxLng) / 2;
  const centerLat = (minLat + maxLat) / 2;

  // Calculate zoom based on spread
  const lngSpread = maxLng - minLng;
  const latSpread = maxLat - minLat;
  const maxSpread = Math.max(lngSpread, latSpread);

  // Rough zoom calculation (adjust as needed)
  let zoom = 12;
  if (maxSpread > 0.1) zoom = 11;
  if (maxSpread > 0.2) zoom = 10;
  if (maxSpread > 0.5) zoom = 9;
  if (maxSpread < 0.02) zoom = 14;

  return { longitude: centerLng, latitude: centerLat, zoom };
}

/**
 * Extract price from result to determine best deal
 */
function extractPriceValue(result?: string): number | null {
  if (!result) return null;
  const match = result.match(/[£$](\d+(?:\.\d{2})?)/);
  return match ? parseFloat(match[1]) : null;
}

export function BlitzMapCard({
  callStatuses,
  bestDealBusiness,
  onMarkerClick,
  height = 250,
}: BlitzMapCardProps) {
  const [selectedBusiness, setSelectedBusiness] = useState<BusinessMarkerData | null>(null);

  // Filter to only businesses with valid coordinates (Issue 8C - frontend validation)
  const businessesWithCoords = useMemo(() => {
    return callStatuses
      .filter(
        (c): c is CallStatus & { latitude: number; longitude: number } =>
          typeof c.latitude === "number" &&
          typeof c.longitude === "number" &&
          !isNaN(c.latitude) &&
          !isNaN(c.longitude)
      )
      .map((c) => ({
        id: c.phone || c.business,
        name: c.business,
        phone: c.phone,
        address: c.address,
        rating: c.rating,
        latitude: c.latitude,
        longitude: c.longitude,
        status: c.status,
        result: c.result,
        isBestDeal: false, // Will be set below
      }));
  }, [callStatuses]);

  // Determine best deal if not explicitly provided
  const markersWithBestDeal: BusinessMarkerData[] = useMemo(() => {
    if (businessesWithCoords.length === 0) return [];

    // If bestDealBusiness provided, use it
    if (bestDealBusiness) {
      return businessesWithCoords.map((b) => ({
        ...b,
        isBestDeal: b.name === bestDealBusiness,
      }));
    }

    // Otherwise, find lowest price among completed calls
    const completedWithPrices = businessesWithCoords
      .filter((b) => b.status === "complete" && b.result)
      .map((b) => ({
        ...b,
        priceValue: extractPriceValue(b.result),
      }))
      .filter((b) => b.priceValue !== null);

    if (completedWithPrices.length === 0) {
      return businessesWithCoords;
    }

    const lowestPrice = Math.min(
      ...completedWithPrices.map((b) => b.priceValue as number)
    );
    const bestDealId = completedWithPrices.find(
      (b) => b.priceValue === lowestPrice
    )?.id;

    return businessesWithCoords.map((b) => ({
      ...b,
      isBestDeal: b.id === bestDealId,
    }));
  }, [businessesWithCoords, bestDealBusiness]);

  // Calculate initial view state
  const initialViewState = useMemo(
    () => calculateBounds(markersWithBestDeal),
    // Only recalculate when businesses change (not status updates)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [markersWithBestDeal.map((b) => b.id).join(",")]
  );

  const handleMarkerClick = useCallback(
    (business: BusinessMarkerData) => {
      setSelectedBusiness(business);
      onMarkerClick?.(business);
    },
    [onMarkerClick]
  );

  const handlePopupClose = useCallback(() => {
    setSelectedBusiness(null);
  }, []);

  // If no Mapbox token, show fallback
  if (!MAPBOX_TOKEN) {
    return (
      <div className="blitz-map-error" style={{ height }}>
        <span>Map unavailable - configure VITE_MAPBOX_TOKEN</span>
      </div>
    );
  }

  // If no businesses with coords, show minimal message
  if (markersWithBestDeal.length === 0) {
    return (
      <div className="blitz-map-error" style={{ height }}>
        <span>Locating businesses...</span>
      </div>
    );
  }

  return (
    <MapErrorBoundary>
      <div className="blitz-map-container" style={{ height }}>
        <Map
          mapboxAccessToken={MAPBOX_TOKEN}
          initialViewState={initialViewState}
          style={{ width: "100%", height: "100%" }}
          mapStyle="mapbox://styles/mapbox/dark-v11"
          attributionControl={false}
          onError={(e) => {
            console.error("[BlitzMap] Mapbox error:", e);
          }}
        >
          <NavigationControl position="top-left" showCompass={false} />

          {/* Render business markers */}
          {markersWithBestDeal.map((business) => (
            <BusinessMarker
              key={business.id}
              business={business}
              onClick={handleMarkerClick}
            />
          ))}

          {/* Popup for selected business */}
          {selectedBusiness && (
            <Popup
              longitude={selectedBusiness.longitude}
              latitude={selectedBusiness.latitude}
              anchor="bottom"
              onClose={handlePopupClose}
              closeButton={true}
              closeOnClick={false}
              className="map-popup-wrapper"
            >
              <div className="map-popup">
                <h4>{selectedBusiness.name}</h4>
                {selectedBusiness.address && (
                  <p>{selectedBusiness.address}</p>
                )}
                {selectedBusiness.rating && (
                  <p>Rating: {selectedBusiness.rating}/5</p>
                )}
                {selectedBusiness.result && (
                  <p style={{ color: "#86efac", marginTop: 4 }}>
                    {selectedBusiness.result}
                  </p>
                )}
                <span className={`status-badge ${selectedBusiness.status}`}>
                  {selectedBusiness.status.replace("_", " ")}
                </span>
              </div>
            </Popup>
          )}
        </Map>
      </div>
    </MapErrorBoundary>
  );
}

export default BlitzMapCard;
