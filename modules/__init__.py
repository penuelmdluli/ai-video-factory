# AI Video Factory Modules

# Scope every render's temp audio to its own build directory. See
# modules/safe_render.py for the 2026-09-02 role-slot failure this prevents:
# every builder writes work/final.mp4 from the repo root, so MoviePy's default
# put all of their temp audio in ONE file, and two overlapping builds deleted
# it out from under each other.
#
# Installed here because it has to be live for all 43 write_videofile calls in
# the repo, and every builder imports modules.*. The cost is that moviepy now
# loads for non-render importers too (the comment engine, the facts checker):
# about 1.1s on a batch job, which is why the failure is swallowed rather than
# raised - a render safeguard must never be the reason a football reply or an
# integrity check cannot run.
try:
    from modules.safe_render import install as _install_render_safety

    _install_render_safety()
except Exception:  # pragma: no cover - moviepy absent or broken
    pass
