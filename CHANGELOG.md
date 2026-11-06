# Changelog

Notable user-facing changes are recorded here.

## Unreleased

- Catch up only on reminder windows that opened while the app was closed; events added, imported, or edited inside an open window no longer fire an instant toast.
- Show the actual time remaining in reminder notifications instead of the window name.
- Require API requests to come from this service's exact loopback origin, not any localhost port; the Vite dev proxy now presents that origin.
- Save JSON/CSV exports to the Downloads folder in the Linux shell (no overwrite, with a confirmation dialog) and enable pywebview downloads on Windows.
- Fix notification pruning for event IDs that contain colons.
- Run the test suite before building a tagged release.
- Add ESLint, Prettier and strict TypeScript; remove unused imports and every `any` from the interface code; run them in CI and before releases.
- Discard offline changes the service permanently rejects (HTTP 400/409/413/422) with a visible notice instead of letting one bad change block all later syncs; saving an event that was deleted elsewhere now recreates it.
- Show a message when a Website or Register link cannot be opened.

## 1.0.0-8 — 2026-11-05

- Deliver the RPM through GitHub Releases with SHA-256 checksums instead of committing package binaries.
- Package only the desktop launcher, server, compiled frontend, public assets, and license.
- Add calendar deadline markers, multi-day event spans, searchable website links, and tested deadline countdowns.
- Add missed-reminder catch-up and prune stale notification records.
- Harden localhost Host/Origin checks, request handling, and static file serving.
- Fix queued event upserts and import/export reporting; guard CSV formula cells.
- Split the React interface into feature components and prevent duplicate Windows desktop instances.
- Add regression tests for filters, deadlines, calendar markers, imports, and desktop instance ownership.

## 1.0.0-7 — 2026-11-05

- Add retryable notification delivery and local API validation.
- Add Windows uninstall support and Fedora notification dependencies.

## 1.0.0-6 — 2026-11-05

- Add device-local profile picture support.

## 1.0.0-5 — 2026-11-05

- Add the Windows WebView2 launcher, user data path, and toast notifications.

## 1.0.0-4 — 2026-11-05

- Fix the event countdown scope issue that blanked the embedded view.
- Rebuild bundled frontend assets and bypass stale WebKit cache.

## 1.0.0-3 — 2026-11-05

- Ship the full stylesheet and correct the user-level launcher wrapper.

## 1.0.0-2 — 2026-11-05

- Initial local release with SQLite persistence and desktop reminders.
