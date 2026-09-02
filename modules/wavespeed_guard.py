"""One gate in front of every WaveSpeed submission.

Owner call 2026-09-02: "NEVER USE WAVESPEED, it is reserved for the Penuel
Mdluli profile only. Never use AI to create video - only the baby dance can
use wavespeed."

This is the same spend boundary [[runpod_guard]] draws, for the same reason and
against a second vendor. WaveSpeed was never explicitly chosen by the content
pipelines that were spending on it: .env sets I2V_BACKEND='wan', and the wan
branch in modules/visual_fetcher.py falls through wan -> runpod -> WAVESPEED ->
stock. RunPod is already gated and every endpoint sits at workersMax 0, so both
earlier options fail by design and every scheduled build landed on WaveSpeed as
its "fallback". A Tech Pulse Africa news reel and a Herbal Organic Life herb
video were both generating paid AI clips at 15:26 on 2 Sep, unattended, on a
budget reserved for the profile.

That is why the gate lives HERE and not in a config default. Changing
I2V_BACKEND only redirects the branch that names WaveSpeed; it does nothing
about three other paths that reach it by falling over. A guard at the
submission point covers all of them, including any added later.

make_dance_reel.py is deliberately unaffected: it calls the WaveSpeed HTTP API
directly rather than going through modules/wavespeed_video.py, so the profile's
dancing pipeline keeps working untouched while everything else is refused.

To run the profile pipeline through this module:

    set WAVESPEED_PURPOSE=dance     (PowerShell:  $env:WAVESPEED_PURPOSE="dance")

or, in code, at the top of the entry point:

    from modules.wavespeed_guard import allow
    allow("dance")

Everything else - news reels, health, careers, football, motivation - is
refused and falls back to stock footage, which for those pages was always the
better visual anyway. This is a spend gate, not a security boundary: it exists
to stop an automated pipeline running up a bill unattended, and it says plainly
how to lift it.
"""
import os

# The only purpose permitted to spend WaveSpeed credit right now.
ALLOWED = {"dance"}

ENV_VAR = "WAVESPEED_PURPOSE"


class WaveSpeedSpendBlocked(RuntimeError):
    """Raised when something tries to submit a WaveSpeed job it may not pay for."""


def current_purpose() -> str:
    return os.getenv(ENV_VAR, "").strip().lower()


def is_allowed(purpose: str = "") -> bool:
    """True if this caller may submit a WaveSpeed job.

    Callers that would rather degrade than crash should use this and fall back
    to stock footage, instead of catching the exception from check().
    """
    return (purpose or current_purpose()) in ALLOWED


def allow(purpose: str) -> None:
    """Declare the purpose of this process, for entry points that know it."""
    os.environ[ENV_VAR] = purpose.strip().lower()


def check(what: str = "this clip", purpose: str = "") -> None:
    """Refuse the submission unless its purpose is allowed."""
    p = purpose or current_purpose()
    if p in ALLOWED:
        return
    raise WaveSpeedSpendBlocked(
        f"WaveSpeed submission blocked for {what}. The budget is reserved for "
        f"the Penuel Mdluli profile's dance pipeline; {ENV_VAR} is "
        f"{('set to ' + repr(p)) if p else 'not set'}, and the only allowed "
        f"value is {sorted(ALLOWED)}. Set {ENV_VAR}=dance for the profile "
        f"pipeline, or edit ALLOWED in modules/wavespeed_guard.py to widen it."
    )
