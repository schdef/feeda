# Feeda: Project Plan, Known Issues & Roadmap

> **Status:** Active Development  
> **Target Platforms:** Linux / Workstations, Samsung Galaxy S10+ (Termux / Edge Server)  
> **Last Updated:** November 2026

---

## 1. Executive Summary & Architecture Overview

**Feeda** is a modern, privacy-first RSS and podcast reader powered by local machine learning, designed for single-user self-hosting on low-power devices (such as a 24/7 Samsung Galaxy S10+ running Termux) or standard Linux servers.

```
┌─────────────────────────────────────────────────────────────┐
│                       Feeda Architecture                    │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │             Frontend (React 19 + Vite 6)            │   │
│   │  - Tailwind CSS (v4) & Lucide Icons                 │   │
│   │  - Zustand App Store & Local Storage                │   │
│   │  - Offline IndexedDB Outbox & Service Worker (PWA)  │   │
│   │  - Interactive Visualizations (Canvas / SVG)        │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │ REST API (/api/*)            │
│   ┌──────────────────────────▼──────────────────────────┐   │
│   │             Backend (FastAPI + Uvicorn)             │   │
│   │  - Async SQLite (WAL mode + busy_timeout = 15s)     │   │
│   │  - Background Feed Poller (30-min scheduled loop)   │   │
│   │  - Semantic Deduplication & Cross-day Clustering    │   │
│   │  - AI Summarization & Story Signature Extraction    │   │
│   │  - FTS5 Full-Text Search Engine                     │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Current Known Issues & Technical Debt

| ID | Issue Description | Component | Severity | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| **ISS-01** | **Interests Board shows read starred items in unread mode:** When `showRead === false`, read articles that are starred (`a.is_read = 1 AND a.is_starred = 1`) remain visible because of `if (!showRead && article.is_read && !article.is_starred)`. Backend query also grabs `WHERE (a.is_read = 0 OR a.is_starred = 1)`. | Frontend / Backend | High | Fix in progress (Goal queue) |
| **ISS-02** | **Interests Board empty topic column rendering:** When applying filters (`Likely`, `Less Likely`), columns with 0 matching articles remain rendered with empty placeholders rather than collapsing to show only matching topics. | Frontend | Medium | Fix in progress (Goal queue) |
| **ISS-03** | **Tests coupled to production `feeda.db`:** `tests/test_podcast_dedup.py` and `tests/test_ml_and_dedup.py` directly read from and write to the live SQLite DB, causing test failures (e.g. `assert 20 == 19`) and flakiness in CI. | Testing | Critical | In progress (Subagent) |
| **ISS-04** | **FTS5 search input crash on special characters:** `articles_fts MATCH ?` in `/api/articles/search` uses unsanitized user query input; characters such as `"`, `:`, `*`, `+`, `AND`, or `OR` cause SQLite syntax exceptions. | Backend | Medium | In progress (Subagent) |
| **ISS-05** | **Hardcoded private deployment port & domain in repo:** A custom private deployment port was used as default across docs, scripts, and config, exposing private deployment details that belong exclusively in `personal-infra`. | Infra / Config | High | Resolved |
| **ISS-06** | **Service worker asset cache staleness:** `frontend/public/sw.js` uses a static cache key (`feeda-v2`), causing browsers to serve outdated bundled assets until caches are manually purged. | Frontend PWA | Medium | Open |
| **ISS-07** | **Case-sensitivity alteration in URL hash:** `normalize_url()` in `dedup.py` executes `url.lower()` on the full query string, which could alter case-sensitive video or episode tokens if used outside hashing. | Backend | Low | Open |

---

## 3. Feature Gaps & Missing Capabilities

### 3.1 Media & Podcast Playback
- **Audio Enclosure Extraction:** `feed_parser.py` currently only extracts image thumbnails from enclosures and discards `audio/mpeg` or podcast streams.
- **Integrated In-App Audio Player:** No native persistent audio player, playback progress bar, playback speed adjustment (1.25x, 1.5x, 2x), or position resumption.
- **Background Media Playback:** No Media Session API integration to handle phone lock-screen controls.

