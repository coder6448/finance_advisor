import os
import requests
from typing import List, Dict, Optional

RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY") or os.getenv("RENTCAST_KEY")
RENTCAST_BASE_URL = os.getenv("RENTCAST_BASE_URL")


def _mock_results(location: Optional[str], max_results: int = 5) -> List[Dict]:
    # Small mocked dataset for local development when no Rentcast URL is configured.
    base = "https://example.com/listing"
    return [
        {
            "price": 1200 + i * 150,
            "beds": 1 + (i % 3),
            "baths": 1 + (i % 2),
            "sqft": 500 + i * 120,
            "address": f"{100+i} Mockingbird Ln, {location or 'Nearby City'}",
            "url": f"{base}/{i}",
        }
        for i in range(max_results)
    ]


def search_housing(location: Optional[str], radius: Optional[int] = None, min_beds: int = 1,
                   min_baths: int = 1, min_sqft: int = 300, max_results: int = 10) -> List[Dict]:
    """Search for rental listings using Rentcast (if configured) or return a mock dataset.

    - Read `RENTCAST_API_KEY` and `RENTCAST_BASE_URL` from environment; do NOT hardcode keys.
    - If `RENTCAST_BASE_URL` is provided, performs a GET request to `{base}/search` with query params.
    - Otherwise returns a small mocked list suitable for demo/testing.
    """
    if not RENTCAST_API_KEY or not RENTCAST_BASE_URL:
        return _mock_results(location, max_results=max_results)

    params = {
        "q": location,
        "radius": radius,
        "min_beds": min_beds,
        "min_baths": min_baths,
        "min_sqft": min_sqft,
        "limit": max_results,
    }

    headers = {
        "Authorization": f"Bearer {RENTCAST_API_KEY}",
        "Accept": "application/json",
    }

    try:
        url = RENTCAST_BASE_URL.rstrip("/") + "/search"
        resp = requests.get(url, params={k: v for k, v in params.items() if v is not None}, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Try common field names; gracefully degrade to raw items if structure differs.
        items = data.get("listings") or data.get("results") or (data if isinstance(data, list) else [])
        out = []
        for it in items[:max_results]:
            out.append({
                "price": it.get("price") or it.get("rent"),
                "beds": it.get("beds") or it.get("bedrooms"),
                "baths": it.get("baths") or it.get("bathrooms"),
                "sqft": it.get("sqft") or it.get("size"),
                "address": it.get("address") or it.get("location") or it.get("display_address"),
                "url": it.get("url") or it.get("detail_url") or it.get("listing_url"),
            })
        return out
    except Exception:
        # On any error, return a mock result rather than failing the entire request.
        return _mock_results(location, max_results=max_results)
