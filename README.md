# ReproFrame AI

**Scientific visuals you can verify, not just admire.**

**Live app:** [reproframe-ai.onrender.com](https://reproframe-ai.onrender.com)

![ReproFrame AI generate-evaluate-retry-verify workflow](assets/devpost-cover.png)

ReproFrame turns a bounded set of evidence-backed claims into a visual abstract and
keeps every prompt, attempt, quality check, revision, model decision, and asset hash in
one replayable manifest. It is being built for the Backblaze Generative Media
Hackathon using Genblaze for media orchestration and Backblaze B2 as the durable system
of record.

## Current state

The public app now runs end to end in credentialed `gemini-svg` mode, while the same
control boundary remains available in zero-credential fixture mode for local testing:

1. validate an evidence-bound visual brief;
2. construct a constrained generation prompt;
3. generate a real SVG candidate;
4. evaluate required labels, prohibited content, and integrity metadata;
5. persist the asset and reproducibility manifest;
6. expose both through a working FastAPI UI.

Fixture results remain explicitly labeled development proof. Fixture attempt one
deliberately omits one required label when possible, so the public workflow visibly
demonstrates evaluation feedback and a lineage-linked retry instead of only showing a
perfect first result. A credentialed
`gemini-svg` run has now generated a safe, self-contained scientific SVG through a
free-tier Gemini text model, passed the Genblaze evaluation loop with a 1.0 score, and
stored the candidate, Genblaze provenance, and final manifest in encrypted B2. The
private bucket is served through a narrow application proxy, so credentials and signed
URLs never enter manifests.

The GMI adapter is also authenticated and ready behind `REPROFRAME_MODE=gmi`, but the
account currently has no generation credits. `gemini-svg` is therefore the verified
real-mode path; it falls back between compatible free-tier text models on transient
provider failure.

## Run locally

Requirements: Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/).

```bash
make setup
make test
make demo
make api
```

Open <http://127.0.0.1:8000>.

Copy `.env.example` to `.env` and set `REPROFRAME_MODE=gemini-svg`, `GEMINI_API_KEY`,
and the bucket-scoped B2 variables to run the credentialed cloud path. Keep
`REPROFRAME_MODE=fixture` for offline development and tests.

## Verification and evaluation

The application now exposes a durable run ledger, attempt-by-attempt comparison,
token-protected human review, stored-byte verification, and a downloadable ZIP proof
bundle. The CLI uses the same code paths:

```bash
reproframe history --limit 5
reproframe verify <run-id>
reproframe bundle <run-id> --output evidence.zip
make benchmark
```

`reproframe verify` separately checks the ReproFrame canonical manifest hash, every
locally addressable asset byte hash, and each Genblaze manifest. This distinction is
intentional: validating a manifest is not the same as fetching and re-hashing the media
it names.

The checked-in five-case fixture benchmark covers spectroscopy, microscopy, materials,
ecology, and robotics communication. Its latest deterministic results live at
[`benchmarks/results/latest.json`](benchmarks/results/latest.json). They measure the
ReproFrame control boundary, not scientific truth, model quality, or human visual
preference.

The latest public verification used two Genblaze iterations: attempt one failed the
deterministic gate at `0.8333`; attempt two passed the Gemini visual review at `1.0`.
Both assets and both Genblaze manifests were then fetched from B2 and re-hashed
successfully. The resulting proof bundle contains ten files and passes `unzip -t`.
Exact scope, run identifiers, and commands are recorded in
[`docs/VERIFICATION_LEDGER.md`](docs/VERIFICATION_LEDGER.md).

## Architecture

```mermaid
flowchart LR
  Brief[Evidence-bound brief] --> Prompt[Constrained prompt]
  Prompt --> Genblaze[Genblaze pipeline]
  Genblaze --> Candidate[Generated candidate]
  Candidate --> QA[Deterministic + model QA]
  QA -->|feedback| Genblaze
  QA -->|accepted| B2[Backblaze B2]
  B2 --> Bundle[Asset + evaluation + manifest]
```

The local fixture implements the same control boundary with a local artifact store.
Cloud credentials are never accepted by the browser or written into manifests.

The production image is built from the digest-pinned `python:3.12-slim` base, runs as
UID 1000, and exposes a Docker health check on port 7860. The live service is deployed
from the public GitHub branch to Render's free Docker runtime with `/health` as its
application-level health check. See `Dockerfile`, `deploy/render/`, and
`deploy/huggingface/`.

## Project plan

See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for milestones, safety boundaries, and
submission acceptance gates.

## Open-source use

ReproFrame depends on the official MIT-licensed
[Genblaze](https://github.com/backblaze-labs/genblaze) SDK. No Genblaze source is
copied into this repository. Backblaze B2 integration uses its documented
S3-compatible API.

## License

Apache-2.0.
