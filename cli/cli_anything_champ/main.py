"""
main.py — CHAMP Graph CLI (cli-anything-champ)

Converts the CHAMP Graph REST API into an agent-ready command-line interface
following the CLI-Anything pattern:
  - Click-based subcommands for scriptable automation
  - Interactive REPL for exploratory sessions
  - --json flag for machine-readable output
  - Session context (server URL + API key) stored in ~/.cli-anything-champ/config

Entry point: cli-anything-champ
"""
import asyncio
import json
import os
import sys
import textwrap
from typing import Any, Dict, Optional

import click

from .repl_skin import (
    create_session,
    get_input,
    print_banner,
    print_error,
    print_header,
    print_info,
    print_success,
    print_table,
    print_warning,
    BOLD,
    CYAN,
    DIM,
    RESET,
    _c,
)

# ---------------------------------------------------------------------------
# Lazy import of the SDK client so the CLI works even if httpx is available
# but the server isn't running.
# ---------------------------------------------------------------------------
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from sdk.graffiti_client import GraffitiClient, GraffitiClientError
except ImportError as e:
    click.echo(f"Error: cannot import CHAMP Graph SDK — {e}", err=True)
    sys.exit(1)

CONFIG_DIR = os.path.expanduser("~/.cli-anything-champ")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_URL = "http://localhost:8080"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, str]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(cfg: Dict[str, str]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def _get_server(ctx_obj: Dict) -> str:
    return (
        ctx_obj.get("server")
        or os.environ.get("CHAMP_GRAPH_URL")
        or _load_config().get("server")
        or DEFAULT_URL
    )


def _get_api_key(ctx_obj: Dict) -> Optional[str]:
    return (
        ctx_obj.get("api_key")
        or os.environ.get("CHAMP_GRAPH_API_KEY")
        or _load_config().get("api_key")
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _out(data: Any, as_json: bool) -> None:
    """Print data either as pretty JSON or human-readable."""
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        _pretty(data)


def _pretty(data: Any, indent: int = 0) -> None:
    """Human-readable recursive print."""
    pad = "  " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                click.echo(f"{pad}{_c(BOLD, str(k))}:")
                _pretty(v, indent + 1)
            else:
                click.echo(f"{pad}{_c(CYAN, str(k))}: {v}")
    elif isinstance(data, list):
        if not data:
            click.echo(f"{pad}{_c(DIM, '(empty)')}")
        for i, item in enumerate(data):
            click.echo(f"{pad}{_c(DIM, f'[{i}]')}")
            _pretty(item, indent + 1)
    else:
        click.echo(f"{pad}{data}")


# ---------------------------------------------------------------------------
# Async runner
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


async def _call(server: str, api_key: Optional[str], method: str, **kwargs) -> Any:
    """Connect to CHAMP Graph and call a SDK method."""
    async with GraffitiClient(server, api_key=api_key) as client:
        fn = getattr(client, method)
        return await fn(**kwargs)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--server", "-s", default=None, help="CHAMP Graph server URL")
@click.option("--api-key", "-k", default=None, help="X-API-Key for authentication")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.pass_context
def cli(ctx: click.Context, server: Optional[str], api_key: Optional[str], as_json: bool):
    """
    cli-anything-champ — CHAMP Graph knowledge graph CLI

    Run without a subcommand to enter interactive REPL mode.

    \b
    Environment variables (override config file):
      CHAMP_GRAPH_URL      Server URL  (default: http://localhost:8080)
      CHAMP_GRAPH_API_KEY  API key

    \b
    Examples:
      champ health
      champ recall "Acme Corp" "What pricing was discussed?"
      champ briefing "Acme Corp"
      champ ingest email --account "Acme Corp" --from rep@co.com --to j@acme.com \\
            --subject "Follow-up" --body "Hi John..."
      champ                          # interactive REPL
    """
    ctx.ensure_object(dict)
    ctx.obj["server"] = server
    ctx.obj["api_key"] = api_key
    ctx.obj["as_json"] = as_json

    if ctx.invoked_subcommand is None:
        # Enter REPL
        _repl(ctx)


# ---------------------------------------------------------------------------
# config command group
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def config(ctx: click.Context):
    """Manage CLI configuration (server URL, API key)."""
    pass


@config.command("set")
@click.argument("key", metavar="KEY")
@click.argument("value", metavar="VALUE")
def config_set(key: str, value: str):
    """Set a config value (server | api_key).

    \b
    Examples:
      champ config set server http://localhost:8080
      champ config set api_key my-secret-key
    """
    valid = {"server", "api_key"}
    if key not in valid:
        print_error(f"Unknown key '{key}'. Valid keys: {', '.join(valid)}")
        sys.exit(1)
    cfg = _load_config()
    cfg[key] = value
    _save_config(cfg)
    print_success(f"Set {key} = {value}")


@config.command("show")
def config_show():
    """Show current config."""
    cfg = _load_config()
    if not cfg:
        print_info(f"No config file at {CONFIG_FILE}")
        return
    print_header("CHAMP Graph CLI Config")
    for k, v in cfg.items():
        masked = v if k != "api_key" else v[:4] + "****"
        click.echo(f"  {_c(CYAN, k)}: {masked}")


@config.command("clear")
def config_clear():
    """Clear saved config."""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
        print_success("Config cleared.")
    else:
        print_info("No config file to clear.")


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def health(ctx: click.Context):
    """Check server health."""
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "health_check"))
        if as_json:
            _out(result, True)
        else:
            status = result.get("status", "unknown")
            if status == "healthy":
                print_success(f"Server is healthy ({server})")
            else:
                print_warning(f"Server status: {status}")
            _pretty(result)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# recall
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("account")
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Max results (default 10)")
@click.pass_context
def recall(ctx: click.Context, account: str, query: str, limit: int):
    """Natural language search of the knowledge graph.

    \b
    Examples:
      champ recall "Acme Corp" "Who are the decision makers?"
      champ recall "Acme Corp" "pricing discussions" --limit 5
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "recall",
                            account_name=account, query=query, num_results=limit))
        _out(result, as_json)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# briefing
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("account")
@click.pass_context
def briefing(ctx: click.Context, account: str):
    """Get pre-call / pre-email account briefing.

    \b
    Example:
      champ briefing "Acme Corp"
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "get_briefing", account_name=account))
        _out(result, as_json)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# email-context
