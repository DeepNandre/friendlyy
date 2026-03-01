/**
 * BusinessMarker - Animated marker for business locations on the Blitz map
 *
 * Reuses CallStatusType values directly for styling (Issue 5A)
 * Includes pulse animations for ringing state and price labels for quotes
 */

import React from "react";
import { Marker } from "react-map-gl/mapbox";
import type { CallStatusType } from "@/hooks/useBlitzStream";
import "./mapStyles.css";

export interface BusinessMarkerData {
  id: string;
  name: string;
  phone?: string;
  address?: string;
  rating?: number;
  latitude: number;
  longitude: number;
  status: CallStatusType;
  result?: string;
  isBestDeal?: boolean;
}

interface BusinessMarkerProps {
  business: BusinessMarkerData;
  onClick?: (business: BusinessMarkerData) => void;
}

/**
 * Extract price from result string (e.g., "Available for £85" -> "£85")
 */
function extractPrice(result?: string): string | null {
  if (!result) return null;
  const match = result.match(/[£$]\d+(?:\.\d{2})?/);
  return match ? match[0] : null;
}

export function BusinessMarker({ business, onClick }: BusinessMarkerProps) {
  const price = business.status === "complete" ? extractPrice(business.result) : null;

  // Build CSS classes based on status
  const markerClasses = [
    "blitz-marker",
    business.status,
    business.isBestDeal ? "best-deal" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Marker
      longitude={business.longitude}
      latitude={business.latitude}
      anchor="center"
      onClick={(e) => {
        e.originalEvent.stopPropagation();
        onClick?.(business);
      }}
    >
      <div className={markerClasses} title={business.name}>
        {/* Price label for completed calls with quotes */}
        {price && <div className="price-label">{price}</div>}
      </div>
    </Marker>
  );
}

export default BusinessMarker;
