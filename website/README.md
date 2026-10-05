# SayIt Website

The official SayIt product website — the **distribution surface** for the SayIt
desktop app. The desktop application (in the repository root) is the **product**;
this package must never become a dependency of it.

## Status: Stage H — SEO, accessibility & performance polish (complete)

Stages A–H are complete. Highlights:

- **Deployment**: [`website-deploy.yml`](../.github/workflows/website-deploy.yml)
  deploys the static site to **GitHub Pages** on pushes touching `website/`,
  on `workflow_dispatch`, and whenever a release is **published**. It builds
  with `NEXT_PUBLIC_BASE_PATH=/<repo>` (GitHub Pages project-site sub-path),
  then embeds the latest published release's `release-manifest.json` asset at
  the site root — if none exists, the site ships its honest "release
  unavailable" fallback instead of fabricated data. One-time setup: repo
  **Settings → Pages → Source: GitHub Actions**
- Next.js (static export) + TypeScript + Tailwind CSS 4 toolchain
- Design token system in [`src/app/globals.css`](src/app/globals.css), mirroring
  the desktop app's visual language (`src/sayit/ui/theme.py`): quiet teal
  accent `#3B9C8C`, near-black ink, calm red reserved for the recording state,
  8–10px radii, two restrained shadow levels
- Light/dark via `prefers-color-scheme` (no manual switching, no FOUC script)
- Homepage: hero, how-it-works steps, feature pillars, honest platform-status
  table, privacy teaser
- `/download`: download center consuming a static `/release-manifest.json`
  (schema in [`src/lib/release.ts`](src/lib/release.ts), example in
  [`release-manifest.example.json`](release-manifest.example.json)). While no
  release exists it shows an honest "first release hasn't been published yet"
  state with working GitHub fallbacks; cards link to the installation guide
- `/install`: platform-aware guides (Windows / Linux / Source) in accessible
  tabs that default to the detected platform and deep-link via URL hash.
  Verified-only requirements, exact commands (uv / python -m sayit /
  chmod +x), honest SmartScreen disclosure, first-run wizard walkthrough,
  visual verification (no invented CLI flags), and precise uninstall/data
  documentation. Source install is clearly labeled as developer-only
- `/features` and `/privacy`: evidence-backed pages incl. honest limitations
- `/design`: internal design-system reference page (will be demoted from
  public navigation at Stage H)
- Client-side platform detection ([`src/lib/platform.ts`](src/lib/platform.ts)):
  userAgentData → navigator.platform → userAgent with mobile/ChromeOS guards.
  Detection is never stored or transmitted
- Components: `Button`, `Card`, `Container`, `SectionHeading`, `Navbar`,
  `Footer`, `SkipLink`, `SayItMark`, `CopyButton`, `CommandBlock`, `Reveal`,
  `HotkeyChip`, `PageHero`, `FeatureCard`, `PrivacyCard`, `PlatformStatus`,
  `DownloadCenter`, `DownloadCard`, `ChecksumBlock`, `PlatformTabs`,
  `Callout`/`Steps`/`Troubleshooting`, stroke `icons`
- Tests (Vitest + Testing Library) incl. a content claims guard, a
  platform-detection matrix, manifest validation/failure-state tests,
  install-guide content tests, and WCAG contrast / dead-link / metadata /
  build-security audits; ESLint; typecheck; static build

- **Release pipeline**:
  [`scripts/generate-manifest.mjs`](scripts/generate-manifest.mjs) turns real
  release artifacts into `release-manifest.json` + a sha256sum-compatible
  `checksums.txt`. It fails the release when artifacts are missing (no
  partial releases), when an artifact doesn't match its own `.sha256`
  sidecar, when the AppImage's embedded version contradicts the tag, or when
  anything else is inconsistent (plan §40/§41). Wired into
  `.github/workflows/build.yml`'s release job — manifest and checksums ship
  as release assets alongside the installers
- **Contract lock**: a test suite runs the generator on fixture artifacts and
  asserts its output passes the website's own runtime validator
  ([`src/lib/release.ts`](src/lib/release.ts)) — CI-side generation and
  site-side consumption cannot drift apart

Release status: v0.1.2 is published. The release workflow generates the manifest and checksums,
then the GitHub Pages deploy workflow refreshes the download center from that published release.

## Commands

```powershell
npm install        # once
npm run dev        # dev server
npm run check      # lint + typecheck + test + build (full gate)
npm run build      # static export to out/
npm run preview    # serve out/ at http://localhost:4173
```

## Ground rules

- **No API keys.** No cloud ASR, no key-gated services, no analytics keys.
- **No tracking.** No analytics SDK, fingerprinting, or third-party scripts.
- **No accounts.** Downloading will never require signup.
- **Honest claims only.** Every statement traces to the actual desktop
  implementation. No fabricated versions, sizes, downloads, or platform
  support (macOS is not supported; do not imply it).
- **Release data comes from a manifest.** Download URLs and versions will be
  consumed from a generated `release-manifest.json` (later stage) — never
  hardcoded on pages.
- **The desktop app builds without this folder.** Nothing outside `website/`
  depends on it.
