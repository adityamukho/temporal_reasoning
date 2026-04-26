# MCP Server Design

**Date:** 2026-04-26
**Status:** Approved
**Scope:** Replace CLI-based graph access with a persistent MCP server using the minigraf Python binding; add automatic turn-by-turn memory injection and extraction for supported harnesses.

---

## Problem

Agents reliably forget to invoke the skill — both reads (missing relevant context) and writes (not recording decisions). Prompt tuning does not solve this because tool selection is probabilistic and the reward signal for task completion does not reinforce memory hygiene. The fix is to move the memory loop outside the agent's decision-making entirely.

---

## Context

### minigraf Python binding

`minigraf` 0.22.0+ is published to PyPI. The Python API surface:

```python
from minigraf import MiniGrafDb, MiniGrafError

db = MiniGrafDb.open("memory.graph")   # file-backed, persistent
db = MiniGrafDb.open_in_memory()       # ephemeral
result_json = db.execute(datalog_str)  # all operations: query, transact, retract, rules
db.checkpoint()                        # flush WAL to disk
```

`execute()` is the single entry point for all Datalog operations. Rules registered via `execute()` are cached in the process-level `RuleRegistry` and persist across subsequent calls on the same `MiniGrafDb` instance.

### Exclusive file access constraint

minigraf explicitly does not support concurrent open of the same `.graph` file by multiple processes ("not a goal for embedded-first" — Phase 5 WAL-ACID spec). The MCP server must be the only process holding the graph file open.

### Prepared statements

Available in the Rust core since Phase 7.8 but deferred from the Python FFI until post-1.0 ("stateful handle design TBD once basic FFI API is proven stable" — Phase 8.3 language bindings spec). The persistent `MiniGrafDb` instance in the MCP server provides session-level rule caching; prepared statements are a future enhancement.

### Harness hook support

| Harness | Pre-turn injection | Post-turn extraction | Mechanism |
|---|---|---|---|
| Claude Code | Yes | Yes | `UserPromptSubmit` / `Stop` hooks → `mcp_tool` |
| Codex CLI | Yes | Yes | `UserPromptSubmit` / `Stop` hooks → `mcp_tool` |
| Hermes | Yes | Yes | `pre_llm_call` / `post_llm_call` hooks → `mcp_tool` |
| OpenCode | No | No | Pre/post-turn hooks not yet implemented (feature requested); MCP tools available for explicit agent invocation |

---

## Architecture

`mcp_server.py` is the sole process that opens the `.graph` file, via `MiniGrafDb`. No other code path opens the file. `vulcan.py` is deleted.

The MCP server is a persistent stdio process. The harness spawns it at session open and tears it down at session close. All graph access — automatic (hooks) and explicit (agent tool calls) — routes through this single process and single `MiniGrafDb` instance.

```
[User message]
      │
      ▼
[Harness hook: UserPromptSubmit / pre_llm_call]
      └─→ memory_prepare_turn(user_message)
          → queries graph, returns relevant facts as additionalContext
      │
      ▼
[Agent sees: user message + injected memory context]
      │
      ▼
[Agent responds; may explicitly call vulcan_query / vulcan_transact / vulcan_retract]
      │
      ▼
[Harness hook: Stop / post_llm_call]
      └─→ memory_finalize_turn(conversation_delta)
          → extracts facts via configured strategy, transacts into graph
```

For OpenCode (degraded mode), the top and bottom hooks are absent. The agent calls memory tools explicitly as today.

---

## Components

### Deleted

| File | Reason |
|---|---|
| `vulcan.py` | Replaced by `mcp_server.py`; exclusive file access requires one owner |
| Binary download logic in `install.py` | `pip install minigraf` replaces pre-built binary download |

Deleted functions from `install.py`: `_get_platform_asset`, `_get_latest_version`, `_download_binary`, `_verify_checksum`, `_install_binary`, `_install_via_cargo`, `ensure_minigraf`.

### Added

| File | Purpose |
|---|---|
| `mcp_server.py` | MCP server — sole graph interface |
| `hooks/claude-code.json` | Hook + MCP server config template for Claude Code |
| `hooks/codex.toml` | Hook + MCP server config template for Codex CLI |
| `hooks/hermes.yaml` | Hook + MCP server config template for Hermes |
| `hooks/opencode.json` | MCP server config template for OpenCode (no hooks) |

### Modified

| File | Change summary |
|---|---|
| `install.py` | Binary download replaced with `pip install minigraf`; syncs `mcp_server.py` and `hooks/`; post-install output updated |
| `SKILL.md` | Tool invocation examples updated; Dependencies section updated; Files table updated; Harness setup section added |
| `tools/*.json` | Tool schemas updated to match MCP server tools |
| `ROADMAP.md` | New phase added |

### Retained unchanged

| File | Reason |
|---|---|
| `report_issue.py` | Does not access the graph; no changes needed |
| `tools/report_issue.json` | Unchanged |

