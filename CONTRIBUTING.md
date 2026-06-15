# Contributing

Use focused branches and conventional, imperative commit messages. Changes must preserve evaluator independence and event-schema compatibility.

Before opening a pull request:

```bash
ruff check .
pytest
docker build -t procurement-agent:test .
```

Architecture changes should include tests proving event fan-out, baseline integrity, and autonomous remediation behavior.
