#!/usr/bin/env python3
"""
Temporal Reasoning MCP Server.

Persistent stdio MCP server providing bi-temporal graph memory for AI coding agents.
Sole interface to the minigraf .graph file via the MiniGrafDb Python binding.
"""
import asyncio
import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from minigraf import MiniGrafDb, MiniGrafError

# ---------------------------------------------------------------------------
# Session-scoped rules — registered once at startup, cached in RuleRegistry
# ---------------------------------------------------------------------------
SESSION_RULES = [
    "(rule [(linked ?a ?b) [?a :depends-on ?b]])",
    "(rule [(linked ?a ?b) [?a :calls ?b]])",
    "(rule [(reachable ?a ?b) [?a :depends-on ?b]])",
    "(rule [(reachable ?a ?b) [?a :calls ?b]])",
]

# Module-level DB instance — opened once, held for the session lifetime
_db: Optional[MiniGrafDb] = None

# Module-level server reference — set after server creation for MCP sampling
_server_ref: Optional[Server] = None

# ---------------------------------------------------------------------------
# DB lifecycle
# ---------------------------------------------------------------------------


def _get_graph_path() -> str:
    return os.environ.get("MINIGRAF_GRAPH_PATH", str(Path.cwd() / "memory.graph"))


def open_db(graph_path: Optional[str] = None) -> MiniGrafDb:
    """Open MiniGrafDb and register session-scoped rules. Called once at startup."""
    global _db
    path = graph_path or _get_graph_path()
    _db = MiniGrafDb.open(path)
    for rule in SESSION_RULES:
        _db.execute(rule)
    return _db


def get_db() -> MiniGrafDb:
    """Return the open DB instance; raises RuntimeError if not initialised."""
    if _db is None:
        raise RuntimeError("DB not initialised — call open_db() first")
    return _db


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

def _parse_query_result(raw_json: str) -> Dict[str, Any]:
    """Parse JSON returned by MiniGrafDb.execute() for a query command."""
    try:
        data = json.loads(raw_json)
        return {"ok": True, "results": data.get("results", [])}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Unexpected result format: {e} — raw: {raw_json[:200]}"}


def _parse_tx_result(raw_json: str) -> Dict[str, Any]:
    """Parse JSON returned by MiniGrafDb.execute() for a transact/retract command."""
    try:
        data = json.loads(raw_json)
        return {"ok": True, "tx": str(data.get("tx", "unknown"))}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Unexpected result format: {e} — raw: {raw_json[:200]}"}


# ---------------------------------------------------------------------------
# Explicit agent tool handlers
# ---------------------------------------------------------------------------

def handle_vulcan_query(datalog: str) -> Dict[str, Any]:
    """Query the graph. Returns {ok, results} or {ok, error}."""
    db = get_db()
    try:
        raw = db.execute(f"(query {datalog})")
        return _parse_query_result(raw)
    except MiniGrafError as e:
        return {"ok": False, "error": str(e)}


def handle_vulcan_transact(facts: str, reason: str) -> Dict[str, Any]:
    """Transact facts into the graph. reason is required."""
    if not reason or not reason.strip():
        return {"ok": False, "error": "reason is required for all writes"}
    db = get_db()
    try:
        raw = db.execute(f"(transact {facts})")
        db.checkpoint()
        result = _parse_tx_result(raw)
        if result["ok"]:
            result["reason"] = reason
        return result
    except MiniGrafError as e:
        return {"ok": False, "error": str(e)}


def handle_vulcan_retract(facts: str, reason: str) -> Dict[str, Any]:
    """Retract facts from the graph. reason is required."""
    if not reason or not reason.strip():
        return {"ok": False, "error": "reason is required for retract"}
    db = get_db()
    try:
        raw = db.execute(f"(retract {facts})")
        db.checkpoint()
        result = _parse_tx_result(raw)
        if result["ok"]:
            result["reason"] = reason
        return result
    except MiniGrafError as e:
        return {"ok": False, "error": str(e)}


