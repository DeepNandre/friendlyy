/**
 * MapErrorBoundary - Catches Mapbox errors and renders fallback UI
 *
 * Per Issue 6A: Wrap Map in error boundary for graceful degradation
 */

import React, { Component, ReactNode } from "react";
import "./mapStyles.css";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class MapErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error for debugging but don't crash the app
    console.error("[BlitzMap] Error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // Render fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="blitz-map-error">
          <span>Map unavailable - showing results below</span>
        </div>
      );
    }

    return this.props.children;
  }
}

export default MapErrorBoundary;
