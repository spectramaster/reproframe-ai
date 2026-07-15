# Hugging Face Docker Space deployment

Create a public Docker Space and upload the repository root with this directory's
`README.md` as the Space root card. Configure these runtime secrets in Space Settings:

- `GEMINI_API_KEY`
- `B2_KEY_ID`
- `B2_APP_KEY`
- `B2_BUCKET`
- `B2_REGION`
- `REPROFRAME_REVIEW_TOKEN`

Configure these public variables:

- `REPROFRAME_MODE=gemini-svg`
- `REPROFRAME_MODEL_REVIEW_ENABLED=true`
- `REPROFRAME_MAX_CONCURRENT_RUNS=2`

Never add secret values to a Docker build argument, committed file, manifest, browser
form, or Devpost field.
