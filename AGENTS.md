# AGENTS.md

## Codebase Exploration

Follow below instructions to quickly go through project:

1. **Discover landscape** — Go through `docs/centers/{CENTER_ID}/README.md`
   which semantic centers are relevant to the current task.
   
2. **DO NOT** traversal other file under the centers directory.

3. **Delegate per-center exploration** — For center-specific analysis,
   delegate to `quro-center-explorer` agent with `{stable_id, query}`.
   The agent follows the standard flow:
   check members_hash staleness → recall cached conclusions → explore
   if needed → return compressed findings + intents[3].

4. **Cross-center search** — Use `quro-doc` MCP tools when the task spans
   multiple centers or requires semantic search across boundaries.

You are NOT required to know any specific center's symbols upfront.
Let per-center agents discover code structure at runtime.

## HARD CONSTRAINTS

- **NEVER** go through codebase without delegate to agents.