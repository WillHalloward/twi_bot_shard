-- Migration: add ao3_sessions table for cached AO3 login sessions
-- Date: 2026-06-01
--
-- Context:
--   cogs/external_services.py creates a fresh AO3.Session(username, password)
--   on every bot startup. The underlying ao3-api library is a BeautifulSoup
--   scraper, so login intermittently fails (Sentry: PYTHON-AIOHTTP-9 /
--   PYTHON-AIOHTTP-A). To reduce login round-trips we now pickle the
--   authenticated Session after a successful login and rehydrate it on the
--   next startup, falling back to fresh login if the cached session is
--   stale (>7 days) or fails a cheap auth probe.
--
--   session_data holds pickle.dumps(ao3_session) — contains AO3 auth cookies
--   (strictly less sensitive than the username/password already stored in
--   config). saved_at gates the 7-day staleness check;
--   last_validated_at records the most recent successful probe.

CREATE TABLE IF NOT EXISTS ao3_sessions (
    username           text      PRIMARY KEY,
    session_data       bytea     NOT NULL,
    saved_at           timestamp NOT NULL,
    last_validated_at  timestamp
);
