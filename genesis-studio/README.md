# Genesis Studio — motion graphics as code

Remotion project for Genesis News / Mzansi Careers graphics. Two ways in:

    npm run studio                  # live editor: timeline, preview, scrubbing
    node render.mjs props.json out.mp4 StatsBand    # headless, for the pipeline

The Python pipeline stays the source of truth for DATA (news feeds, standings,
the DPSA circular) and for the verification gate. This project only draws.
The contract between them is a JSON file of props.

## Why

Every graphics bug in the PIL templates came from the same root cause: there
is no layout engine, so each element's position and size is arithmetic we
write by hand. Text ran off the edges, headings collided with chips, and each
new template repeated the work. Here the browser does layout — flexbox,
ellipsis, wrapping — so those bugs cannot occur.

## Status

  StatsBand — the live league band that runs under match footage. Ported and
  rendering from real standings data.

Renders write to out/. First render downloads a headless Chrome shell (~113MB,
once).
