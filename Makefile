.PHONY: help test verify
help:
	@echo 'make test: testes host sem aparelho; make verify: hashes da publicação'
test:
	python3 tools/run-host-checks.py
verify:
	python3 tools/verify-manifest.py
