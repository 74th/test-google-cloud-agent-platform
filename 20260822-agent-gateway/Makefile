.PHONY: test fmt validate

test:
	uv run pytest -q

fmt:
	terraform -chdir=terraform fmt -check

validate:
	terraform -chdir=terraform validate
