"""PNG/JPEG icon converter with main-thread UI and cancellable batch export."""
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
from ico_core import ICON_SIZES, convert_batch, convert_image, load_image, validate_sizes

VERSION = "1.1.0"


class ImageToIconConverter:
    def __init__(self, root):
        self.root = root
        self.input_files = []
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.close_requested = False
        self.poll_id = None
        self.last_results = []
        self.preview_photo = None
        root.title(f"Image to ICO {VERSION} — Swir")
        root.geometry("720x570")
        root.minsize(570, 470)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame = ttk.Frame(root, padding=16)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.files = tk.Listbox(frame, exportselection=False, height=8)
        self.files.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.files.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.files.configure(yscrollcommand=scroll.set)
        self.preview = ttk.Label(frame, text="Image preview", width=22, anchor="center")
        self.preview.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        self.files.bind("<<ListboxSelect>>", self.preview_selection)
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=3, pady=12)
        self.add_button = ttk.Button(buttons, text="Add PNG / JPEG…", command=self.add_image)
        self.add_button.pack(side="left", padx=5)
        self.remove_button = ttk.Button(buttons, text="Remove selected", command=self.remove_image)
        self.remove_button.pack(side="left", padx=5)
        sizes = ttk.LabelFrame(frame, text="Sizes inside each ICO", padding=10)
        sizes.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.size_vars = {size: tk.BooleanVar(root, True) for size in ICON_SIZES}
        self.size_checks = []
        for column, size in enumerate(ICON_SIZES):
            check = ttk.Checkbutton(sizes, text=str(size), variable=self.size_vars[size])
            check.grid(row=0, column=column, padx=4)
            self.size_checks.append(check)
        ttk.Label(frame, text="One source image creates one icon. Images keep their proportions with transparent padding.", wraplength=650).grid(row=3, column=0, columnspan=3, sticky="w", pady=10)
        export = ttk.Frame(frame)
        export.grid(row=4, column=0, columnspan=3, pady=6)
        self.convert_button = ttk.Button(export, text="Convert to ICO…", command=self.convert_to_ico)
        self.convert_button.pack(side="left", padx=5)
        self.cancel_button = ttk.Button(export, text="Cancel batch", command=self.cancel.set, state="disabled")
        self.cancel_button.pack(side="left", padx=5)
        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew", pady=8)
        self.status = tk.StringVar(root, "Add one or more PNG/JPEG images.")
        ttk.Label(frame, textvariable=self.status, wraplength=660).grid(row=6, column=0, columnspan=3, sticky="ew")
        self.details = tk.Text(frame, height=5, wrap="word", state="disabled")
        self.details.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_image(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="Select PNG or JPEG images", filetypes=[("PNG / JPEG images", "*.png *.jpg *.jpeg")])
        for path in paths:
            if path not in self.input_files:
                self.input_files.append(path)
                self.files.insert("end", Path(path).name)
        if self.input_files:
            self.files.selection_clear(0, "end")
            self.files.selection_set(0)
            self.update_image_preview(0)

    def preview_selection(self, _event=None):
        selection = self.files.curselection()
        self.update_image_preview(selection[0] if selection else -1)

    def update_image_preview(self, index):
        self.preview_photo = None
        self.preview.configure(image="", text="Image preview")
        if not 0 <= index < len(self.input_files):
            return
        try:
            image = load_image(self.input_files[index])
            image.thumbnail((180, 180), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(image, master=self.root)
            self.preview.configure(image=self.preview_photo, text="")
            self.status.set(Path(self.input_files[index]).name)
        except (OSError, ValueError) as error:
            self.status.set(f"Cannot preview this image: {error}")

    def remove_image(self):
        selection = self.files.curselection()
        if selection:
            del self.input_files[selection[0]]
            self.files.delete(selection[0])
        if self.input_files:
            self.files.selection_set(min(selection[0] if selection else 0, len(self.input_files) - 1))
        self.preview_selection()

    def selected_sizes(self):
        return validate_sizes([size for size, variable in self.size_vars.items() if variable.get()])

    def convert_to_ico(self):
        if not self.input_files:
            self.status.set("Add at least one image first.")
            return
        try:
            self.selected_sizes()
        except ValueError as error:
            self.status.set(str(error))
            return
        if len(self.input_files) == 1:
            destination = filedialog.asksaveasfilename(parent=self.root, title="Save icon", initialfile=Path(self.input_files[0]).stem + ".ico", defaultextension=".ico", confirmoverwrite=True, filetypes=[("Windows icon", "*.ico")])
        else:
            destination = filedialog.askdirectory(parent=self.root, title="Output folder — existing files are preserved", mustexist=True)
        if destination:
            self.begin_conversion(destination, overwrite=len(self.input_files) == 1)

    def begin_conversion(self, destination, *, overwrite=False):
        if self.worker is not None and self.worker.is_alive():
            return False
        try:
            sizes = self.selected_sizes()
            if not self.input_files:
                raise ValueError("Add at least one image first.")
        except ValueError as error:
            self.status.set(str(error))
            return False
        sources = tuple(self.input_files)
        self.last_results = []
        self.cancel.clear()
        self.progress.configure(maximum=len(sources), value=0)
        self.status.set("Converting…")
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.configure(state="disabled")
        for widget in [self.add_button, self.remove_button, self.convert_button, *self.size_checks]:
            widget.configure(state="disabled")
        self.cancel_button.configure(state="normal")

        def work():
            try:
                if len(sources) == 1:
                    if not self.cancel.is_set():
                        output = convert_image(sources[0], destination, sizes, overwrite=overwrite)
                        self.events.put({"source": sources[0], "output": str(output), "ok": True})
                else:
                    for result in convert_batch(sources, destination, sizes, self.cancel):
                        self.events.put(result)
            except Exception as error:
                self.events.put({"source": sources[0] if len(sources) == 1 else "Batch", "ok": False, "error": str(error)})
            finally:
                self.events.put(None)

        self.worker = threading.Thread(target=work, name="ico-export", daemon=False)
        self.worker.start()
        self.poll_id = self.root.after(50, self.poll_results)
        return True

    def poll_results(self):
        self.poll_id = None
        finished = False
        while True:
            try:
                result = self.events.get_nowait()
            except queue.Empty:
                break
            if result is None:
                finished = True
                break
            self.last_results.append(result)
            self.progress.configure(value=len(self.last_results))
            line = f"Saved: {result['output']}" if result["ok"] else f"Failed: {Path(result['source']).name} — {result['error']}"
            self.details.configure(state="normal")
            self.details.insert("end", line + "\n")
            self.details.configure(state="disabled")
        if finished:
            self.worker.join()
            self.worker = None
            saved = sum(result["ok"] for result in self.last_results)
            failed = len(self.last_results) - saved
            self.status.set(f"{'Cancelled' if self.cancel.is_set() else 'Finished'}: {saved} saved, {failed} failed.")
            for widget in [self.add_button, self.remove_button, self.convert_button, *self.size_checks]:
                widget.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            if self.close_requested:
                self.root.destroy()
        else:
            self.poll_id = self.root.after(50, self.poll_results)

    def on_close(self):
        if self.worker is not None:
            self.close_requested = True
            self.cancel.set()
            self.status.set("Finishing the current image before closing…")
        else:
            self.root.destroy()


def self_test(report):
    root = app = None
    result = {"application":"Image-To-Ico", "version":VERSION, "passed":False}
    try:
        parent = Path(report).resolve().parent
        with tempfile.TemporaryDirectory(prefix="ico-smoke-", dir=parent) as directory:
            folder = Path(directory).resolve()
            if not folder.is_relative_to(parent):
                raise RuntimeError("Unexpected smoke-test directory")
            first, second = folder / "sample.png", folder / "photo.jpg"
            Image.new("RGBA", (80, 40), (30, 160, 200, 128)).save(first)
            Image.new("RGB", (40, 80), (220, 80, 20)).save(second)
            root = tk.Tk()
            root.withdraw()
            app = ImageToIconConverter(root)
            app.input_files = [str(first), str(second)]
            app.update_image_preview(0)
            assert app.preview_photo is not None
            assert app.begin_conversion(folder)
            deadline = time.monotonic() + 20
            while app.worker is not None and time.monotonic() < deadline:
                root.update()
                time.sleep(.01)
            assert app.worker is None and len(app.last_results) == 2 and all(item["ok"] for item in app.last_results)
            for stem in ("sample", "photo"):
                with Image.open(folder / f"{stem}.ico") as image:
                    assert image.ico.sizes() == {(size, size) for size in ICON_SIZES}
            root.destroy()
            root = None
            result.update(passed=True, checks=["Tk and image preview", "background PNG/JPEG batch", "all seven ICO sizes", "decoded output files"])
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        if app is not None and app.worker is not None:
            app.cancel.set()
            app.worker.join(timeout=30)
        if root is not None:
            if app is not None and app.poll_id is not None:
                root.after_cancel(app.poll_id)
            root.destroy()
        Path(report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["passed"] else 1


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        return self_test(sys.argv[2])
    root = tk.Tk()
    ImageToIconConverter(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
