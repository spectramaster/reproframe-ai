# ReproFrame AI execution plan

## Outcome

Submit a production-minded scientific visual workflow to the Backblaze Generative
Media Hackathon by **August 3, 2026, 17:00 EDT**. The judged app must generate media
through Genblaze, persist assets and provenance to Backblaze B2, expose a working URL,
and include a concise public demo.

## Product position

**ReproFrame turns evidence-backed research claims into visual abstracts while keeping
every generation, review, revision, model choice, and content hash replayable.**

Primary users: researchers, journal editors, research communication teams, and
technical educators who need generated visuals without losing claim fidelity.

## Non-negotiable safety boundaries

- Never commit provider, B2, AWS, GitHub, or deployment credentials.
- Use bucket-scoped B2 application keys with only the capabilities required.
- Fixture mode must remain functional without network access or paid API calls.
- Generated scientific visuals are communication aids, not evidence or medical advice.
- Human acceptance remains explicit; automatic checks do not claim scientific truth.
- Keep this repository and its cloud resources isolated from `lineageguard-ai`.

## Milestones

### M0 — rules and foundation (July 15)

- [x] Verify deadline, required services, deliverables, prizes, and judging criteria.
- [x] Freeze the research-visual use case and evidence-bound product promise.
- [x] Create an independent local project with fixture mode and no secrets.
- [x] Run the first complete local test and UI verification.

### M1 — real Genblaze workflow (July 16–18)

- [x] Implement the credential-gated Genblaze image adapter for GMI Cloud.
- [x] Drive generate → evaluate → retry with `AgentLoop` and manifest lineage.
- [ ] Add a model-based visual evaluator behind an explicit provider interface.
- [ ] Preserve deterministic checks as a mandatory pre-acceptance gate.

### M2 — Backblaze B2 as the system of record (July 18–20)

- [x] Create a private, encrypted B2 bucket and a 90-day bucket-scoped application key.
- [x] Use Genblaze `ObjectStorageSink` with hierarchical run layout.
- [ ] Store input brief, every candidate, evaluation report, final asset, and manifest.
- [ ] Verify asset SHA-256 and Genblaze manifest integrity from a clean environment.

### M3 — product-quality app and evaluation (July 20–25)

- [ ] Add run history, attempt comparison, manual acceptance, and downloadable bundle.
- [ ] Build at least five representative scientific-communication fixtures.
- [ ] Measure claim/label coverage, retry success, latency, cost, and storage integrity.
- [ ] Add abuse limits, input bounds, timeouts, structured errors, and privacy controls.

### M4 — deploy and package (July 25–29)

- [ ] Build and verify a locked container image.
- [ ] Deploy the working app with health checks and protected server-side credentials.
- [ ] Create the public GitHub repository with complete setup and architecture docs.
- [ ] Run a clean-room reproduction and secret scan.

### M5 — submission (July 29–August 2)

- [ ] Record a real three-minute demo: problem → generation → failed check → retry → B2 proof.
- [ ] Prepare Devpost copy mapped directly to all four judging criteria.
- [ ] List exact providers/models and meaningful Genblaze/B2 usage.
- [ ] Submit at least 24 hours before the deadline and verify the final public page.

### M6 — CockroachDB extension (August 4–18)

- [ ] Review cross-submission and pre-existing-code rules before modifying the product.
- [ ] Add persistent user preferences, failure memory, model performance, and repair recall.
- [ ] Deploy the memory service on AWS with CockroachDB as the durable store.
- [ ] Produce a distinct evaluation and submission focused on agentic memory quality.

## Win-oriented acceptance gates

1. The hosted app works without judge setup beyond opening the URL.
2. B2 stores more than final outputs: it is the durable provenance and orchestration layer.
3. Genblaze controls real generation, retries, lineage, and manifests—not a token import.
4. A failed quality check visibly changes the next attempt.
5. Every numeric claim in the submission is reproduced by a checked-in evaluation command.
6. The three-minute demo shows real evidence, not slides or mocked cloud screenshots.