### 3.2 Reader Experience & Content Extraction
- **Full-Text Readability Scraper:** Feeds that only publish 1–2 sentence teasers cannot be expanded to full article text within Feeda.
- **Reader Typography Customization:** No font size slider, serif/sans-serif switch, line-height options, or reading time indicators.

### 3.3 Storage & Database Lifecycle
- **Unbounded Storage Growth:** The database grows indefinitely (~61 MB currently). There is no automated retention policy (e.g., delete non-starred read articles older than 30–60 days) or automated SQLite `VACUUM`.
- **Database Maintenance Routine:** Need a periodic maintenance cron to optimize FTS indexes, purge unreferenced clusters, and keep storage lean on mobile devices.

### 3.4 Security & Multi-Client Access
- **API Authentication:** Lack of token-based authentication (`FEEDA_API_KEY`) when exposing the server over Tailscale, LAN, or reverse proxies.
- **Third-Party Sync API:** Lack of Google Reader API or Fever API emulation, preventing integration with third-party native apps like Reeder, NetNewsWire, or Readwise.

### 3.5 App Management & UI Settings
- **Settings UI:** No user-facing settings view to modify feed polling intervals, configure AI model keys, or inspect storage metrics.
- **Batch Feed Management:** Cannot bulk move feeds between folders, bulk mark folders as read from sidebar, or bulk export selections.
- **Notifications:** No Web Push or local notification triggers for high-likelihood breaking stories.

---

## 4. Phased Roadmap & Milestones

### Phase 1: Test DB Isolation & Security Hardening *(Current Sprint)*
- [x] Create plan and acceptance criteria.
- [ ] Create `tests/conftest.py` with isolated temporary SQLite test fixtures and auto-migrations.
- [ ] Decouple `test_podcast_dedup.py` and `test_ml_and_dedup.py` from `backend/feeda.db`.
- [ ] Sanitize FTS5 search queries in `backend/feeda/routers/articles.py`.
- [ ] Implement `FEEDA_API_KEY` authentication middleware and default host binding to `127.0.0.1`.
- [x] Purge custom private deployment ports and any domain references from `feeda`, isolating private deployment coordinates in `personal-infra`.

### Phase 2: Interests View Dynamic Adjustment & Unread Filtering *(Next Goal)*
- [ ] Default Interests board to unread-only (`showRead === false`), strictly excluding read starred articles.
- [ ] Add `unread_only: bool = True` query parameter to `/api/articles/interest-board` to optimize topic slots.
- [ ] Dynamically hide topic columns with 0 matching articles when filtering by likelihood or read status.
- [ ] Ensure column badge counts accurately display the count of matching visible articles.

### Phase 3: Podcast Audio Engine & Media Enclosures
- [ ] Add `enclosure_url`, `media_type`, and `duration` fields to the `articles` database schema.
- [ ] Update `feed_parser.py` to extract and preserve audio enclosures.
- [ ] Implement persistent floating audio player with playback speed, progress scrubbing, and Media Session API support.

### Phase 4: Full Article Scraper & Reader Customization
- [ ] Implement readability scraper backend service (extracting readable article body on demand).
- [ ] Add font family (Sans / Serif / Monospace), font size, and reader line spacing controls in `ArticleReader.tsx`.

### Phase 5: Storage Retention & Database Maintenance
- [ ] Add background retention worker to prune unstarred read articles older than 30 days.
- [ ] Expose manual "Clean & Compact Database" action in settings to execute SQLite `VACUUM`.

### Phase 6: Sync Protocols & Cloud Integrations
- [ ] Implement Google Reader / Miniflux compatible API endpoints (`/fever`, `/greader/api/0/*`) for seamless integration with mobile RSS clients.
