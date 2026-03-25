---
name: cli-anything-champ
description: CLI harness for CHAMP Graph — Centralized High-context Agent Memory Platform
version: 1.0.0
entry_point: champ
install_cmd: pip install -e cli/
homepage: https://github.com/HKUDS/CLI-Anything
category: knowledge-graph
---

# CHAMP Graph CLI Skill

CLI-Anything harness for CHAMP Graph. Exposes the full CHAMP Graph REST API as
an agent-ready command-line interface with JSON output, REPL, and session management.

## Installation

```bash
# From the CHAMP Graph project root
pip install -e cli/

# Verify
champ --help
```

## Quick Start

```bash
# Check server health
champ health

# Search the knowledge graph
champ recall "Acme Corp" "Who are the decision makers?"

# Get pre-call briefing
champ briefing "Acme Corp"

# Enter interactive REPL
champ
```

## Configuration

```bash
# Save server URL and API key (persists across sessions)
champ config set server http://localhost:8080
champ config set api_key your-secret-key

# Or use environment variables (override config)
export CHAMP_GRAPH_URL=http://localhost:8080
export CHAMP_GRAPH_API_KEY=your-secret-key

# Show current config
champ config show
```

## Command Reference

| Command | Description |
|---------|-------------|
| `champ health` | Check server health |
| `champ recall <account> <query>` | Natural language search |
| `champ briefing <account>` | Pre-call/email briefing |
| `champ email-context <account>` | Email composition context |
| `champ contacts <account>` | List all contacts |
| `champ timeline <account>` | Interaction timeline |
| `champ stakeholders <account>` | Stakeholder map (champions, blockers) |
| `champ gaps <account>` | Find stale contacts |
| `champ remember <account> <content>` | Store free-form info |
| `champ ingest email` | Log a single email |
| `champ ingest call` | Log a call |
| `champ ingest batch <file.json>` | Batch-ingest emails from JSON |
| `champ config set <key> <value>` | Save server/api_key |
| `champ config show` | Show current config |

## JSON Output (for agents)

Every command supports `--json` for machine-readable output:

```bash
champ --json recall "Acme Corp" "pricing" | jq '.results'
champ --json contacts "Acme Corp" | jq '.contacts[].name'
champ --json briefing "Acme Corp"
```

## Ingest Examples

```bash
# Log an email
champ ingest email \
  --account "Acme Corp" \
  --from rep@ourco.com \
  --to john@acme.com \
  --subject "Q2 Follow-up" \
  --body "Hi John, wanted to circle back on pricing..."

# Log an email with body from file
champ ingest email --account "Acme Corp" \
  --from rep@ourco.com --to john@acme.com \
  --subject "Long proposal" --body-file proposal.txt

# Log a call
champ ingest call \
  --account "Acme Corp" \
  --contact "John Smith" \
  --summary "Discussed Q2 timeline and 3-year contract terms" \
  --duration 45

# Batch ingest from JSON array
champ ingest batch emails.json --account "Acme Corp"

# Store free-form notes
champ remember "Acme Corp" "John mentioned Augusta — he's a golfer"
```

## Query Examples

```bash
# Natural language search
champ recall "Acme Corp" "What pricing was discussed?"
champ recall "Acme Corp" "Any blockers mentioned?" --limit 5

# Email composition context
champ email-context "Acme Corp" \
  --contact-name "John Smith" \
  --subject "contract renewal"

# Stale contacts (not engaged in 2 weeks)
champ gaps "Acme Corp" --days 14

# Recent timeline
champ timeline "Acme Corp" --limit 10
```

## AI Agent Guidance

1. **Use `--json` flag** for structured, machine-readable output:
   ```bash
   champ --json recall "Acme Corp" "decision maker" | jq '.results[0].fact'
   ```

2. **Check exit codes** — 0 = success, non-zero = failure.

3. **Parse stderr for errors** — error messages go to stderr, data to stdout.

4. **Use `champ health` before any session** to confirm server connectivity.

5. **Quote account names** containing spaces: `champ briefing "Acme Corp"`.

6. **Batch over single** for bulk operations — use `champ ingest batch` instead
   of looping `champ ingest email`.

## REPL Mode

Run `champ` with no subcommand to enter an interactive REPL:

```
champ › recall "Acme Corp" "pricing"
champ › briefing "TechStart Inc"
champ › ingest email --account "Acme" --from a@b.com --to c@d.com --subject "Hi" --body "Hello"
champ › exit
```

The REPL supports command history (`~/.cli-anything-champ/history`) and
auto-suggestion when `prompt-toolkit` is installed.