---

## MCP Server Internals

### Startup sequence

1. Resolve graph path: `MINIGRAF_GRAPH_PATH` env var, else `{cwd}/memory.graph`
2. Open `MiniGrafDb` at that path (file created if absent)
3. Register session-scoped rules via `execute()`:
   ```
   (rule [(linked ?a ?b) [?a :depends-on ?b]])
   (rule [(linked ?a ?b) [?a :calls ?b]])
   (rule [(reachable ?a ?b) [?a :depends-on ?b]])
   (rule [(reachable ?a ?b) [?a :calls ?b]])
   ```
   These persist in the `RuleRegistry` for the session without re-registration on each query.
4. Start MCP stdio listener

### Tools

#### Hook-invoked (automatic)

**`memory_prepare_turn(user_message: str) → str`**

Called by the harness before passing the user message to the agent.

1. Extract entity mentions and keywords from `user_message` (simple substring/noun-phrase heuristic)
2. For each extracted entity, run: `[:find ?a ?v :where [?e ?a ?v] (contains? ?v "<entity>")]`
3. Deduplicate results across entities
4. If no targeted results, fall back to a capped broad scan of the most recent N facts (N configurable via `VULCAN_PREPARE_SCAN_LIMIT`, default 50)
5. Format results as a human-readable context block
6. Return the block as a string; the harness injects it as `additionalContext` before the model call

**`memory_finalize_turn(conversation_delta: str) → {ok: bool, stored_count: int}`**

Called by the harness after the agent completes its turn.

`conversation_delta`: full turn exchange — user message, agent response, any tool calls and their results.

Runs the configured extraction strategy (see below) and transacts resulting facts into the graph.

#### Agent-invoked (explicit)

**`vulcan_query(datalog: str) → {ok: bool, results: list}`**

Thin wrapper over `db.execute()`. Parses and returns results in the same structure as the former `vulcan.py` `query()` function.

**`vulcan_transact(facts: str, reason: str) → {ok: bool, tx: str}`**

Thin wrapper over `db.execute()`. `reason` required; enforced server-side.

**`vulcan_retract(facts: str, reason: str) → {ok: bool, tx: str}`**

Thin wrapper over `db.execute()`. `reason` required.

**`vulcan_report_issue(category: str, description: str, datalog: str?, error: str?) → {ok: bool}`**

Delegates to `report_issue.py`. Unchanged behaviour.

---

## Fact Extraction Strategies

Configured via `VULCAN_EXTRACTION_STRATEGY` env var. Default: `heuristic`.

### `heuristic`

Pattern matching on decision-signal phrases:

> "we'll use", "going with", "decided", "we chose", "I prefer", "I don't like", "always use", "never use", "must be", "can't use", "prioritize", "depends on", "requires", "calls into"

For each match, surrounding context (±2 sentences) is extracted and converted to Datalog facts using a template mapping signal type → attribute set. No external API calls; always available.

### `llm`

Calls a lightweight model to extract facts from the conversation delta.

- Model: `VULCAN_LLM_MODEL` env var, default `claude-haiku-4-5-20251001`
- API key: `ANTHROPIC_API_KEY` (or model-appropriate key)
- Prompt: structured extraction prompt asking for decisions/preferences/constraints/dependencies present in the delta, returned as ready-to-transact Datalog facts with reasons
- On API call failure or missing key: automatically falls back to `agent`

### `agent`

Uses the MCP sampling protocol to request a structured memory block from the connected agent. The MCP server sends a sampling request; the agent outputs Datalog facts summarising what was decided in the turn; the server transacts them.

Natural fallback for `llm` when running local LLMs that support MCP sampling but have no separate lightweight model endpoint.

### Strategy selection

```
VULCAN_EXTRACTION_STRATEGY=llm       → try llm; on failure → agent
VULCAN_EXTRACTION_STRATEGY=heuristic → heuristic only
VULCAN_EXTRACTION_STRATEGY=agent     → agent (MCP sampling) only
```

---

## Hook Configuration Templates

**Important:** Argument passing from hook event context to MCP tool parameters (how `user_message` is sourced, how `conversation_delta` is assembled) is harness-specific and must be verified against each harness's hook documentation during implementation. The templates below capture intent and approximate structure.

The graph path is resolved from the harness's working directory. Either launch the harness from the project root, or set `MINIGRAF_GRAPH_PATH` explicitly in the `env` block.

### Claude Code (`.claude/settings.json`)

```json
{
  "mcpServers": {
    "temporal-reasoning": {
      "command": "python",
      "args": ["${TEMPORAL_REASONING_PATH}/mcp_server.py"],
      "env": {
        "VULCAN_EXTRACTION_STRATEGY": "heuristic"
      }
    }
  },
  "hooks": {
    "UserPromptSubmit": [{
      "type": "mcp_tool",
      "mcp_server": "temporal-reasoning",
      "tool_name": "memory_prepare_turn"
    }],
    "Stop": [{
      "type": "mcp_tool",
      "mcp_server": "temporal-reasoning",
      "tool_name": "memory_finalize_turn"
    }]
  }
}
```

