# Load testing with Locust

Assets live in `backend/tests/performance/`; the CI workflow
(`ci-load-test.yml`) runs a 50-user smoke against a local app instance.

```bash
cd backend && uv run locust -f tests/performance/locustfile.py \
  --headless -u 50 -r 10 -t 60s --html=locust-report.html
```

Field-tested tips: pin `locust<3` (already in the dev group); mock the LLM
endpoint to measure *infrastructure* throughput separately from model
latency; track time-to-first-token for streaming endpoints, not just p95;
switch OAuth U2M→M2M for runs longer than an hour.
