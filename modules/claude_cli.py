"""
Claude via the local Claude Code CLI — uses the subscription already paid for.

Why: the pay-as-you-go Anthropic API key ran out of credits mid-run, which broke
script generation across every channel. The Claude Code CLI on this machine
authenticates with the existing subscription instead of API credits, so routing
through it removes the per-call billing entirely.

The prompt goes in on STDIN (not argv) — Windows caps a command line around 32K
characters and these prompts carry the full live-headline block, so argv would
truncate or fail outright.

Usage:
    from modules.claude_cli import claude_cli_complete
    text = await claude_cli_complete(prompt)      # None if unavailable
"""
import asyncio
import os
import shutil
import sys

# Resolve once. On Windows npm installs a .cmd shim; shutil.which finds it via
# PATHEXT, but check explicitly so a missing PATHEXT doesn't silently disable it.
def _find_claude() -> str | None:
    override = os.getenv("CLAUDE_CLI_PATH", "").strip()
    if override:
        return override if os.path.exists(override) else None
    for name in ("claude", "claude.cmd", "claude.CMD", "claude.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


CLAUDE_BIN = _find_claude()

# Master switch — on by default when the CLI exists. Set USE_CLAUDE_CLI=false to
# fall straight back to the API key.
def cli_enabled() -> bool:
    if os.getenv("USE_CLAUDE_CLI", "true").lower() in ("false", "0", "no"):
        return False
    return bool(CLAUDE_BIN)


async def claude_cli_complete(
    prompt: str,
    timeout: int = 180,
    model: str | None = None,
) -> str | None:
    """
    Run one non-interactive Claude turn and return its text.

    Returns None on any failure (missing CLI, timeout, non-zero exit, empty
    output) so callers fall through to their existing API/Gemini chain.
    """
    if not cli_enabled():
        return None

    args = [CLAUDE_BIN, "-p", "--output-format", "text"]
    if model:
        args += ["--model", model]

    # CRITICAL: strip the API-key vars. If ANTHROPIC_API_KEY is present the CLI
    # uses it INSTEAD of the subscription login — and since that key is what ran
    # out of credits, inheriting it defeats the whole point and fails with
    # "credit balance is too low".
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                        "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
                        "CLAUDE_CODE_USE_VERTEX")}

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            # Don't inherit a workspace cwd — this is a pure text call, and running
            # it inside the repo makes the CLI load project context it doesn't need.
            cwd=os.path.expanduser("~"),
        )
    except Exception as e:
        print(f"[ClaudeCLI] could not start: {e}")
        return None

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(prompt.encode("utf-8", errors="replace")),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        print(f"[ClaudeCLI] timed out after {timeout}s")
        return None

    if proc.returncode != 0:
        err = (stderr or b"").decode("utf-8", errors="replace")[:200]
        print(f"[ClaudeCLI] exit {proc.returncode}: {err}")
        return None

    text = (stdout or b"").decode("utf-8", errors="replace").strip()
    if not text:
        print("[ClaudeCLI] empty response")
        return None
    return text


if __name__ == "__main__":
    async def _test():
        print("binary:", CLAUDE_BIN, "| enabled:", cli_enabled())
        out = await claude_cli_complete('Reply with exactly: {"ok": true}')
        print("response:", out)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_test())
