# Feature: eje-cafetero-pipeline

## Objective
Deliver Scenario 3 (two Docker containers, GitHub) and then Scenario 5 (Jenkins CI) for a
medallion data pipeline: extract -> bronze -> quality gate -> silver -> gold -> dashboard.
Thesis to demonstrate: corrupted data that skips quality checks produces wrong decisions.

## Constraints
- Solo work. Dataset: datos.gov.co `gdqq-rry2` (83,813 rows, clean at source).
- Two containers: `app` (own Dockerfile) + `db` (postgres official). Credentials only in `.env`.
- Flow: one branch + one PR per task, Conventional Commits, no AI attribution in commits.
- Planning heuristic: ~400 authored changed lines per task.
- Artifacts in English (code); class documents (README, report, ai-log) in Spanish.

## Key risk to resolve early
The live API changes over time, so the "expected result" of the example operation would drift.
Decision (T1): pin the extraction with a fixed `$where`/`$order` window AND keep a small
fixture CSV in the repo for tests/CI, so the operation always returns the same numbers.

## Authorized scope
Everything under this repository. Push, PR creation and merge stay with the user.

## Scenario 3 tasks
- [x] T1 `feat/bronze-extraction`: extractor (paginated Socrata CSV, pinned window), bronze loader with batch metadata, fixture CSV, unit tests. Check: bronze row count == source count.
- [x] T2 `feat/silver-quality-gate`: Great Expectations suite (nulls, types, price > 0, min <= medio <= max, parseable dates, valid categories, duplicates), silver transform (Spanish dates, casts, normalization), gate blocks silver on failure, writes `meta.quality_runs`. Check: clean batch passes, corrupted batch is rejected.
- [ ] T3 `feat/gold-aggregates`: `gold.precio_mensual` and `gold.variacion_mensual`. Check: known product/city/month matches a hand-computed value.
- [ ] T4 `feat/pipeline-cli`: `python -m pipeline.run` orchestrator, `--source clean|corrupted`, corruption injector (nulls, duplicates, price x10, min>max, bad dates, negatives). Check: example operation prints the expected result.
- [ ] T5 `feat/dashboard`: Streamlit on gold + last quality-gate status, plus a "what a corrupted batch would have shown" comparison. Check: container serves on 8501.
- [ ] T6 `docs/readme-and-report`: README (clone-and-run), architecture diagram, screenshots, report, ai-log filled.
- [ ] T7 `chore/clean-clone-validation`: clone into an empty folder and bring the system up using only the README.

## Scenario 5 tasks (after Scenario 3 is delivered)
- [ ] T8 `feat/verify-operation`: standalone verification command that exits non-zero when the result differs from the expected one.
- [ ] T9 `feat/jenkinsfile`: stages checkout, build image, up, verify, and `post { always }` teardown; reports the failing stage; `sh` on macOS; Poll SCM trigger.
- [ ] T10 Jenkins local install and configuration (macOS): Java, Docker access for the Jenkins account, plugins, no secrets in repo.
- [ ] T11 Provoke failure with the corrupted batch, confirm build fails, fix, confirm green; capture history.
- [ ] T12 Requirements document: infrastructure with versions and official sources (APA 7), configuration, repeatable install steps, operation, risks (security, backup, growth), AI log.

## Acceptance
- S3: clean clone starts from README; both containers run; services talk by service name; example operation returns the expected result; no credentials in repo; report complete.
- S5: Jenkins polls the repo, builds, fails on corrupted data and passes on clean data, tears down always; requirements document complete with sources.

## Progress
Base committed and pushed (4 commits on `main`).
T1 done on `feat/bronze-extraction`: RED observed (import errors), GREEN 12/12 in container,
live ingest of 5000 rows matched the source window and bronze count. Route: inline.

## Next step
T1 merged (PR #1). T2 done on `feat/silver-quality-gate`: RED observed, 43 tests GREEN,
gate accepts all 83,813 real rows, rejects corrupted batches end to end (exit 1, silver kept).
Known limitation: only-precio_maximo x10 is not detected. Route: inline.
Decision: silver holds the last approved batch (TRUNCATE + load); duplicates are flagged by
the gate, not removed by silver.

Next: open PR for T2, then T3 `feat/gold-aggregates`.
