# SportHub AI — Sports Knowledge Expansion Roadmap

## Scope and principles

This plan expands verified knowledge for Natural Mode across Football, Badminton, Pickleball, Tennis, Basketball, and Volleyball. The FIFA World Cup finals pilot validates the import, provenance, and deterministic lookup pattern; it does not complete the broader sports knowledge goal. Professional Mode stays outside this roadmap.

Use Markdown RAG for explanatory rules, technique, terminology, and original summaries linked to authoritative references. Use compact structured records for facts that need exact filters, comparisons, counts, or time ranges, such as match results and tournament placements. Keep source, revision, license, attribution, checksum, scope, validation, and approval state in a shared manifest shape while allowing sport-specific schemas.

Official rulebooks are useful sources for correctness, but a public PDF is not permission to redistribute or ingest its text. Until reuse terms are verified, author short original explanations, cite the official page, and do not copy full text or diagrams. Community datasets remain candidates only until their data license and provenance are confirmed.

## Sport-by-sport plan

| Sport | Knowledge to add | Public source candidates and current license status | RAG versus structured data | Questions enabled after a verified stage |
|---|---|---|---|---|
| **Football** | Laws, positions, tactics, competitions, national-team/tournament history, final scores and standings | IFAB Laws of the Game and FIFA Connect data are authoritative references; IFAB/FIFA redistribution terms need review. OpenFootball `worldcup.json` is the approved CC0/public-domain candidate for the seven pilot editions only. Do not extend its scope without another review. | Original rule/tactics summaries in Markdown; match results, standings, and tournament awards as structured records. | Stage 1: rules and roles. Pilot: champions, runners-up, final results for the seven included editions. Later: other competitions only after source/license review. |
| **Badminton** | Scoring/service rules, singles/doubles tactics, equipment, tournament formats, player and event history | BWF Laws/Handbook is authoritative; redistribution terms are unverified. A community BWF match CSV claims 2007–2026 coverage, but its README points to a separate licensing/attribution section that must be checked before use. [BWF Laws](https://worldbadminton.com/rules/), [candidate match dataset](https://github.com/SahilMotyar/bwf-match-data). | Markdown for rules and technique; structured matches, set scores, disciplines, and event placements if license/provenance pass. | Rules, scoring and service explanations first; later exact tournament/match questions within verified coverage. |
| **Pickleball** | Serve and scoring rules, kitchen/non-volley zone, faults, doubles positioning, equipment and strategy | USA Pickleball official rulebook is authoritative, but the 2025 PDF carries “all rights reserved”; no reuse permission was verified. Do not ingest the PDF as a corpus. Seek explicit permission or use independently authored summaries after checking allowable quotation and citation. [Rulebook](https://usapickleball.org/docs/2025-USA-Pickleball-Rulebook.pdf). | Original Markdown explanations first. Structured competition records only when a source has clear terms and documented coverage. | Basic rules, scoring, court zones, and tactics after editorial verification; no historical statistical claims until a source is approved. |
| **Tennis** | Rules, scoring, surfaces, tournament formats, strokes/tactics, player and match history | ITF rules page and Tennis Open Data Standards (TODS) are promising references; the rules page does not itself establish reuse permission, and TODS is described as evolving. ITF match data/API rights and terms need review. [ITF rules](https://www.itftennis.com/en/about-us/governance/rules-and-regulations/), [TODS](https://itftennis.atlassian.net/wiki/spaces/TODS/overview?homepageId=535920732). | Markdown for rules/technique; structured match scores, events, surfaces, and rankings where an approved source and schema are available. | Rules/scoring first; then exact records for specifically licensed tournament datasets. |
| **Basketball** | Rules, positions, court/shot terminology, tactics, league formats, team/player records | FIBA official rule downloads are authoritative; reuse terms for documents need verification. FIBA GDAP requires registration and has limited, revocable API licensing, so it is not a zero-friction local dataset source. A public NBA dataset candidate advertises facts-only data, but the data license and source rights still require file-level verification. [FIBA rules](https://refereeing.fiba.basketball/en/rules), [GDAP terms](https://gdap-portal.fiba.basketball/terms-of-services), [dataset candidate](https://github.com/roham/every-game-ever). | Markdown for rules and strategy; structured game/box-score/player data only from a clearly licensed, versioned source. | Rules and scoring first; later game results and statistics within source coverage. |
| **Volleyball** | Rotation, scoring, positions, faults, serve/receive, formations, indoor versus beach rules | FIVB official rules and refereeing documents are authoritative references; reuse terms remain unverified. FIVB’s legacy data/service documentation is a lead, not approval for API access or redistribution. [FIVB reports and documents](https://www.fivb.com/inside-fivb/refereeing/reports-documents/), [service documentation](https://www.fivb.org/VisSDK/VisWebService/webindex.html). | Markdown for rules and tactics; structured set scores, tournaments, rosters, and match results only after a source is checked for license and completeness. | Scoring/rotation explanations first; later tournament-result queries on verified structured data. |

The cited candidates above are planning leads only. Except for the OpenFootball World Cup pilot, none is approved for local import by this report. Terms for current official rulebooks, community datasets, athlete data, and APIs must be rechecked at the exact file/revision before any download.

## Rollout order

1. Complete and validate the World Cup finals pilot, including Natural-only routing and Professional/booking regression checks.
2. Football rules and basic tactical knowledge from original summaries, then a source review for additional structured competition results.
3. Badminton rules and scoring; assess the community match dataset license and tournament coverage before structured import.
4. Pickleball rules and terminology from original summaries after reviewing current official rules and reuse constraints.
5. Tennis rules/scoring and TODS schema review; do not assume ITF data API or tournament data can be redistributed.
6. Basketball rules and terminology; assess local public-record datasets before considering stats.
7. Volleyball rules, rotation and positions; evaluate a structured match source after its terms and completeness are verified.

Each stage has its own acceptance gate. Do not download data for the five non-pilot sports under CP-KB-03B.

## Shared implementation pattern

- Keep one small manifest convention: dataset/sport, source URL and revision, data license, attribution, import timestamp, source/output checksums, schema version, row count, validation report, and approval status.
- Preserve source references per record. Do not silently merge conflicting records; fail closed and resolve against an independent reliable reference whose content is used only for validation unless its reuse terms are also approved.
- Keep exact historical lookups deterministic and local. Reuse the existing Natural Mode sports knowledge branch after the Professional guard. Keep explanatory questions on the existing Markdown RAG pipeline.
- Avoid a generic data platform until several sports demonstrate a real need. Small sport-specific normalizers and schemas can share validation helpers and manifest fields.
- Evaluate local models only after these deterministic and RAG stages have measured gaps; first compare quality and resource needs without downloading a model.

## Open verification work

- Verify license and attribution at the exact revisions/files of every non-pilot candidate.
- Check competition and season coverage, missing records, duplicate handling, schema stability, and independent result samples.
- Decide whether each source supports local retention and redistribution, not merely public viewing or API access.
- Track country/language coverage: many official rule sources are English-first; Vietnamese terms and translations will need review.

## Sports knowledge metadata contract status

The Markdown loader and ``KnowledgeEntry`` support optional source, rights, and editorial metadata while preserving the legacy 8-column, 13-column, and current header-based tables. New fields are ``source_title``, ``source_version``, ``verified_at``, ``effective_from``, ``effective_to``, ``rule_set``, ``jurisdiction``, ``rights_status``, ``license``, ``rights_evidence_url``, ``rights_checked_at``, ``approved_uses``, ``authoring_type``, and ``record_status``. ``source_version`` is the single version field for a published edition or pinned dataset revision; no ``citation_label`` is stored because a display label can be derived from ``source_title`` or ``source_name``.

Absent metadata remains ``None``. ``collected_at`` is not used to populate ``verified_at`` or ``rights_checked_at``. Date fields written by the Markdown writer use the canonical ``YYYY-MM-DD`` form. Valid rights states are ``approved``, ``reference_only``, ``pending_review``, and ``restricted``; valid record states are ``active``, ``draft``, ``conflicted``, ``superseded``, and ``withdrawn``. State values are trimmed and lowercased; the writer rejects unknown states, while the parser preserves unknown state text so policy validation can distinguish it from missing metadata. ``authoring_type`` currently has no closed value set and is an optional string. ``approved_uses`` is an optional comma-separated Markdown cell parsed as an immutable tuple; the writer trims and lowercases items, rejects empty items or items containing commas, a missing or blank cell remains ``None``, and ``[]`` represents an explicitly empty tuple. ``classification`` and ``priority`` retain their existing retrieval meanings and are not rights signals.

This metadata support does not verify any source license, assign ``approved``, approve existing records, or add a retrieval filter. Rights evidence and uses must be reviewed per source/content before new data is imported. The optional web-update Markdown writer validates metadata and cell delimiters before creating or opening the destination file, and appends the extended header when needed; existing legacy tables remain untouched. It writes the prepared header/row block in one file operation, but does not use whole-file atomic replacement, so an operating-system I/O failure during that operation could still leave a partial append. Unsafe Markdown cell delimiters are rejected rather than escaped, because the loader uses a simple pipe split.