def handle_vulcan_report_issue(
    category: str,
    description: str,
    datalog: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Delegate to report_issue.py."""
    try:
        from report_issue import report_issue
        report_issue(category, description, datalog=datalog, error=error)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# memory_prepare_turn
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would could should "
    "may might shall can need dare ought used to am i we you he she it they what which who "
    "this that these those my our your his her its their about above after all also and as at "
    "before but by for from if in into just me more most no not of on only or other our out "
    "same so than then there they through to too under up us very via was we what when where "
    "which while who why with".split()
)

_MIN_ENTITY_LEN = 4


def _extract_entities(text: str) -> List[str]:
    """Extract candidate entity tokens from user message text."""
    tokens = text.lower().split()
    result = []
    for t in tokens:
        stripped = t.strip(".,?!;:\"'()[]")
        if len(stripped) >= _MIN_ENTITY_LEN and stripped not in _STOP_WORDS:
            result.append(stripped)
    return result


def _format_facts(results: List[List[str]]) -> str:
    """Format a list of [attr, val] or [e, attr, val] rows as a readable block."""
    if not results:
        return ""
    lines = []
    for row in results:
        lines.append("  " + " | ".join(str(v) for v in row))
    return "\n".join(lines)


_HISTORICAL_SIGNALS = re.compile(
    r"\b(last\s+\w+|yesterday|before|earlier|as\s+of|at\s+the\s+time|back\s+when|previously)\b",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b"
)


def _is_historical_query(user_message: str) -> bool:
    return bool(_HISTORICAL_SIGNALS.search(user_message))


def _now_utc_ms() -> str:
    """Return current UTC time as an ISO 8601 string with millisecond precision and Z suffix.

    minigraf requires UTC (no timezone offsets) and millisecond precision to
    reliably find facts transacted in the same second as the query.
    e.g. "2026-05-02T15:44:52.184Z"
    """
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _build_query_clauses(user_message: str) -> str:
    """
    Return temporal clauses to append to a Datalog query.

    For current-state queries use :valid-at with the current UTC timestamp
    (millisecond precision). This correctly finds all facts whose valid window
    includes right now — including facts transacted earlier the same second —
    while excluding expired/retracted facts and future-dated facts.

    For historical queries where an explicit ISO date is detected in the user
    message, use :valid-at with that date (resolves to midnight UTC on that
    date — intentional for point-in-time historical semantics).

    minigraf :valid-at accepts: ISO 8601 date ("YYYY-MM-DD" → midnight UTC)
    or UTC datetime with Z suffix ("YYYY-MM-DDTHH:MM:SS.mmmZ").
    Timezone offsets are not supported; :any-valid-time disables filtering.
    """
    if _is_historical_query(user_message):
        date_match = _DATE_PATTERN.search(user_message)
        if date_match:
            valid_at = date_match.group(1)
            return f':valid-at "{valid_at}"'
    return f':valid-at "{_now_utc_ms()}"'


def handle_memory_prepare_turn(user_message: str) -> str:
    """
    Query graph for facts relevant to the user message.
    Returns a formatted context block string for injection as additionalContext.

    Uses :any-valid-time for most queries so facts stored without an explicit
    valid-at are included. Historical queries with a detected ISO date use
    :valid-at to restrict to the point-in-time state.
    """
    db = get_db()
    scan_limit = int(os.environ.get("VULCAN_PREPARE_SCAN_LIMIT", "50"))
    temporal_clauses = _build_query_clauses(user_message)

    entities = _extract_entities(user_message)
    collected: List[List[str]] = []
    seen: set = set()

    for entity in entities:
        try:
            raw = db.execute(
                f'(query [:find ?a ?v {temporal_clauses} :where [?e ?a ?v] (contains? ?v "{entity}")])'
            )
            data = json.loads(raw)
            for row in data.get("results", []):
                key = tuple(row)
                if key not in seen:
                    seen.add(key)
                    collected.append(row)
        except (MiniGrafError, json.JSONDecodeError):
            continue

    if not collected:
        # Broad fallback scan — still respect temporal clause
        try:
            raw = db.execute(
                f"(query [:find ?e ?a ?v {temporal_clauses} :where [?e ?a ?v]])"
            )
            data = json.loads(raw)
            all_results = data.get("results", [])
            collected = all_results[:scan_limit]
        except (MiniGrafError, json.JSONDecodeError):
            pass

    if not collected:
        return ""

    block = _format_facts(collected)
    return f"Relevant memory context:\n{block}"


# ---------------------------------------------------------------------------
# Fact extraction — heuristic strategy
# ---------------------------------------------------------------------------

_SIGNAL_PATTERNS = [
    (r"we(?:'ll?|\s+will)\s+use\s+([\w\-]+)", "decision", ":description", "chosen technology or approach"),
    (r"going\s+with\s+([\w\-]+)", "decision", ":description", "chosen approach"),
    (r"decided\s+(?:to\s+)?(?:use\s+)?([\w\-]+)", "decision", ":description", "decided approach"),
    (r"we\s+chose\s+([\w\-]+)", "decision", ":description", "chosen option"),
    (r"I\s+prefer\s+([\w\-]+)", "preference", ":description", "stated preference"),
    (r"I\s+don'?t\s+like\s+([\w\-]+)", "preference", ":description", "stated dislike"),
    (r"always\s+use\s+([\w\-]+)", "preference", ":description", "always-use preference"),
    (r"never\s+use\s+([\w\-]+)", "preference", ":description", "never-use preference"),
    (r"prioritize\s+([\w\-]+)", "preference", ":description", "priority preference"),
    (r"must\s+be\s+([\w\-]+)", "constraint", ":description", "hard constraint"),
    (r"can'?t\s+use\s+([\w\-]+)", "constraint", ":description", "exclusion constraint"),
    (r"depends\s+on\s+([\w\-]+)", "dependency", ":description", "dependency relationship"),
    (r"requires?\s+([\w\-]+)", "dependency", ":description", "required dependency"),
]


def heuristic_extract(text: str) -> List[Dict[str, str]]:
    """
    Scan text for decision-signal phrases and return a list of fact dicts.
    Each dict has keys: entity, attribute, value, reason.
    """
    facts = []
    seen_values: set = set()

    for pattern, entity_type, attribute, reason_prefix in _SIGNAL_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1).strip()
            if len(value) < 2 or value.lower() in _STOP_WORDS:
                continue
            key = (entity_type, value.lower())
            if key in seen_values:
                continue
            seen_values.add(key)
            entity_ident = f":{entity_type}/{value.lower().replace('-', '_')}"
            facts.append({
                "entity": entity_ident,
                "entity_type": entity_type,
                "attribute": attribute,
                "value": value,
                "reason": f"{reason_prefix} — extracted by heuristic strategy",
            })

    return facts


def _transact_extracted_facts(facts: List[Dict[str, str]]) -> int:
    """
    Transact a list of extracted fact dicts. Returns count of successfully stored facts.

    Sets :valid-at to the current UTC ms timestamp on every write so that
    valid-time is recorded. Combined with :as-of in queries this enables true
    bi-temporal point-in-time reads.
    """
    db = get_db()
    stored = 0
    for fact in facts:
        entity = fact["entity"]
        entity_type = fact.get("entity_type", "")
        attribute = fact["attribute"]
        value = fact["value"]
        now_z = _now_utc_ms()
        try:
            # Map syntax verified working: (transact [[e attr "v"]] {:valid-at "ts"})
            db.execute(f'(transact [[{entity} {attribute} "{value}"]] {{:valid-at "{now_z}"}})')
            if entity_type:
                db.execute(
                    f'(transact [[{entity} :entity-type :type/{entity_type}]] {{:valid-at "{now_z}"}})'
                )
            stored += 1
        except MiniGrafError:
            continue
    if stored:
        db.checkpoint()
    return stored


# ---------------------------------------------------------------------------
# Fact extraction — llm strategy
# ---------------------------------------------------------------------------

_LLM_EXTRACTION_PROMPT = """You are a memory extraction assistant for a bi-temporal graph database. Review the conversation below and identify any decisions, preferences, constraints, or dependencies that should be stored in long-term memory.

Return ONLY a Datalog transact expression — a list of triples in this exact format:
[[:entity/ident :attribute "value"]
 [:entity/ident :attribute "value"]]

If nothing worth storing was found, return an empty list: []

Use these entity type prefixes: :decision/, :preference/, :constraint/, :dependency/
Use these attributes: :description, :reason, :rejected

IMPORTANT — bi-temporality: this database is bi-temporal. Facts have both a transaction time
(when they were recorded) and a valid time (when they were true in the world). When the conversation
mentions that something was decided or true at a specific past date, note that date alongside the
fact so the caller can set :valid-at accordingly. Wrap such facts in a comment line:
; valid-at: 2024-03-15
[[:entity/ident :attribute "value"]]

For point-in-time historical queries, always use :as-of N and :valid-at "date" TOGETHER —
using only one gives a partial view.

Conversation:
{conversation}"""


def _get_anthropic_client():
    """Return an Anthropic client. Raises if anthropic package or API key is missing."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed — pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def _parse_valid_at_hint(raw: str):
    """Extract optional '; valid-at: YYYY-MM-DD' comment from model output.

    Returns (valid_at, cleaned_datalog) where valid_at defaults to the current
    UTC ms timestamp if no hint is present.
    """
    valid_at = _now_utc_ms()
    kept = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("; valid-at:"):
            date_str = stripped[len("; valid-at:"):].strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                valid_at = date_str
        else:
            kept.append(line)
    return valid_at, "\n".join(kept).strip()


def _llm_extract_and_transact(conversation_delta: str) -> Dict[str, Any]:
    """Call a lightweight LLM to extract facts. Returns {ok, stored_count, strategy}."""
    try:
        client = _get_anthropic_client()
        model = os.environ.get("VULCAN_LLM_MODEL", "claude-haiku-4-5-20251001")
        prompt = _LLM_EXTRACTION_PROMPT.format(conversation=conversation_delta)
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_facts = message.content[0].text.strip()
        if not raw_facts or raw_facts == "[]":
            return {"ok": True, "stored_count": 0, "strategy": "llm"}
        valid_at, datalog = _parse_valid_at_hint(raw_facts)
        if not datalog or datalog == "[]":
            return {"ok": True, "stored_count": 0, "strategy": "llm"}
        db = get_db()
        db.execute(f'(transact {datalog} {{:valid-at "{valid_at}"}})')
        db.checkpoint()
        stored_count = datalog.count("[:")
        return {"ok": True, "stored_count": stored_count, "strategy": "llm"}
    except Exception as e:
        return {"ok": False, "error": str(e), "strategy": "llm"}


# ---------------------------------------------------------------------------
# Fact extraction — agent (MCP sampling) strategy
# ---------------------------------------------------------------------------

_AGENT_SAMPLING_PROMPT = """Review this conversation turn and output ONLY a Datalog transact expression for any decisions, preferences, constraints, or dependencies worth storing in long-term memory.

Format: [[:entity/ident :attribute "value"]]
If nothing is worth storing, output: []

IMPORTANT — bi-temporality: this database is bi-temporal. Facts have both a transaction time
(when recorded) and a valid time (when true in the world). If a fact was decided or true at a
specific past date, prefix it with a comment: ; valid-at: YYYY-MM-DD

For historical point-in-time queries, always use :as-of N AND :valid-at "date" together —
using only one gives a partial view, not a true bi-temporal snapshot.

Conversation:
{conversation}"""


async def _request_agent_memory_block_async(conversation_delta: str) -> str:
    """Use MCP sampling to ask the connected agent for a memory block."""
    if _server_ref is None:
        raise RuntimeError("Server reference not set")
    from mcp.types import SamplingMessage, TextContent as TC
    prompt = _AGENT_SAMPLING_PROMPT.format(conversation=conversation_delta)
    result = await _server_ref.request_context.session.create_message(
        messages=[SamplingMessage(role="user", content=TC(type="text", text=prompt))],
        max_tokens=512,
    )
    return result.content.text if hasattr(result.content, "text") else str(result.content)


async def _agent_extract_and_transact(conversation_delta: str) -> Dict[str, Any]:
    """Request a memory block from the agent via MCP sampling, then transact it."""
    try:
        raw_facts = await _request_agent_memory_block_async(conversation_delta)
        raw_facts = raw_facts.strip()
        if not raw_facts or raw_facts == "[]":
            return {"ok": True, "stored_count": 0, "strategy": "agent"}
        valid_at, datalog = _parse_valid_at_hint(raw_facts)
        if not datalog or datalog == "[]":
            return {"ok": True, "stored_count": 0, "strategy": "agent"}
        db = get_db()
        db.execute(f'(transact {datalog} {{:valid-at "{valid_at}"}})')
        db.checkpoint()
        stored_count = datalog.count("[:")
        return {"ok": True, "stored_count": stored_count, "strategy": "agent"}
    except Exception as e:
        return {"ok": False, "error": str(e), "strategy": "agent"}


# ---------------------------------------------------------------------------
# memory_finalize_turn — dispatcher
# ---------------------------------------------------------------------------

async def handle_memory_finalize_turn(conversation_delta: str) -> Dict[str, Any]:
    """
    Extract facts from conversation_delta and transact them.
    Strategy selected via VULCAN_EXTRACTION_STRATEGY env var (default: heuristic).
    """
    strategy = os.environ.get("VULCAN_EXTRACTION_STRATEGY", "heuristic")

    if strategy == "heuristic":
        facts = heuristic_extract(conversation_delta)
        stored = _transact_extracted_facts(facts)
        return {"ok": True, "stored_count": stored, "strategy": "heuristic"}

    if strategy == "llm":
        result = _llm_extract_and_transact(conversation_delta)
        if result["ok"]:
            return result
        return await _agent_extract_and_transact(conversation_delta)

    if strategy == "agent":
        return await _agent_extract_and_transact(conversation_delta)

    return {"ok": False, "error": f"Unknown strategy: {strategy}"}


# ---------------------------------------------------------------------------
# MCP server (tools wired in subsequent tasks)
# ---------------------------------------------------------------------------

server = Server("temporal-reasoning")


async def main() -> None:
    open_db()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
