# Data sources — notes, quirks, ToS

## 1. yfinance (commodity prices + BDI)

- **Tickers:** `HG=F` (copper COMEX), `ALI=F` (aluminum), `HRC=F` (HRC steel), `CL=F` (crude), `^BDI` (Baltic Dry Index).
- **Note:** `HG=F` is COMEX, not true LME terminal. Documented proxy choice.
- **Auth:** None. Yahoo Finance scraping; no ToS guarantee; use tenacity.
- **Cadence:** 15 min (prices), 1h (BDI via logistics_agent).

## 2. GDELT 2.0 GKG (BigQuery)

- **Table:** `gdelt-bq.gdeltv2.gkg`
- **Auth:** GCP service account (`apps/api/secrets/gcp.json`). Role: BigQuery Job User + Data Viewer.
- **Budget:** 1 TB/month free. Target ≤ 5 GB/query via partition pruning (`_PARTITIONTIME`).
- **Billing alert:** Set at $5 in GCP console.
- **Quirks:** Partition is by day. Always add `WHERE _PARTITIONTIME BETWEEN ...` to avoid full-table scans.
- **Adaptive behaviour:** If run returns < 5 items, agent broadens theme filters next run; if > 200, narrows.

## 3. SEC EDGAR

- **Endpoints:** `https://data.sec.gov/submissions/CIK{...}.json` and `https://efts.sec.gov/LATEST/search-index?q=...`
- **Auth:** None. **Must** set `User-Agent: cis-research/0.1 a.shablovskiy@gmail.com` in every request.
- **Rate limit:** 10 req/s. Use tenacity with backoff; hold to 4h cadence.
- **Watched CIKs:** GE Vernova (1993009), Eaton (31277), Hubbell (48898), MSFT (789019), GOOGL (1652044), AMZN (1018724), META (1326801).

## 4. Industry press RSS

- Feeds defined in `apps/api/ingest/sources/press_feeds.yml`.
- **Dedup:** title-embedding cosine ≥ 0.85 (Voyage embeddings) across feeds.
- **Etiquette:** Send `If-Modified-Since` and `ETag` headers on re-polls.

## 5. Hyperscaler / demand

- Hybrid: corporate press-room RSS + SEC 10-Q capex extracts (re-uses sec_agent items).
- GDELT `INVEST` theme events with datacenter entities.

## 6. Freight / logistics

### IMF PortWatch API
- **URL:** `https://portwatch.imf.org/pages/api`
- **Auth:** None. Open, no key required.
- **Watched ports:** Busan (KRPUS), Antwerp (BEANR), Rotterdam (NLRTM), Bremerhaven (DEBRV), Savannah (USSAV), Norfolk (USORF).
- **Signal:** congestion delta ≥ 50% above 30-day rolling average.

### Splash247 RSS
- **URL:** `https://splash247.com/feed/`
- **Auth:** None.
- **Filter:** canal disruptions, port strikes, severe weather, vessel groundings.

### Baltic Dry Index (`^BDI`)
- Pulled via yfinance. Sustained 30-day move ≥ 20% → shipping tightness signal.
- BDI tracks bulk dry cargo, not heavy-lift directly. Documented proxy choice.
