"""
SessionStart hook - injects knowledge base context into every conversation.

This is the "context injection" layer. When Claude Code starts a session,
this hook reads the knowledge base index and recent daily log, then injects
them as additional context so Claude always "remembers" what it has learned.

Additionally, this hook injects identity files (SOUL.md, USER.md) from the
Obsidian vault to define how the agent should act.

Configure in .claude/settings.json:
{
    "hooks": {
        "SessionStart": [{
            "matcher": "",
            "command": "uv run python hooks/session-start.py"
        }]
    }
}
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Paths relative to project root
ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
DAILY_DIR = ROOT / "daily"
INDEX_FILE = KNOWLEDGE_DIR / "index.md"

# Obsidian vault paths (identity files)
VAULT_DIR = Path("/Users/josephfajen/git/obsidian-second-brain/memory")
SOUL_FILE = VAULT_DIR / "SOUL.md"
USER_FILE = VAULT_DIR / "USER.md"
BOOTSTRAP_FILE = VAULT_DIR / "BOOTSTRAP.md"

MAX_CONTEXT_CHARS = 20_000
MAX_LOG_LINES = 30


def read_file_safe(path: Path, max_chars: int = 5000) -> str:
    """Read a file safely, returning empty string if missing."""
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n...(truncated)"
        return content
    except Exception:
        return ""


def get_recent_log() -> str:
    """Read the most recent daily log (today or yesterday)."""
    today = datetime.now(timezone.utc).astimezone()

    for offset in range(2):
        date = today - timedelta(days=offset)
        log_path = DAILY_DIR / f"{date.strftime('%Y-%m-%d')}.md"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            # Return last N lines to keep context small
            recent = lines[-MAX_LOG_LINES:] if len(lines) > MAX_LOG_LINES else lines
            return "\n".join(recent)

    return "(no recent daily log)"


def build_context() -> str:
    """Assemble the context to inject into the conversation."""
    parts = []

    # 1. BOOTSTRAP.md (if exists) - highest priority for onboarding
    bootstrap_content = read_file_safe(BOOTSTRAP_FILE)
    if bootstrap_content:
        parts.append(f"## ONBOARDING ACTIVE\n\n{bootstrap_content}")

    # 2. SOUL.md - agent identity
    soul_content = read_file_safe(SOUL_FILE)
    if soul_content:
        parts.append(f"## Agent Identity\n\n{soul_content}")

    # 3. USER.md - user profile
    user_content = read_file_safe(USER_FILE)
    if user_content:
        parts.append(f"## User Profile\n\n{user_content}")

    # 4. Today's date
    today = datetime.now(timezone.utc).astimezone()
    parts.append(f"## Today\n{today.strftime('%A, %B %d, %Y')}")

    # 5. Knowledge base index (the core retrieval mechanism)
    if INDEX_FILE.exists():
        index_content = INDEX_FILE.read_text(encoding="utf-8")
        parts.append(f"## Knowledge Base Index\n\n{index_content}")
    else:
        parts.append("## Knowledge Base Index\n\n(empty - no articles compiled yet)")

    # 6. Recent daily log
    recent_log = get_recent_log()
    parts.append(f"## Recent Daily Log\n\n{recent_log}")

    context = "\n\n---\n\n".join(parts)

    # Truncate if too long
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n...(truncated)"

    return context


def main():
    context = build_context()

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
