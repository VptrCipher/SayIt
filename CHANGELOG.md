# Changelog\n\n## [0.1.2] - 2026-10-05\n\n### Custom hotkeys\n- Hardened custom hotkey runtime registration and replacement so a newly applied shortcut replaces the old listener cleanly.\n- Normalized Qt special-key names (including Page Up/Down, Print Screen, locks, Backspace, Return, and arrows) to the pynput key names used by the global listener.\n- Added regression coverage for special keys, character/function keys, settings persistence, and Qt-to-runtime key normalization.\n

All notable changes to this project are documented here. The project version in `pyproject.toml` is `0.1.2`. Version 0.1.2 is a reliability/bugfix release focused on custom hotkey robustness and persistence.

This changelog describes work completed during a reliability, UX, and
privacy-hardening effort. Items are listed only where they correspond to actual
code and passing automated tests. Behavior that has not been validated end-to-end
(for example, real ASR model-backed transcription) is noted as such in the README.

## [0.1.1] - 2026-10-04

### Release / bug fixes
- Fixed persistent ASR model selection being overwritten by the Speech Mode controls.
- Fixed settings reset so it persists to disk, immediately reapplies the runtime settings, and preserves the typed `HotkeyConfig`.
- Fixed live custom hotkey replacement: applying a new hotkey now tears down the old global keyboard listener, clears stale pressed-key state, and registers the new combination immediately.
- Preserved custom hotkey restoration on startup from the persisted `settings.json` configuration.
- Added regression coverage for model and custom-hotkey disk persistence, startup restoration, and live hotkey re-registration.
- Added the SayIt OS icon packaging pipeline and removed the BeeWare default icon from the packaged executable.

## [0.1.1] - 2026-10-04

### Release / CI fixes
- Aligned `sherpa-onnx-core` with the validated `sherpa-onnx 1.12.21` release to avoid a Linux native ONNX Runtime symbol mismatch during CI.
- Updated CI dependency resolution so the build environment refreshes the lock consistently before testing and packaging.

## [Unreleased]

### Local intelligence layer (Phase 8A–8H)
A deterministic, local-only, explainable "intelligence" layer added on top of
the existing ASR pipeline. Nothing here uses an LLM, the network, screenshots,
the clipboard, or page/editor contents; every feature can be disabled and all
output still flows through the existing safe clipboard-paste insertion.

- **Context Engine + Profiles (8A).** Local active-window/process detection
  (Windows via `user32`/`kernel32`; Linux via `xdotool` when present) resolves a
  formatting *profile* (Normal / Developer / Email / Chat / Notes / Prompt). The
  profile only narrows which existing 6G/6I correction rules run — it never
  rewrites arbitrary prose. Manual override always wins; the current context is
  shown on Home as `Context: Developer` / `Context: Auto · code`.
