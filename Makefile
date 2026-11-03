.PHONY: sync check live demo fake-demo
sync:
	uv sync
check:
	uv run ruff check . && uv run pytest -q -m "not live and not live_llm"
live:
	uv run pytest -q -m live
demo:
	uv run python -m ringfence.app
fake-demo:
	uv run python -m ringfence.app --backend fake --agent scripted
