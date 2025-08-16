import tkinter as tk
from tkinter import filedialog, messagebox
import os

def merge_files_from_multiple_dirs():
    root = tk.Tk()
    root.withdraw()

    all_file_paths = []

    while True:
        file_paths = filedialog.askopenfilenames(title="Select files")
        if not file_paths:
            break
        all_file_paths.extend(file_paths)

        add_more = messagebox.askyesno("Add More?", "Do you want to add more files from another directory?")
        if not add_more:
            break

    if not all_file_paths:
        print("No files selected.")
        return

    output_lines = []
    for file_path in all_file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            file_name = os.path.basename(file_path)
            output_lines.append(f"{file_name}:\n{content}\n")
        except Exception as e:
            print(f"Could not read {file_path}: {e}")

    output_path = filedialog.asksaveasfilename(
        title="Save merged file as",
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt")]
    )

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as out_file:
            out_file.write('\n'.join(output_lines))
        print(f"Files merged into {output_path}")
    else:
        print("No output file selected.")

merge_files_from_multiple_dirs()