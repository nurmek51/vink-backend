# Tariff Integration Documentation

## Overview

This document describes how tariffs and network rates are handled in the VinkSIM application. The backend dynamically fetches and caches these rates to ensure the user is always presented with the most up-to-date pricing information based on their location.

## Data Source

Primary data source for tariff rates:
`https://imsimarket.com/js/data/alternative.rates.json`

This JSON file is maintained by the provider and updated hourly. The backend syncs with this source.

### Data Structure

The source returns an array of objects:

```json
[
  {
    "PLMN": "26201",
    "NetworkName": "Telekom",
    "CountryName": "Germany",
    "DataRate": 0.05
  },
  ...
]
```

- **PLMN**: Public Land Mobile Network code (MCC + MNC).
- **NetworkName**: The display name of the local operator.
- **CountryName**: The country where this rate applies.
- **DataRate**: The cost in USD per MB of data usage.

## Backend Logic

### Rate Caching

The `EsimService` manages a local in-memory cache of these rates:
1.  **On Request**: When `get_tariffs` or eSIM details are requested, the service checks the cache.
2.  **Expiration**: The cache expires after 1 hour (3600 seconds) to align with the hourly update cycle of the source.
3.  **Fetch**: If expired or empty, it fetches the JSON from the provider URL.

### Location & Rate Tracking

When an eSIM is active, the provider reports the **Last MCC** (Mobile Country Code) where the device was seen.

1.  **MCC Mapping**: The backend maps the `last_mcc` (e.g., 424) to a specific country (e.g., "United Arab Emirates") using a static MCC list (`app/common/mcc_codes.py`).
2.  **Rate Lookup**: The service looks up all standard rates for that country in the fetched tariffs.
3.  **Cost Display**: It selects the **minimum available DataRate** for that country to display on the eSIM object (`current_rate`).
    *   *Note: While the exact network the user is connected to dictates the precise rate, showing the minimum capability or a general country rate gives the user the best expected baseline.*

## Frontend Integration Guidelines

### 1. Displaying Available Tariffs

Use the `GET /tariffs` endpoint to show users where they can use the service and how much it costs.

**Response:**
```json
[
  {
    "plmn": "26201",
    "network_name": "Telekom",
    "country_name": "Germany",
    "data_rate": 0.05
  },
  ...
]
```

**Implementation:**
- Fetch this list on app launch or when browsing destinations.
- Group by `country_name` if you want to show "Rates in Germany" (showing the range or best rate).

### 2. Monitoring Current Usage Rate

Use the `GET /esims` or `GET /esims/{id}` endpoints.

**Relevant Fields:**
- `country`: The current country detection (e.g., "Germany").
- `rate`: The current cost per MB (e.g., 0.05).
- `last_mcc`: Technical location code.

**UI Recommendation:**
- On the eSIM details screen, display: **"Current Location: {country}"**.
- Display: **"Rate: ${rate}/MB"**.
- If `rate` is 0.0 or `country` is "Global", it implies the device hasn't reported a location yet (or is offline).

### 3. Usage & Balance

Since the balance is pre-calculated by the provider based on these rates, the frontend **DOES NOT** need to calculate usage cost manually.

- Simply display `data_remaining_mb` or `provider_balance` (which reflects the remaining money).
- If the API returns `provider_balance`, you can calculate remaining MB approx as: `provider_balance / rate`.
- **Backend handles this**: Use the `data_remaining_mb` from `GET /esims/{id}/usage` for the most accurate "Megabytes left" gauge.

## Error Handling

- If the tariff data source is unreachable, the backend returns an empty list or cached stale data.
- Frontend should handle empty tariff lists gracefully (e.g., "Retrying..." or generic message).
