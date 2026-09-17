# README migration verification — 2026-09-17

This is a documentation-quality and bounded source-behavior check, not a new application release or full product qualification.

## Evidence baseline

- Reviewed the complete README, `ikona.py`, `requirements.txt`, repository tree, existing release workflow, open pull requests and public release metadata.
- Tested a byte-identical local copy of `ikona.py`, Git blob SHA `dcd6943d6ff3b60b54942d3060a28c1aada2cb7d`.
- Existing package: `v1.0.0`, published 2026-09-12, with Windows x64 ZIP, ZIP SHA-256 sidecar and EXE. Package metadata was read; the EXE was not executed.
- No existing project icon, documentation banner, dedicated roadmap or LICENSE file was present in the inspected tree.

## Source checks actually executed

Environment: Linux, Python 3.13.5, Tk 8.6.16 under Xvfb, Pillow 12.3.0 and imageio 2.37.3.

The existing `ImageToIconConverter` class was instantiated in a real Tk window. File chooser and message-box functions were replaced only in the local test harness, not in application source. Preview creation and image export used the actual libraries.

| Check | Result |
|---|---|
| Instantiate/update/destroy the Tk window | PASS |
| Empty selection reports the existing error dialog | PASS |
| Add a generated 64 × 64 RGB PNG and display its preview | PASS |
| Export that PNG as ICO and reopen it with Pillow | PASS |
| Add a generated 64 × 64 RGB JPG and display its preview | PASS |
| Export that JPG as ICO and reopen it with Pillow | PASS |
| Cancel the save dialog without calling the writer, for both input types | PASS |
| Remove clears a single selection; with two inputs it removes the last | PASS |
| Submit two 64 × 64 images to the existing imageio export call | FAIL — `KeyError: 'ICO'` |

A minimal reproduction of the export limitation with those library versions:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

import imageio.v2 as imageio
from PIL import Image

with TemporaryDirectory() as directory:
    root = Path(directory)
    inputs = []
    for index in range(2):
        source = root / f"input-{index}.png"
        Image.new("RGB", (64, 64), (0, 136, 255)).save(source)
        inputs.append(imageio.imread(source))
    # Same writer invocation as ikona.py; fails for two images in this environment.
    imageio.mimsave(root / "output.ico", inputs, format="ICO", duration=0.2)
```

`requirements.txt` contains `pip install pillow tk imageio`, so the README now documents direct dependency installation instead of treating that shell command as a valid requirements list. The file itself is unchanged.

## Documentation checks

- Validated the v2 marker, 12 visible project-specific search phrases, internal navigation targets, relative paths, the project name as real text and preserved attribution.
- Parsed both self-contained SVG assets as XML and rendered them with CairoSVG; visually reviewed the hero.
- Rendered the README locally with MarkdownIt and Chromium at 1280 and 390 pixels. Both SVGs loaded, navigation targets existed and neither viewport had page-level horizontal overflow. Visually reviewed both header layouts.
- The local review used an approximate documentation stylesheet. Remote badges were labelled placeholders in that local review only; the committed README uses actual badge URLs. This was not a GitHub-hosted render or an external badge-availability test.

The existing workflow publishes releases on selected main/workflow changes, tags or manual dispatch; it has no pull-request documentation test. This migration does not modify or manually run that publishing workflow. Local checks must not be reported as a new green Windows CI run.

## Boundaries

No changes to `ikona.py`, dependency files, workflow files, versions, release tags or published binaries. The new icon is for repository documentation only and is not embedded into the existing EXE. No new license was assigned. Windows interactive behavior, a fresh Windows installation, arbitrary image dimensions/formats and broad cross-platform compatibility were not tested.
