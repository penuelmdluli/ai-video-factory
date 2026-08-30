"""
One gate in front of every RunPod submission.

Owner call 2026-08-30: the RunPod credit about to be loaded is dedicated to the
85K personal profile — the dancing-video motion-transfer work — and nothing
else in this system may spend against it.

Setting workersMax to 0 on every endpoint (done the same day) stops GPUs
starting, but it does NOT stop a job being ACCEPTED. Submitted jobs sit in the
endpoint queue, and the moment workers are enabled to run the profile pipeline,
a backlog of whatever else was queued fires first and spends the credit before
anything dancing-related renders. That failure would arrive as an empty balance
with no obvious cause, which is the expensive way to find out.

So submission itself is gated here. The default is CLOSED: any caller that has
not declared a purpose is refused with a message naming what to do about it.

To run the profile pipeline:

    set RUNPOD_PURPOSE=dance          (PowerShell:  $env:RUNPOD_PURPOSE="dance")

or, in code, at the top of the entry point:

    from modules.runpod_guard import allow
    allow("dance")

Everything else — LTX shots, Wan i2v, MuseTalk, Chatterbox, the assembler,
Whisper captions, MusicGen — is refused until the owner widens ALLOWED or
clears the flag deliberately. This is a spend gate, not a security boundary:
it is meant to stop an automated pipeline running up a bill unattended, and it
says plainly how to lift it.
"""
import os

# The only purpose permitted to spend RunPod credit right now.
ALLOWED = {"dance"}

ENV_VAR = "RUNPOD_PURPOSE"


class RunPodSpendBlocked(RuntimeError):
    """Raised when something tries to submit a RunPod job it may not pay for."""


def current_purpose() -> str:
    return os.getenv(ENV_VAR, "").strip().lower()


def is_allowed(purpose: str = "") -> bool:
    """True if this caller may submit a RunPod job."""
    return (purpose or current_purpose()) in ALLOWED


def allow(purpose: str) -> None:
    """Declare the purpose of this process, for entry points that know it."""
    os.environ[ENV_VAR] = purpose.strip().lower()


def check(what: str = "this job", purpose: str = "") -> None:
    """Refuse the submission unless its purpose is allowed.

    Raises RunPodSpendBlocked with an actionable message. Callers that would
    rather degrade than crash should use is_allowed() and fall back to a local
    renderer instead of catching this.
    """
    p = purpose or current_purpose()
    if p in ALLOWED:
        return
    raise RunPodSpendBlocked(
        f"RunPod submission blocked for {what}. The credit is dedicated to the "
        f"85K profile's dancing pipeline; {ENV_VAR} is "
        f"{('set to ' + repr(p)) if p else 'not set'}, and the only allowed "
        f"value is {sorted(ALLOWED)}. Set {ENV_VAR}=dance for the profile "
        f"pipeline, or edit ALLOWED in modules/runpod_guard.py to widen it."
    )
