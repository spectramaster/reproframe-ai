# Verification ledger

This ledger records narrow, reproducible evidence. It is not a broad quality benchmark
and contains no credentials.

## Credentialed Gemini + Genblaze + Backblaze B2 run

- UTC created at: `2026-07-15T19:14:06.389805Z`
- Run ID: `10b9346c-23f5-480b-ab84-d51e4d7187d3`
- Generation provider/model: Google Gemini / `gemini-3.1-flash-lite`
- Attempt 1 deterministic score: `0.8182`
- Attempt 2 deterministic + model-review score: `0.975`
- Model-review checks: legible, clear hierarchy, no obvious overlap, claims visually distinct
- Final status: accepted after two Genblaze AgentLoop iterations
- B2 verification: two asset hashes and two Genblaze manifests verified
- Stored objects: nine

Re-run the storage verification with the bucket-scoped credentials configured locally:

```bash
reproframe verify 10b9346c-23f5-480b-ab84-d51e4d7187d3
```

## Locked container smoke test

- Base image: `python:3.12-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28`
- Runtime user: UID 1000
- Health endpoint: HTTP 200 in fixture mode
- Generated run ID: `a355c149-0327-4dea-8e0f-ec214b234a6d`
- Attempts: two
- Stored-byte verification: valid
- Downloaded evidence ZIP: ten entries; `unzip -t` reported no errors

The container smoke test used fixture mode and therefore made no provider or B2 call.

## Deterministic five-case benchmark

The current checked-in report is [`../benchmarks/results/latest.json`](../benchmarks/results/latest.json).
It covers only ReproFrame's deterministic control boundary. The report explicitly does
not claim to measure scientific truth, Gemini/GMI quality, or human visual preference.