- **Voice Edit / Backtrack (8B).** Deterministic, strongly-anchored editing of
  the most recent output: within-utterance ("… at five. Actually six." →
  "… at six."; "Install Docker. Scratch that. Install Podman." → "Install
  Podman.") and cross-utterance ("scratch that", "replace X with Y", "change X
  to Y", "delete/remove the last sentence"). A bounded, in-memory,
  single-unit output buffer backs cross-utterance edits (never written to disk).
  Ambiguous phrases are treated as ordinary dictation.
- **Snippets (8C).** Local, text-only expansion distinct from vocabulary
  ("my github" → a saved URL; "pull request template" → a Markdown block).
  Whole-utterance match by default; optional inline mode. Snippets are **never
  executed** — command-like content is inserted verbatim as text. New Snippets
  tab, stored in settings (no SQLite).
- **Developer Mode (8D).** Explicit identifier casing commands ("get user by id,
  camel case" → `getUserById`; snake/kebab/pascal) and a `code block … end code
  block` wrapper that preserves content verbatim in a Markdown fence. Only
  explicit commands transform text; ordinary developer prose is untouched.
- **Safe Zones (8E).** User-configured protected applications where recording is
  blocked **before any audio is captured**, reusing the 8A detector (no second
  detection subsystem). Fail-safe: a detection failure never silently disables
  dictation. Home shows "SayIt paused — protected application".
- **Remember Correction (8F).** Explicit, opt-in learning only: a correction is
  diffed into a candidate rule and offered via a Remember / Not now / Never
  prompt; only "Remember" creates a (6J) vocabulary entry (category "learned"),
  and "Never" suppresses that exact candidate. No passive/silent learning.
- **Smart Structure (8G).** Explicit structure commands ("new line", "new
  paragraph") and clean ordinal enumerations ("first … second … third …" →
  a numbered list). Strongly anchored so ordinary nouns ("a good point", "a new
  line of code") never trigger.
- **Intelligence Orchestrator (8H).** A single deterministic orchestrator
  sequences 8B–8G in a fixed priority (Voice Edit → Snippet → Structure →
  Developer → Dictate), single-pass (no transformation loops), with explicit
  commands taking precedence over passive context. It orchestrates the existing
  engines rather than re-implementing them, runs before the existing 6G/6I/6J +
  optional-LLM pipeline, and sets a `skip_correction` flag so literal output
  (snippets, code blocks, structure, identifiers) is preserved verbatim.
- **Settings/UI.** New Snippets navigation tab; Configuration-tab sections for
  Context & Profiles, Local Intelligence toggles, and Safe Zones (add/remove/
  clear protected apps); a Remember-correction dialog; Home context/protected/
  voice-edit indicators. All reuse the existing motion system and reduced-motion
  support.
- **Tests/perf/privacy.** 156 new fast tests (unit, negative, cross-feature
  matrix, E2E scenarios, privacy AST audits, determinism, settings round-trip);
  full fast suite 546 passed. Every engine measured sub-0.02 ms median; the full
  orchestrator ~0.011 ms median / ~0.016 ms p95; memory growth 5.7 KiB over 50
  mixed cycles. See `docs/PHASE_8_VALIDATION.md`.


- Rebranded the Windows distribution as **SayIt**: the Briefcase `formal_name`
  is now "SayIt" (produces `SayIt.exe` with ProductName/FileDescription/
  CompanyName = SayIt and version 0.1.0), and the Inno Setup installer outputs
  `SayIt-Setup-x64.exe`. Internal technical identifiers are unchanged: the Python
  package/import path stays `sayit`, the per-user data directory stays
  `%LOCALAPPDATA%\SayIt`, and the autostart registry key stays "SayIt",
  so existing installs/settings/models/autostart keep working.
- Verified the Briefcase Windows app builds a self-contained bundle
  (`briefcase create/build windows app`): `SayIt.exe` plus a bundled Python
  runtime, PySide6, and Sherpa-ONNX including the native `sherpa-onnx-c-api.dll`.
  Bundle ≈ 480 MB; ASR model weights are **not** bundled (downloaded on first
  use into `%LOCALAPPDATA%\SayIt\models`).
- Hardened the Inno Setup script: SayIt product name, `AppVerName`, uninstall
  display name/icon, Start Menu + optional Desktop/startup shortcuts, and a
  **safe uninstall data policy** — the previous unconditional deletion of
  `%LOCALAPPDATA%\SayIt` was replaced with an explicit prompt that defaults
  to **keeping** the user's settings and downloaded models.
- Pointed Briefcase at the real `LICENSE` file (MIT) to bundle correct license
  text and resolve the packaging license warning.
- Updated the GitHub Actions release workflow: app renamed to SayIt, the test
  job runs `pytest -m "not slow"` headless, a SHA-256 checksum is generated for
  the installer, and both the `.exe` and `.sha256` are uploaded as artifacts and
  included in the (draft) GitHub Release. No release is auto-published.
- Packaging security review: no `.env`, logs, private keys, or SayIt test/
  benchmark fixtures are present in the bundle (dependency modules named
  "credential/secret/token" are legitimate library source, not secret values).
- `.gitignore` now excludes `installer-output/`, `*.exe`, `*.AppImage`, `*.msi`,
  and `*.sha256` so release binaries are treated as GitHub Release assets rather
  than committed to source control.
- Added `docs/PHASE_7_RELEASE_VALIDATION.md` and expanded `RELEASE_CHECKLIST.md`
  with concrete release-candidate fields, strictly separating AUTOMATED VERIFIED
  from INSTALLED-APPLICATION VERIFIED and USER PHYSICAL VALIDATION REQUIRED.
- Known limitation: Inno Setup (`iscc`) is not available in the development
  environment, so the final installer is compiled by the CI `windows-latest`
  job; clean-install and physical-dictation validation are explicitly pending.
  The binary is unsigned (code signing is a documented release consideration).

### Reliability
- Hardened the data-cleanup path-safety guard against filesystem/drive roots,
  the home directory, and dangerously shallow paths (cross-platform).
- Hardened the audio recorder lifecycle: the microphone stream is always closed
  and state reset even on error, the capture buffer is cleared between
  recordings, and a failed recording no longer affects the next one.
- Added protection against overlapping transcription jobs.
- Added explicit per-dictation job ownership (monotonic job id) so results are
  tied to the job that produced them.
- Added stale-result rejection so an old job can never insert into a newer
  context.
- Made failed text insertion recoverable (transcript retained; visible error
  state) instead of silently lost.

### Runtime state
- Introduced an explicit application state machine (Idle / Recording /
  Transcribing / Cancelled / Error / Shutting-down) as the single source of
  truth for the dictation workflow.
- Centralized tray status so the visible status always matches the real state.
- Added cooperative **Esc** cancellation for recording and in-flight
  transcription (cancelled results are never inserted; threads are not
  force-killed).
- Made engine/model reload deterministic with respect to an active transcription
  (invalidate + cooperatively cancel + wait before unloading).
- Hardened shutdown to invalidate active jobs and block new work.
- Ensured error paths return the app to a usable state rather than a stuck one.

### First-run experience
- Reworked the first-run setup wizard: welcome/privacy, microphone, speech model,
  hotkey, "try your first dictation", and completion.
- Added an ASR-free microphone signal test (`MicrophoneTestController`) with
  honest outcomes (device unavailable / stream failed / no signal / signal
  detected) and guaranteed stream cleanup.
- Made the model step non-blocking with honest "installed / not installed"
  states; setup can be completed without a model, but dictation requires one.
- Made the "try it" step honest — it never fabricates a transcript.
- Added accessible names and keyboard-oriented controls to setup/privacy UI.

### Local text correction (Phase 6G)
- Added a local, deterministic post-ASR correction layer
  (`core/transcript_processor/technical_corrector.py`) that runs entirely
  on-device with no network, no model, and no transcript logging. The pipeline
  is: raw transcript → technical normalization → structured formatting → final
  text, applied before the existing vocabulary replacements and optional LLM
  enhancement.
- Kept the vocabulary data (`tech_vocabulary.py`) separate from the processing
  logic. The registry covers common developer terms (Git/GitHub/GitHub Actions,
  Python/JavaScript/TypeScript, React/Next.js/Node.js, SQL/PostgreSQL/GraphQL,
  Docker/Kubernetes/CI-CD, AWS/GCP/Azure, VS Code, protocols) and spelled-out
  acronyms (API, SDK, TLS, SSH, JSON, YAML, JWT, OAuth, CI/CD, …).
- Conservative by design: only registered multi-word aliases and whole
  spelled-out acronym phrases are rewritten; ordinary prose and unrecognized
  proper names are left unchanged. No fuzzy matching, no name guessing, no
  network/LLM.
- Added conservative structured formatting for decimal/version expressions
  ("three point two" → "3.2"), percentages ("ninety five percent" → "95%"), and
  common dates ("March fourteenth" → "March 14th"). This is intentionally not a
  full natural-language number engine.
- Each run produces an explainable result (raw text, final text, and a list of
  changes with category/original/replacement/rule). This is internal only and is
  never exposed in the inserted text or written to normal logs.
- Added two settings, both **on by default** and both fully local:
  `technical_correction_enabled` and `structured_formatting_enabled`, with
  Configuration-tab toggles so the layer can be turned off from the UI.
- Added tests covering known aliases, acronyms, already-correct text,
  false-positive resistance, structured expressions, custom vocabulary,
  punctuation, Unicode, idempotency, empty text, explainability, and the
  Configuration-tab toggles.
- Extended the local model benchmark to report raw vs processed WER, per-clip
  changes, and processing time, with no benchmark-specific transcripts hard-coded
  as corrections. On the user-recorded technical clips (A–E, with references),
  the default Parakeet int8 model's overall WER on the referenced set went from
  11.0% (raw) to 4.7% (processed) with no per-clip regression; clips with no
  applicable correction were left unchanged. The unreferenced clip (F) has no WER
  computed.

### User-controlled custom vocabulary (Phase 6J)
- Added a user-managed custom vocabulary (spoken form -> written form) in
  `core/transcript_processor/vocabulary.py`. A structured `VocabularyEntry`
  (spoken, written, enabled, category, created_at, usage_count) replaces the
  flat pair list, with backward-compatible migration from the legacy
  `vocabulary_replacements` tuples. It is **user-controlled only**: nothing is
  learned automatically, no corrections are collected, no transcript is stored
  for learning, and nothing is transmitted.
- Matching engine (`apply_user_vocabulary`), reimplemented natively but
  conceptually adapted from the WritHer "Layer A" user vocabulary:
  case-insensitive, whole-word (`\b` boundaries), multi-word spoken forms with
  flexible internal whitespace, and deterministic longest-first precedence
  (longer spoken forms win; stable for ties). Disabled entries are skipped.
  Returns explainable Phase 6G `Change` records (rule `user_vocabulary`) and a
  local usage-count delta. Substring matches inside larger words are not
  replaced.
- Added deterministic conflict detection (`detect_conflicts`): duplicate spoken
  forms and whole-word overlaps (e.g. "new" ⊂ "new york"), surfaced in the UI.
- Persistence reuses SayIt's existing Pydantic/JSON settings (new
  `custom_vocabulary` list field) — **no SQLite dependency was introduced**
  despite the WritHer reference using SQLite, because the existing settings
  store is sufficient. The legacy `vocabulary_replacements` list is kept in sync
  (enabled entries only) for backward compatibility.
- Reworked the Vocabulary settings tab: add / edit (in-place) / delete /
  enable-disable per entry, an optional category, and a live conflict summary.
  Accessible names set on controls.
- Pipeline position unchanged: custom vocabulary runs in the same place as the
  previous vocabulary step — after Phase 6G technical correction and Phase 6I
  structured formatting, before optional LLM enhancement. Verified by a worker
  integration test.
- Added a vocabulary latency benchmark (`tools/benchmark_vocabulary.py`).
  Measured median processing time on a representative sentence: ~0.07 ms at 10
  entries, ~0.74 ms at 100, ~4.45 ms at 500, and ~61.8 ms at 1000 entries
  (growth is roughly linear-to-superlinear in entry count; realistic
  vocabularies of tens of entries are sub-millisecond). These are machine
  measurements on one dev machine, not a guarantee.
- Added 38 tests covering whole-word / multi-word / longest-first / overlaps /
  duplicates / conflicts / disabled entries / punctuation / capitalization /
  substring false-positives / idempotency / persistence / legacy migration /
  explainability, plus Vocabulary-tab UI and the worker pipeline-order check.

### Context-aware structured formatting (Phase 6I)
- Extended the local, deterministic corrector with context-aware formatting of
  clearly-structured technical expressions dictated with spoken delimiters
  (`core/transcript_processor/structured_formatter.py`): URLs
  ("example dot com slash repo" → "example.com/repo"), file paths
  ("src slash app dot py" → "src/app.py"), email addresses
  ("noah at example dot com" → "noah@example.com"), API-path/version structures
  ("a p i slash v one" → "API/v1", "v one point two" → "v1.2"), and extended the
  percentage rule to whole hundreds ("one hundred percent" → "100%").
- Strong-evidence only: a spoken "dot"/"slash"/"at" is collapsed solely inside a
  structure anchored by a known TLD, a known file extension, an email shape, a
  known technical acronym, or a leading "www". Ordinary prose such as
  "put a dot here", "walk down the path", "use a slash in the sentence", and
  "meet me at noon" is left unchanged. No fuzzy matching, no edit distance, no
  LLM, no network.
- The new stage runs after technical-entity normalization and before the Phase
  6G number/percent/date rules; it never consumes the word "point", so Phase 6G
  number formatting is unaffected. Deterministic and idempotent. Transformations
  are reported through the existing explainable `Change` records with Phase 6I
  rule ids (`url_structure`, `file_path`, `email_address`, `tech_slash`,
  `version_v`). The feature is gated by the existing "Structured formatting"
  toggle — no new per-rule settings were added. Generic identifier/underscore
  conversion was intentionally **not** implemented (too ambiguous to do
  conservatively) and is documented as unsupported.
- Added a Phase 6I benchmark mode (`tools/benchmark_models.py --phase6i`) that
  reports raw vs Phase 6G-only vs Phase 6I-full WER, the applied structured
  transformations, and per-stage latency. On the default Parakeet int8 model,
  the referenced A–E set WER was 11.0% (raw) → 4.7% (Phase 6G) → 4.7% (Phase
  6I): Phase 6I made **no change** to the recorded clips (none contain dictated
  URL/path/email structures), i.e. no regression and no spurious formatting.
  Phase 6I overhead measured at sub-millisecond per clip. F has no reference, so
  no F WER is computed.
- Added 33 deterministic tests covering URL/path/email/tech-slash/version
  formatting, a strong negative/false-positive corpus, idempotency,
  explainability, the structured-formatter unit API, and the
  `enable_structured` isolation flag.

### Dictation latency & streaming investigation (Phase 6H)
- Investigated true real-time/streaming dictation. Finding: the application
  loads every model with Sherpa-ONNX's **offline** recognizer
  (`OfflineRecognizer.from_whisper` / `OfflineRecognizer.from_transducer`).
  Whisper has no streaming recognizer in Sherpa-ONNX, and the default
  Parakeet TDT 0.6B v2 **offline** export cannot be loaded by the **online**
  recognizer (`OnlineRecognizer.from_transducer`) — the native library aborts
  because the encoder export has no streaming cache tensors. Simulating partial
  results by re-decoding growing audio prefixes with the offline recognizer cost
  ~2.7x the CPU of a single decode for only four prefixes, which is not an
  acceptable tradeoff. **Conclusion: true stateful streaming is not practical
  with the current model catalog, so none was implemented.** SayIt does **not**
  claim real-time/streaming dictation; it performs one-shot offline
  transcription on hotkey release.
- Added privacy-safe pipeline timing instrumentation
  (`core/asr/pipeline_timing.py`): per-job stage timestamps and derived
  latencies (recording duration, time-to-final-transcript, stop→final-text,
  Phase 6G correction overhead, end-to-end), plus counters (ASR invocations,
  chunk count, final character count). It records timestamps/durations/counters
  and a job id only — never transcript content. The offline path reports
  "time to first partial" as not-applicable rather than fabricating a value.
- Hardened the long-audio chunked path against duplicate words at chunk seams:
  `AudioProcessor.combine_transcriptions` now conservatively removes an exact,
  case-insensitive, whole-word overlap (up to four words) at each seam, so
  overlapping chunks cannot produce doubled text like "to GitHub to GitHub".
  Non-repeated text is never altered.
- Added a Phase 6H benchmark mode (`tools/benchmark_models.py --phase6h`) that
  measures, for the one-shot offline path, per-clip decode time, RTF, final-text
  latency, Phase 6G overhead, and a determinism/duplicate check (each clip
  decoded three times; identical output required). On the default Parakeet int8
  model (CPU), measured median RTF ≈ 0.081 (~12x faster than real time),
  time-to-final ≈ 0.38–1.36 s for 4.7–16.7 s clips, correction overhead
  ≈ 0.3–3.8 ms, and 9/9 clips deterministic over three runs (zero duplicate or
  unstable output). F has no reference, so no WER is computed for it.
- Added tests for the timing helper, seam de-duplication / exactly-once
  insertion (duplicate-prevention regression), chunk accounting, worker timing
  integration, and a model-gated test documenting that the offline Parakeet
  export cannot be loaded as a streaming/online recognizer.

### Privacy
- Cloud enhancement is explicitly **off by default**.
- Added a `history_enabled` setting; persistent transcript history is **off by
  default**.
- Added transient in-memory transcript recovery that is independent of the
  persistent-history setting.
- Added a dedicated **Privacy & Data** settings tab: history toggle, accurate
  local-vs-cloud enhancement disclosure, provider disclosure, and Clear Data
  access with an accurate confirmation.
- Made the History tab show an honest "history is off" state without fabricating
  entries.

### Documentation
- Rewrote the README to accurately describe the current implementation, tested
  scope, privacy behavior, platform support, and known limitations; removed
  references to files that do not exist (`permissions_dialog.py`, `bootstrap.py`)
  and corrected the hotkey to `Ctrl + Space`.
- Added this changelog, a release checklist, and a third-party/licensing notes
  file.

### Notes
- The product working name is **SayIt** (provisional, pending owner review).
  Repository and technical identifiers remain **SayIt** and are unchanged.
