"""BCF local NLP package.

Phase 0 scaffold: schema, FastAPI server, HTTP client, and runner stubs.
The training entry points (`encode`, `train_span`, `train_section`,
`evaluate`), the llama.cpp bootstrap loop (`bootstrap`), and the Textual
review TUI (`tui/*`) are implemented by parallel agents and import the
contracts defined here.

`nlp.schema` and `nlp.client` depend only on pydantic and httpx so the
iMac can import them without torch. `nlp.serve` and `nlp.runners` defer
all heavy imports (torch, transformers) until first use.
"""

from .schema import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION"]
