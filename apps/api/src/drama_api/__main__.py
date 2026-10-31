"""``uv run python -m drama_api`` starts the RQ worker."""

from drama_api.worker import main

if __name__ == "__main__":
    raise SystemExit(main())
