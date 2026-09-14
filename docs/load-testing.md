# Load testing with Locust

The locustfile lives in `backend/tests/performance/locustfile.py`; `.github/workflows/ci-load-test.yml` runs a
50-user, 60-second smoke on manual dispatch against a local app instance and uploads the CSV and HTML reports.

```bash
make load-test                      # 50 users, 2 minutes, headless, against the local app
cd backend && uv run locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 60s --html=locust-report.html
```

Against a deployed app, pass `--host` with the app URL and the caller's OAuth token in the `Authorization`
header (the Apps ingress rejects unauthenticated requests). Measure time to first token for the chat stream, not
only p95 latency; keep the model endpoint out of the loop when you want infrastructure numbers.
