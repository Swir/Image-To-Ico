"""PNG/JPEG to multi-resolution ICO conversion without silent overwrites."""
import os
from pathlib import Path
import tempfile
import warnings
from PIL import Image, ImageOps

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
MAX_PIXELS = 40_000_000


def validate_sizes(sizes):
    values = tuple(sorted(set(sizes)))
    if not values or any(type(value) is not int or value not in ICON_SIZES for value in values):
        raise ValueError("Choose at least one icon size: 16, 24, 32, 48, 64, 128 or 256.")
    return values


def load_image(path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format not in ("PNG", "JPEG"):
                    raise ValueError("Only PNG and JPEG input is supported.")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("The input image exceeds the 40-megapixel limit.")
                image.load()
                return ImageOps.exif_transpose(image).convert("RGBA")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("The image is too large to decode safely.") from error


def icon_canvas(path, sizes=ICON_SIZES):
    sizes = validate_sizes(sizes)
    image = load_image(path)
    side = max(sizes)
    fitted = ImageOps.contain(image, (side, side), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(fitted, ((side - fitted.width) // 2, (side - fitted.height) // 2))
    return canvas, sizes


def convert_image(source, destination, sizes=ICON_SIZES, *, overwrite=False):
    source, destination = Path(source), Path(destination)
    if destination.suffix.lower() != ".ico":
        raise ValueError("The output filename must end in .ico.")
    if source.resolve() == destination.resolve():
        raise ValueError("The source image cannot be overwritten.")
    canvas, sizes = icon_canvas(source, sizes)
    temporary = None
    reserved_inode = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent, prefix=".ico-export-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            canvas.save(stream, format="ICO", sizes=[(size, size) for size in sizes])
            stream.flush()
            os.fsync(stream.fileno())
        with Image.open(temporary) as exported:
            if exported.format != "ICO" or exported.ico.sizes() != {(size, size) for size in sizes}:
                raise ValueError("The saved icon did not contain the requested sizes.")
            for size in sizes:
                exported.ico.getimage((size, size)).load()
        if not overwrite:
            descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            try:
                reserved_inode = os.fstat(descriptor).st_ino
            finally:
                os.close(descriptor)
        os.replace(temporary, destination)
        reserved_inode = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if reserved_inode is not None:
            try:
                info = destination.stat()
                if info.st_ino == reserved_inode and info.st_size == 0:
                    destination.unlink()
            except FileNotFoundError:
                pass
    return destination


def next_output_path(folder, stem):
    folder = Path(folder)
    candidate = folder / (stem + ".ico")
    counter = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({counter}).ico"
        counter += 1
    return candidate


def convert_batch(sources, directory, sizes=ICON_SIZES, cancel=None):
    sizes = validate_sizes(sizes)
    if not Path(directory).is_dir():
        raise ValueError("Select an existing output directory.")
    for source in sources:
        if cancel is not None and cancel.is_set():
            break
        source = Path(source)
        try:
            for _attempt in range(100):
                destination = next_output_path(directory, source.stem)
                try:
                    convert_image(source, destination, sizes)
                    break
                except FileExistsError:
                    continue
            else:
                raise OSError("Could not reserve an unused output filename.")
            yield {"source": str(source), "output": str(destination), "ok": True}
        except (OSError, ValueError) as error:
            yield {"source": str(source), "ok": False, "error": str(error)}
