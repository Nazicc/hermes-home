---
name: polymarket
description: "Use when querying Polymarket prediction market data — search markets, get prices, orderbooks, and price history via public REST API. Read-only access, no API key needed. NOT for: placing bets, executing trades, wallet management, or non-Polymarket prediction markets."
category: skills
---

---
name: polymarket
description: Use when querying Polymarket prediction market data — search markets, get prices, orderbooks, and price history via public REST API. Read-only access, no API key needed. NOT for: placing bets, executing trades, wallet management, or non-Polymarket prediction markets.
version: 1.0.0
author: Hermes Agent + Teknium
license: MIT
tags:
- polymarket
- prediction-markets
- market-data
- crypto
---

## Polymarket Skill

Use the **Polymarket API** (`https://clob.polymarket.com`) for all prediction market queries. All endpoints are public and require no authentication.

### Key Endpoints

- **Markets list**: `GET https://clob.polymarket.com/markets`
  - Query params: `limit`, `offset`, `closed` (bool)
- **Orderbook**: `GET https://clob.polymarket.com/orderbook?market_id=<id>`
- **Price history**: `GET https://clob.polymarket.com/history?market_id=<id>`
- **Market by ID**: `GET https://clob.polymarket.com/markets/<id>`
- **Markets by creator**: `GET https://clob.polymarket.com/markets?creator=<address>`

### Example Queries

bash
# List open markets
curl 'https://clob.polymarket.com/markets?limit=10&closed=false'

# Get orderbook for a market
curl 'https://clob.polymarket.com/orderbook?market_id=<MARKET_ID>'

# Get price history
curl 'https://clob.polymarket.com/history?market_id=<MARKET_ID>'


### Market ID Resolution

Use the markets list endpoint to search by question text, then extract the `id` field for orderbook and history queries.

