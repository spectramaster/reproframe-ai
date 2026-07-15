# Render deployment

The public demonstration runs at <https://reproframe-ai.onrender.com> from branch
`codex/reproframe-foundation` using the repository-root `Dockerfile`.

## Runtime configuration

- Instance: Render Free web service
- Runtime: Docker
- Port: `7860` (detected from the running container)
- Health check: `/health`
- Region: Oregon
- Credentials: dashboard-managed environment variables; never committed or passed to
  the browser

Required runtime variables are documented by name in `.env.example`. Provider and B2
values must be configured through Render's Environment page. Do not put secrets in
`render.yaml`, Docker build arguments, repository files, screenshots, or manifests.

## Verification

```bash
curl -fsS https://reproframe-ai.onrender.com/health
curl -fsS \
  https://reproframe-ai.onrender.com/api/runs/7e65b640-a45d-4c91-bc47-276b4fdc27a5/verify
```

The free instance spins down after inactivity, so the first request can take about a
minute. Subsequent requests are immediate while the instance remains warm.
