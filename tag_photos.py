import os
import shutil
import subprocess
from tkinter import Tk, Label, Entry, Button, StringVar, Canvas, filedialog
from PIL import Image, ImageTk
import json
import sys

# -------------------------
# Configuration
# -------------------------
SOURCE_FOLDER = filedialog.askdirectory(title="Select folder with photos")
PARENT_DIR = os.path.dirname(SOURCE_FOLDER)
DEST_FOLDER = os.path.join(PARENT_DIR, "tagged_photos")
os.makedirs(DEST_FOLDER, exist_ok=True)

images = [f for f in os.listdir(SOURCE_FOLDER) if f.lower().endswith((".jpg", ".jpeg"))]
if not images:
    print("No images found in folder.")
    exit()

index = 0

# -------------------------
# Helper functions
# -------------------------
def read_exif(file):
    try:
        out = subprocess.check_output(
            ["exiftool", "-DateTimeOriginal", "-j", file],
            universal_newlines=True
        )
        data = json.loads(out)[0]  # ExifTool returns a list with one dictionary
        date = data.get("DateTimeOriginal", "").split()[0].replace(":", "-")

        return date
    except:
        return ""

def get_sidecar_path(img_path):
    return os.path.splitext(img_path)[0] + ".json"

def read_sidecar(img_path):
    path = get_sidecar_path(img_path)
    if not os.path.exists(path):
        return "", "", "", ""

    try:
        with open(path, "r") as f:
            data = json.load(f)
        return (
            data.get("date", ""),
            data.get("airport", ""),
            data.get("registration", ""),
            data.get("aircraft", "")
        )
    except Exception as e:
        print("Sidecar read error:", e)
        return "", "", "", ""

def write_sidecar(img_path, date, airport, reg, aircraft):
    sidecar_path = get_sidecar_path(img_path)
    with open(sidecar_path, "w") as f:
        json.dump(
            {
                "date": date,
                "airport": airport,
                "registration": reg,
                "aircraft": aircraft
            },
            f,
            indent=2
        )

def save_and_next(event=None):
    global index

    if index >= len(images):
        complete_gallery()
        return

    img_file = os.path.join(SOURCE_FOLDER, images[index])

    # write sidecar
    write_sidecar(
        img_file,
        date_var.get(),
        airport_var.get(),
        reg_var.get(),
        aircraft_var.get()
    )

    # move image + sidecar together
    shutil.move(img_file, os.path.join(DEST_FOLDER, images[index]))
    
    sidecar = get_sidecar_path(img_file)
    if os.path.exists(sidecar):
        shutil.move(
            sidecar,
            os.path.join(DEST_FOLDER, os.path.basename(sidecar))
        )

    # --- Call uploader script ---
    subprocess.call([
        sys.executable,               # Python executable
        "upload_to_gdrive.py",        # uploader script
        os.path.join(DEST_FOLDER, images[index]),  # path to the moved image
        os.path.join(DEST_FOLDER, get_sidecar_path(images[index])),  # path to the moved sidecar
        date_var.get(),
        airport_var.get()
    ])
    
    index += 1
    if index < len(images):
        load_image()
    else:
        complete_gallery()

def skip(event=None):
    global index
    index += 1
    
    if index < len(images):
        load_image()
    else:
        complete_gallery()

def load_image():
    img_file = os.path.join(SOURCE_FOLDER, images[index])
    img = Image.open(img_file)
    img.thumbnail((1200, 900))
    canvas.img = ImageTk.PhotoImage(img)
    canvas.delete("all")
    canvas.create_image(0, 0, anchor="nw", image=canvas.img)

    # Read sidecar first
    sc_date, airport, reg, aircraft = read_sidecar(img_file)

    # Read EXIF date
    exif_date = read_exif(img_file)

    # Date logic: EXIF wins if present
    if exif_date:
        date_var.set(exif_date)
    else:
        date_var.set(sc_date)

    airport_var.set(airport)
    reg_var.set(reg)
    aircraft_var.set(aircraft)

    entries[0].focus_set()  # focus first input field

def complete_gallery():
    try:
        # 1. Generate gallery by calling the script
        subprocess.check_call([sys.executable, "generate_gallery.py"])

        # 2. Commit & push to GitHub (DEST_FOLDER must be inside repo)
        subprocess.check_call(["git", "add", "."])
        subprocess.check_call(["git", "commit", "-m", "Update gallery"])
        subprocess.check_call(["git", "push", "origin", "main"])

        # 3. Show confirmation popup
        messagebox.showinfo("Upload Complete", "All photos uploaded and gallery updated!")

    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"An error occurred during gallery generation or git push:\n{e}")

    finally:
        root.destroy()

# -------------------------
# GUI Setup
# -------------------------
root = Tk()
root.title("Photo Tagger")

canvas = Canvas(root, width=1200, height=900)
canvas.pack()

# Input fields
date_var = StringVar()
airport_var = StringVar()
reg_var = StringVar()
aircraft_var = StringVar()

# Auto-uppercase callback
def uppercase_var(var, *args):
    var.set(var.get().upper())
airport_var.trace_add("write", lambda *args: uppercase_var(airport_var))
reg_var.trace_add("write", lambda *args: uppercase_var(reg_var))
aircraft_var.trace_add("write", lambda *args: uppercase_var(aircraft_var))

fields = [("Date (YYYY-MM-DD):", date_var),
          ("Airport ICAO:", airport_var),
          ("Registration:", reg_var),
          ("Aircraft Type:", aircraft_var)]

entries = []
for txt, var in fields:
    Label(root, text=txt).pack()
    e = Entry(root, textvariable=var, fg="green")
    e.pack()
    entries.append(e)

# Bind Enter in last field to Save & Next
entries[-1].bind("<Return>", save_and_next)

# Buttons
Button(root, text="Quit", command=root.destroy, bg="red", fg="white", width=12).pack(side="left", padx=5, pady=5)
Button(root, text="Skip", command=skip, bg="yellow", fg="black", width=12).pack(side="left", padx=5, pady=5)
Button(root, text="Save & Next", command=save_and_next, bg="green", fg="white", width=15).pack(side="right", padx=5, pady=5)

# Load first image
load_image()

root.mainloop()