# ---------------------------------------------------------------------------

@cli.command("email-context")
@click.argument("account")
@click.option("--contact-email", default=None, help="Contact email address")
@click.option("--contact-name", default=None, help="Contact name")
@click.option("--subject", default=None, help="Email subject / topic for focused context")
@click.pass_context
def email_context(ctx: click.Context, account: str, contact_email: Optional[str],
                  contact_name: Optional[str], subject: Optional[str]):
    """Get context for composing an email.

    \b
    Example:
      champ email-context "Acme Corp" --contact-name "John Smith" --subject "pricing"
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "get_email_context",
                            account_name=account,
                            contact_email=contact_email,
                            contact_name=contact_name,
                            subject=subject))
        _out(result, as_json)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# contacts
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("account")
@click.pass_context
def contacts(ctx: click.Context, account: str):
    """List all contacts for an account.

    \b
    Example:
      champ contacts "Acme Corp"
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "get_contacts", account_name=account))
        if as_json:
            _out(result, True)
        else:
            print_header(f"Contacts — {account}")
            items = result.get("contacts", result.get("results", []))
            if not items:
                print_info("No contacts found.")
            else:
                rows = []
                for c in items:
                    rows.append([
                        c.get("name", ""),
                        c.get("email", ""),
                        c.get("title", ""),
                        c.get("department", ""),
                    ])
                print_table(["Name", "Email", "Title", "Department"], rows)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("account")
@click.option("--limit", "-n", default=20, help="Max interactions (default 20)")
@click.pass_context
def timeline(ctx: click.Context, account: str, limit: int):
    """Show cross-channel interaction timeline.

    \b
    Example:
      champ timeline "Acme Corp" --limit 30
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "get_timeline",
                            account_name=account, limit=limit))
        _out(result, as_json)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# stakeholders
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("account")
@click.pass_context
def stakeholders(ctx: click.Context, account: str):
    """Get stakeholder map (champions, blockers, decision-makers).

    \b
    Example:
      champ stakeholders "Acme Corp"
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "get_stakeholders", account_name=account))
        _out(result, as_json)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# gaps (stale contacts)
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("account")
@click.option("--days", "-d", default=30, help="Inactivity threshold in days (default 30)")
@click.pass_context
def gaps(ctx: click.Context, account: str, days: int):
    """Find contacts with no recent engagement.

    \b
    Example:
      champ gaps "Acme Corp" --days 14
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "find_stale_contacts",
                            account_name=account, days=days))
        _out(result, as_json)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# remember
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("account")
@click.argument("content")
@click.option("--source", default="cli", help="Source label (default: cli)")
@click.option("--name", default="CLI note", help="Episode name")
@click.pass_context
def remember(ctx: click.Context, account: str, content: str, source: str, name: str):
    """Store free-form information in the knowledge graph.

    \b
    Example:
      champ remember "Acme Corp" "John is the CFO and golfer — mention Augusta"
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)
    try:
        result = _run(_call(server, api_key, "remember",
                            account_name=account,
                            content=content,
                            source=source,
                            name=name))
        if as_json:
            _out(result, True)
        else:
            print_success("Stored in knowledge graph.")
            _pretty(result)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# ingest command group
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def ingest(ctx: click.Context):
    """Ingest data into the knowledge graph."""
    pass


@ingest.command("email")
@click.option("--account", "-a", required=True, help="Account / company name")
@click.option("--from", "from_address", required=True, help="Sender email")
@click.option("--to", "to_address", required=True, help="Recipient email")
@click.option("--subject", required=True, help="Email subject")
@click.option("--body", default=None, help="Email body (or use --body-file)")
@click.option("--body-file", default=None, type=click.Path(exists=True),
              help="Read body from file")
@click.option("--direction", default="outbound",
              type=click.Choice(["outbound", "inbound"]),
              help="Email direction (default: outbound)")
