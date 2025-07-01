.PHONY: load-test

load-test:
	poetry run locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 2m
