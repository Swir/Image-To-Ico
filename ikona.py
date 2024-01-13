import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import imageio.v2 as imageio

class ImageToIconConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Image to Icon Converter")

        self.input_files = []
        self.output_file = tk.StringVar()
        self.selected_index = -1

        # Ramka
        frame = ttk.Frame(root, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Ramka dla podglądu i przycisków
        content_frame = ttk.LabelFrame(frame, text="Image Processing", padding=(10, 5))
        content_frame.grid(row=0, column=0, padx=10, pady=10, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Podgląd obrazu
        self.image_preview_label = ttk.Label(content_frame, text="Image Preview")
        self.image_preview_label.grid(row=0, column=0, columnspan=4, pady=(10, 10))

        # Przyciski dodawania/usuwania obrazów
        ttk.Button(content_frame, text="Add Image", command=self.add_image).grid(row=1, column=0, pady=5)
        ttk.Button(content_frame, text="Remove Image", command=self.remove_image).grid(row=1, column=1, pady=5)

        # Przycisk konwersji
        ttk.Button(content_frame, text="Convert to ICO", command=self.convert_to_ico).grid(row=2, column=0, columnspan=2, pady=(10, 0))

    def add_image(self):
        files = filedialog.askopenfilenames(title="Select Image Files", filetypes=[("Image files", "*.png;*.jpg")])
        self.input_files.extend(files)

        # Aktualizacja podglądu po dodaniu nowych obrazów
        selected_index = 0 if self.input_files else -1
        self.update_image_preview(selected_index)

    def remove_image(self):
        if self.input_files:
            del self.input_files[-1]

        # Aktualizacja podglądu po usunięciu obrazów
        selected_index = 0 if self.input_files else -1
        self.update_image_preview(selected_index)

    def convert_to_ico(self):
        if not self.input_files:
            messagebox.showerror("Error", "No images selected.")
            return

        output_file = filedialog.asksaveasfilename(defaultextension=".ico", filetypes=[("Icon files", "*.ico")])
        if not output_file:
            return

        images = [imageio.imread(file) for file in self.input_files]

        try:
            imageio.mimsave(output_file, images, format="ICO", duration=0.2)
            messagebox.showinfo("Success", f"ICO file created: {output_file}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def update_image_preview(self, selected_index):
        self.selected_index = selected_index

        if selected_index >= 0 and selected_index < len(self.input_files):
            file_path = self.input_files[selected_index]
            image = Image.open(file_path)
            image.thumbnail((100, 100))
            photo = ImageTk.PhotoImage(image)
            self.image_preview_label.configure(image=photo)
            self.image_preview_label.image = photo
        else:
            self.image_preview_label.configure(image=None)

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageToIconConverter(root)

    root.mainloop()