@click.pass_context
def ingest_email(ctx: click.Context, account: str, from_address: str, to_address: str,
                 subject: str, body: Optional[str], body_file: Optional[str],
                 direction: str):
    """Log a single email interaction.

    \b
    Examples:
      champ ingest email --account "Acme Corp" \\
            --from rep@ourco.com --to john@acme.com \\
            --subject "Follow-up on pricing" --body "Hi John..."

      champ ingest email --account "Acme Corp" \\
            --from rep@ourco.com --to john@acme.com \\
            --subject "Long email" --body-file email.txt
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)

    if body_file:
        with open(body_file) as f:
            body = f.read()
    if not body:
        print_error("Provide --body or --body-file.")
        sys.exit(1)

    try:
        result = _run(_call(server, api_key, "log_email",
                            account_name=account,
                            from_address=from_address,
                            to_address=to_address,
                            subject=subject,
                            body=body,
                            direction=direction))
        if as_json:
            _out(result, True)
        else:
            print_success(f"Email logged for {account}.")
            _pretty(result)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


@ingest.command("call")
@click.option("--account", "-a", required=True, help="Account / company name")
@click.option("--contact", required=True, help="Contact name")
@click.option("--summary", required=True, help="Call summary")
@click.option("--duration", default=0, type=int, help="Duration in minutes")
@click.option("--direction", default="outbound",
              type=click.Choice(["outbound", "inbound"]))
@click.option("--transcript", default="", help="Full transcript text")
@click.option("--transcript-file", default=None, type=click.Path(exists=True),
              help="Read transcript from file")
@click.pass_context
def ingest_call(ctx: click.Context, account: str, contact: str, summary: str,
                duration: int, direction: str, transcript: str,
                transcript_file: Optional[str]):
    """Log a call interaction.

    \b
    Example:
      champ ingest call --account "Acme Corp" --contact "John Smith" \\
            --summary "Discussed Q2 timeline and pricing" --duration 30
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)

    if transcript_file:
        with open(transcript_file) as f:
            transcript = f.read()

    try:
        result = _run(_call(server, api_key, "log_call",
                            account_name=account,
                            contact_name=contact,
                            summary=summary,
                            duration_minutes=duration,
                            direction=direction,
                            transcript=transcript))
        if as_json:
            _out(result, True)
        else:
            print_success(f"Call logged for {account}.")
            _pretty(result)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


@ingest.command("batch")
@click.argument("json_file", type=click.Path(exists=True))
@click.option("--account", "-a", required=True, help="Account / company name")
@click.pass_context
def ingest_batch(ctx: click.Context, json_file: str, account: str):
    """Batch-ingest emails from a JSON file.

    The JSON file must be an array of email objects, each with:
    from_address, to_address, subject, body, direction (optional).

    \b
    Example:
      champ ingest batch emails.json --account "Acme Corp"
    """
    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    as_json = ctx.obj.get("as_json", False)

    with open(json_file) as f:
        emails = json.load(f)

    if not isinstance(emails, list):
        print_error("JSON file must be an array of email objects.")
        sys.exit(1)

    try:
        result = _run(_call(server, api_key, "log_email_batch",
                            account_name=account, emails=emails))
        if as_json:
            _out(result, True)
        else:
            print_success(f"Batch ingested {len(emails)} emails for {account}.")
            _pretty(result)
    except GraffitiClientError as e:
        print_error(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

_REPL_HELP = """
Available commands:
  health                                Check server health
  recall <account> <query>              Search the knowledge graph
  briefing <account>                    Pre-call/email briefing
  email-context <account>               Email composition context
  contacts <account>                    List contacts
  timeline <account> [--limit N]        Interaction timeline
  stakeholders <account>                Stakeholder map
  gaps <account> [--days N]             Stale contacts
  remember <account> <content>          Store free-form info
  ingest email ...                      Log an email (see subcommand flags)
  ingest call ...                       Log a call (see subcommand flags)
  config show                           Show CLI config
  config set <key> <value>              Set server / api_key
  help                                  This help message
  exit | quit | Ctrl-D                  Exit REPL
"""


def _repl(ctx: click.Context) -> None:
    """Enter interactive REPL mode."""
    print_banner()

    server = _get_server(ctx.obj)
    api_key = _get_api_key(ctx.obj)
    print_info(f"Connected to: {server}")

    session = create_session()

    while True:
        try:
            prompt = _c("\033[38;5;80m\033[1m", "champ") + _c("\033[36m", " › ") + RESET
            line = get_input(session, prompt).strip()
        except (KeyboardInterrupt, EOFError):
            click.echo()
            print_info("Goodbye.")
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit", "q"):
            print_info("Goodbye.")
            break
        if line.lower() in ("help", "?"):
            click.echo(_REPL_HELP)
            continue

        # Parse and dispatch via Click's standalone_mode=False
        parts = line.split()
        try:
            result = cli.main(
                args=parts,
                standalone_mode=False,
                obj=ctx.obj,
            )
            # result may be None for commands that print directly
        except SystemExit:
            pass
        except click.UsageError as e:
            print_error(str(e))
        except click.exceptions.Abort:
            pass
        except Exception as e:
            print_error(f"Unexpected error: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
