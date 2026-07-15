# Verification ledger

This ledger records narrow, reproducible evidence. It is not a broad quality benchmark
and contains no credentials.

## Public Render + Gemini + Genblaze + Backblaze B2 run

- Live app: <https://reproframe-ai.onrender.com>
- Demo video: <https://youtu.be/tocmG6Ws6fc> (2:45, unlisted, publicly accessible)
- Devpost submission: <https://devpost.com/software/reproframe-ai> (`Submitted`, 5/5 steps)
- UTC created at: `2026-07-15T19:40:09.927676Z`
- Run ID: `7e65b640-a45d-4c91-bc47-276b4fdc27a5`
- Deployed Git commit: `fcc6d7a1dafb62cb8df3b4d9572eb18048048af5`
- Runtime health: `gemini-svg`, version `0.1.0`, HTTP 200 at `/health`
- Generation provider/model: Google Gemini / `gemini-3.1-flash-lite`
- Attempt 1 score: `0.8333`; required-claim failures triggered feedback and retry
- Attempt 2 score: `1.0`; all deterministic and Gemini visual-review checks passed
- Final status: accepted after two Genblaze AgentLoop iterations
- B2 verification: canonical manifest, two asset hashes, and two Genblaze manifests valid
- Stored objects: nine
- Downloaded evidence ZIP: ten entries; `unzip -t` reported no errors

Public verification endpoints:

```text
https://reproframe-ai.onrender.com/api/runs/7e65b640-a45d-4c91-bc47-276b4fdc27a5/verify
https://reproframe-ai.onrender.com/api/runs/7e65b640-a45d-4c91-bc47-276b4fdc27a5/bundle
```

Render's free service can cold-start after inactivity. The evidence bundle itself is
durable in Backblaze B2 and remains available again when the service resumes.

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
