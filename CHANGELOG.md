# Changelog

## 1.1.0 — 2026-10-19

- Replace the failing imageio multi-image ICO route with Pillow's verified multi-resolution ICO writer.
- Export one icon per source image; batches use separate filenames and preserve existing output files.
- Select embedded 16, 24, 32, 48, 64, 128 and 256 pixel sizes.
- Preserve image proportions, alpha transparency and JPEG EXIF orientation with transparent padding.
- Validate PNG/JPEG input and report corrupt or oversized images without replacing existing files.
- Save icons atomically and reopen every requested size to verify the output before finalizing it.
- Keep conversion work off the Tk thread, provide cancellation between images and show per-file results.
- Add regression and frozen-runtime tests that create, export and reopen real PNG/JPEG-derived icons.
