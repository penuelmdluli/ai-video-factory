"""
Retry & Error Recovery — Production-grade retry logic for all pipeline steps.
"""
import asyncio
import functools
import traceback
from datetime import datetime


def retry_async(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """
    Decorator for async functions with exponential backoff retry.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay on each retry
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                        print(f"[Retry] Retrying in {current_delay:.1f}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"[Retry] {func.__name__} failed after {max_retries + 1} attempts")

            raise last_exception

        return wrapper
    return decorator


def retry_sync(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """Decorator for sync functions with exponential backoff retry."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        print(f"[Retry] {func.__name__} failed (attempt {attempt + 1}): {e}")
                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception

        return wrapper
    return decorator


async def safe_execute(name: str, coro, default=None):
    """Execute an async operation safely, returning default on failure."""
    try:
        return await coro
    except Exception as e:
        print(f"[SafeExec] {name} failed: {e}")
        traceback.print_exc()
        return default


class PipelineHealthCheck:
    """Track pipeline health and provide diagnostics."""

    def __init__(self):
        self.checks = {}

    async def check_gemini(self) -> bool:
        """Verify Gemini API is accessible."""
        try:
            from config import GEMINI_API_KEY
            if not GEMINI_API_KEY:
                self.checks["gemini"] = "NO_KEY"
                return False
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Say 'ok' in one word.",
            )
            self.checks["gemini"] = "OK"
            return True
        except Exception as e:
            self.checks["gemini"] = f"FAIL: {e}"
            return False

    async def check_pexels(self) -> bool:
        """Verify Pexels API is accessible."""
        try:
            from config import PEXELS_API_KEY
            if not PEXELS_API_KEY:
                self.checks["pexels"] = "NO_KEY"
                return False
            import requests
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": "test", "per_page": 1},
                timeout=10,
            )
            resp.raise_for_status()
            self.checks["pexels"] = "OK"
            return True
        except Exception as e:
            self.checks["pexels"] = f"FAIL: {e}"
            return False

    async def check_edge_tts(self) -> bool:
        """Verify edge-tts works."""
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            self.checks["edge_tts"] = f"OK ({len(voices)} voices)"
            return True
        except Exception as e:
            self.checks["edge_tts"] = f"FAIL: {e}"
            return False

    async def check_elevenlabs(self) -> bool:
        """Verify ElevenLabs API is accessible."""
        try:
            from config import ELEVENLABS_API_KEY
            if not ELEVENLABS_API_KEY:
                self.checks["elevenlabs"] = "NO_KEY (will use edge-tts)"
                return False
            from elevenlabs import ElevenLabs
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            voices = client.voices.get_all()
            self.checks["elevenlabs"] = f"OK ({len(voices.voices)} voices)"
            return True
        except Exception as e:
            self.checks["elevenlabs"] = f"FAIL: {e}"
            return False

    async def check_ffmpeg(self) -> bool:
        """Verify FFmpeg is installed."""
        try:
            import subprocess
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.split("\n")[0]
                self.checks["ffmpeg"] = f"OK ({version[:40]})"
                return True
            self.checks["ffmpeg"] = "FAIL: non-zero exit"
            return False
        except Exception as e:
            self.checks["ffmpeg"] = f"FAIL: {e}"
            return False

    async def check_openai(self) -> bool:
        """Verify OpenAI API (for DALL-E)."""
        try:
            from config import OPENAI_API_KEY
            if not OPENAI_API_KEY:
                self.checks["openai_dalle"] = "NO_KEY (will use Pexels only)"
                return False
            self.checks["openai_dalle"] = "KEY_SET (DALL-E available)"
            return True
        except Exception as e:
            self.checks["openai_dalle"] = f"FAIL: {e}"
            return False

    async def run_all(self) -> dict:
        """Run all health checks."""
        print("\n--- Pipeline Health Check ---")

        await asyncio.gather(
            self.check_gemini(),
            self.check_pexels(),
            self.check_edge_tts(),
            self.check_elevenlabs(),
            self.check_ffmpeg(),
            self.check_openai(),
        )

        all_ok = all(v.startswith("OK") for v in self.checks.values() if not v.startswith("NO_KEY"))

        for name, status in self.checks.items():
            icon = "OK" if status.startswith("OK") else ("SKIP" if "NO_KEY" in status else "FAIL")
            print(f"  [{icon}] {name}: {status}")

        print(f"  Overall: {'READY' if all_ok else 'ISSUES DETECTED'}")
        print("---\n")

        return {
            "status": "ready" if all_ok else "degraded",
            "checks": self.checks,
            "timestamp": datetime.now().isoformat(),
        }
