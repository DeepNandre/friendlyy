"""
Google Places API integration with fallback to hardcoded businesses.
Uses asyncio.gather for parallel detail fetches to minimize latency.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any

from core import get_http_client, settings
from models import Business
from services.weave_tracing import traced, log_business_search, get_trace_ctx

logger = logging.getLogger(__name__)

PLACES_API_URL = "https://maps.googleapis.com/maps/api/place"

# Fallback UK businesses for demo reliability (with coordinates for map display)
FALLBACK_BUSINESSES: Dict[str, List[Business]] = {
    "plumber": [
        Business(
            id="fallback_plumber_1",
            name="Pimlico Plumbers",
            phone="+442078331111",
            address="1 Sail Street, London SE11 6NQ",
            rating=4.5,
            latitude=51.4875,
            longitude=-0.1087,
        ),
        Business(
            id="fallback_plumber_2",
            name="Mr. Plumber London",
            phone="+442072230987",
            address="15 High Street, London EC1V 9JX",
            rating=4.3,
            latitude=51.5246,
            longitude=-0.0952,
        ),
        Business(
            id="fallback_plumber_3",
            name="HomeServe UK",
            phone="+443301238888",
            address="Cable Drive, Walsall WS2 7BN",
            rating=4.1,
            latitude=52.5860,
            longitude=-1.9826,
        ),
    ],
    "electrician": [
        Business(
            id="fallback_electrician_1",
            name="London Electrical Services",
            phone="+442071234567",
            address="10 Electric Avenue, London SW9 8LA",
            rating=4.6,
            latitude=51.4613,
            longitude=-0.1156,
        ),
        Business(
            id="fallback_electrician_2",
            name="Spark Electrical",
            phone="+442089876543",
            address="25 Power Street, London NW1 8XY",
            rating=4.4,
            latitude=51.5362,
            longitude=-0.1426,
        ),
    ],
    "locksmith": [
        Business(
            id="fallback_locksmith_1",
            name="London Locksmiths 24/7",
            phone="+442074561234",
            address="Lock Lane, London W1 2AB",
            rating=4.7,
            latitude=51.5155,
            longitude=-0.1419,
        ),
    ],
    "default": [
        Business(
            id="fallback_default_1",
            name="Friendly Demo Business 1",
            phone="+15005550006",  # Twilio test number (always answers)
            address="123 Demo Street, London",
            rating=4.5,
            latitude=51.5074,
            longitude=-0.1278,
        ),
        Business(
            id="fallback_default_2",
            name="Friendly Demo Business 2",
            phone="+15005550006",
            address="456 Test Road, London",
            rating=4.3,
            latitude=51.5124,
            longitude=-0.1231,
        ),
    ],
}


def _log_search(*, result, duration, error, args, kwargs, ctx):
    """Log callback for search_businesses."""
    query = args[0] if args else kwargs.get("query", "")
    location = kwargs.get("location") if len(args) < 2 else args[1]
    log_business_search(
        query=query,
        location=location,
        results_count=len(result) if result else 0,
        duration=duration,
        used_fallback=ctx.get("used_fallback", False),
    )


@traced("search_businesses", log_fn=_log_search)
async def search_businesses(
    query: str,
    location: Optional[str] = None,
    lat_lng: Optional[Dict[str, float]] = None,
    max_results: int = 3,
) -> List[Business]:
    """
    Search for businesses using Google Places API.

    Falls back to hardcoded businesses if:
    - API key not configured
    - API call fails
    - No results found

    Args:
        query: Service type (e.g., "plumber", "electrician")
        location: Location string (e.g., "London", "Manchester")
        lat_lng: Dict with 'lat' and 'lng' keys
        max_results: Maximum businesses to return (default 3)

    Returns:
        List of Business objects with phone numbers
    """
    logger.info(f"[PLACES] Searching: query='{query}', location='{location}', lat_lng={lat_lng}")

    # Check for API key
    if not settings.google_places_api_key:
        logger.info("Google Places API key not set, using fallback")
        get_trace_ctx()["used_fallback"] = True
        return _get_fallback_businesses(query, max_results)

    try:
        businesses = await _search_places_api(query, location, lat_lng, max_results)
        if businesses:
            return businesses
        logger.info(f"No Places results for '{query}', using fallback")
        get_trace_ctx()["used_fallback"] = True
        return _get_fallback_businesses(query, max_results)

    except Exception as e:
        logger.error(f"Places API error: {e}, using fallback")
        get_trace_ctx()["used_fallback"] = True
        return _get_fallback_businesses(query, max_results)


async def _search_places_api(
    query: str,
    location: Optional[str],
    lat_lng: Optional[Dict[str, float]],
    max_results: int,
) -> List[Business]:
    """
    Execute Places API search with parallel detail fetches.
    """
    client = await get_http_client()

    # Build search query
    search_query = query
    if location:
        search_query = f"{query} in {location}"

    logger.info(f"[PLACES] Google API query: '{search_query}'")

    # Build params
    params: Dict[str, Any] = {
        "query": search_query,
        "key": settings.google_places_api_key,
    }

    # Add location bias if provided
    if lat_lng:
        params["location"] = f"{lat_lng['lat']},{lat_lng['lng']}"
        params["radius"] = 10000  # 10km radius

    # Step 1: Text search to find places
    search_response = await client.get(
        f"{PLACES_API_URL}/textsearch/json",
        params=params,
    )
    search_response.raise_for_status()
    search_data = search_response.json()

    places = search_data.get("results", [])
    logger.info(f"[PLACES] Found {len(places)} raw results from Google")
    if not places:
        return []

    # Get extra places in case some don't have phone numbers
    places = places[: max_results * 2]

    # Step 2: Fetch details in parallel using asyncio.gather
    detail_tasks = [
        _fetch_place_details(client, place.get("place_id"))
        for place in places
        if place.get("place_id")
    ]

    details_results = await asyncio.gather(*detail_tasks, return_exceptions=True)

    # Step 3: Filter to businesses with phone numbers
    businesses: List[Business] = []
    for details in details_results:
        if isinstance(details, Exception):
            logger.warning(f"Place details fetch failed: {details}")
            continue

        if details and details.get("phone"):
            # Only include businesses with valid coordinates (per Issue 8C)
            lat = details.get("latitude")
            lng = details.get("longitude")

            businesses.append(
                Business(
                    id=details["place_id"],
                    name=details["name"],
                    phone=details["phone"],
                    address=details.get("address"),
                    rating=details.get("rating"),
                    place_id=details["place_id"],
                    website=details.get("website"),
                    latitude=lat,
                    longitude=lng,
                )
            )

            if len(businesses) >= max_results:
                break

    return businesses


async def _fetch_place_details(
    client: Any, place_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch details for a single place including phone number and coordinates.
    """
    response = await client.get(
        f"{PLACES_API_URL}/details/json",
        params={
            "place_id": place_id,
            "fields": "name,formatted_phone_number,international_phone_number,formatted_address,rating,website,geometry",
            "key": settings.google_places_api_key,
        },
    )
    response.raise_for_status()
    data = response.json()

    result = data.get("result", {})
    if not result:
        return None

    phone = result.get("international_phone_number") or result.get(
        "formatted_phone_number"
    )

    if not phone:
        return None

    # Extract coordinates from geometry
    geometry = result.get("geometry", {})
    location = geometry.get("location", {})
    latitude = location.get("lat")
    longitude = location.get("lng")

    return {
        "place_id": place_id,
        "name": result.get("name", "Unknown"),
        "phone": phone.replace(" ", ""),  # Remove spaces
        "address": result.get("formatted_address"),
        "rating": result.get("rating"),
        "website": result.get("website"),
        "latitude": latitude,
        "longitude": longitude,
    }


def _get_fallback_businesses(query: str, max_results: int) -> List[Business]:
    """
    Get fallback businesses for a given service type.
    """
    query_lower = query.lower()

    # Try exact match first
    if query_lower in FALLBACK_BUSINESSES:
        return FALLBACK_BUSINESSES[query_lower][:max_results]

    # Try partial match
    for key, businesses in FALLBACK_BUSINESSES.items():
        if key in query_lower or query_lower in key:
            return businesses[:max_results]

    # Return default fallback
    return FALLBACK_BUSINESSES["default"][:max_results]