### Codex CLI (`config.toml`)

```toml
[mcp_servers.temporal-reasoning]
command = "python"
args = ["${TEMPORAL_REASONING_PATH}/mcp_server.py"]

[mcp_servers.temporal-reasoning.env]
VULCAN_EXTRACTION_STRATEGY = "heuristic"

[[hooks.UserPromptSubmit]]
type = "mcp_tool"
server = "temporal-reasoning"
tool = "memory_prepare_turn"

[[hooks.Stop]]
type = "mcp_tool"
server = "temporal-reasoning"
tool = "memory_finalize_turn"
```

### Hermes (`config.yaml`)

```yaml
mcp_servers:
  - name: temporal-reasoning
    command: python
    args:
      - "${TEMPORAL_REASONING_PATH}/mcp_server.py"
    env:
      VULCAN_EXTRACTION_STRATEGY: heuristic

hooks:
  pre_llm_call:
    - type: mcp_tool
      server: temporal-reasoning
      tool: memory_prepare_turn
  post_llm_call:
    - type: mcp_tool
      server: temporal-reasoning
      tool: memory_finalize_turn
```

### OpenCode (`opencode.json`, degraded mode)

No pre/post-turn hooks. Agent calls memory tools explicitly.

```json
{
  "mcp": {
    "temporal-reasoning": {
      "command": "python",
      "args": ["${TEMPORAL_REASONING_PATH}/mcp_server.py"],
      "env": {
        "VULCAN_EXTRACTION_STRATEGY": "heuristic"
      }
    }
  }
}
```

---

## install.py Changes

**New dependency check** (replaces `ensure_minigraf`):

```python
def check_minigraf_package():
    """Verify minigraf Python package is installed, installing if absent."""
    try:
        import minigraf
        print("✓ minigraf Python package found")
        return True
    except ImportError:
        print("✗ minigraf not found — installing via pip...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "minigraf"],
            timeout=120,
        )
        return result.returncode == 0
```

**Updated sync lists:**
```python
FILES_TO_SYNC = ["SKILL.md", "mcp_server.py", "skill.json"]
DIRS_TO_SYNC = ["tools", "hooks"]
```

**Updated checks in `main()`:**
```python
checks = [
    ("Python version", check_python_version),
    ("minigraf package", check_minigraf_package),
    ("MCP server", check_mcp_server_importable),
]
```

Post-install output updated to show harness config instructions and point to `hooks/` templates.

---

## SKILL.md Changes

- **Frontmatter / trigger / core habits:** unchanged
- **Tool invocation examples:** `from vulcan import ...` imports removed; examples rewritten in tool-call format (tool name + parameters, no Python import syntax)
- **Dependencies section:** `minigraf >= 0.19.0 — run install.py to download binary` → `minigraf Python package — run install.py to install via pip. Requires Python 3.9+.`
- **New section — Harness setup:** brief guide pointing to `hooks/` templates; notes OpenCode degraded mode
- **Files table:** updated to reflect new and removed files (see Components above)
- **Error responses:** binary-related errors removed; `minigraf package not installed — run install.py` added

---

## Roadmap Update

Mark the existing CLI-based approach (Phases 1–2) as complete. Add:

**Phase 3 — MCP Server + Automatic Turn-by-Turn Memory (this spec)**
- `mcp_server.py` with `MiniGrafDb` (Python binding)
- `memory_prepare_turn` / `memory_finalize_turn` automatic hooks
- Three extraction strategies: `heuristic`, `llm`, `agent`
- Hook config templates: Claude Code, Codex CLI, Hermes, OpenCode (degraded)
- `vulcan.py` deleted; `install.py` updated to `pip install minigraf`

**Future Phase 4 — Prepared Statements**
Expose `prepare()` / `PreparedQuery` in the Python FFI (pending minigraf post-1.0 FFI work). The MCP server gains prepared statements for `memory_prepare_turn`'s standard query patterns with no interface changes.

**Future Phase 5 — Rust MCP Server**
If query volume scales to the point where `execute()` parse+plan latency becomes significant, rewrite `mcp_server.py` as a Rust binary linking minigraf directly. Distributed as a pre-built binary using the same platform matrix as minigraf. Python binding dependency eliminated.

---

## Out of Scope

- Cline / Continue harness support (MCP supported; pre/post-turn hook capability unverified)
- Cursor harness support (closed source; limited hook surface)
- Aider harness support (no MCP support)
- OpenCode automatic injection (upstream feature not yet implemented)
- Prepared statements in Python FFI (post-1.0 minigraf work)
- Multi-agent / shared graph access (minigraf exclusive-open constraint; out of scope for this phase)
- Windows PATH mutation from within `install.py`
