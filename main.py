import tkinter as tk

import json
from pathlib import Path
import tkinter as tk

# Keep the data file beside main.py, regardless of where you run Python.
DATA_FILE = Path(__file__).resolve().parent / "car_data.json"

# ==================================================
# 1. BUTTON ACTIONS
# Functions here describe what happens when you click.
# ==================================================


def clear_inputs():
    car_entry.delete(0, tk.END)
    mileage_entry.delete(0, tk.END)
    car_entry.focus_set()


def show_car():
    car_name = car_entry.get().strip()
    mileage_text = mileage_entry.get().strip()

    if not car_name:
        result_label.config(text="Car Name")
        return

    # Convert the text to an integer.
    # Reject letters, decimal numbers, and empty input.
    try:
        mileage = int(mileage_text)
    except ValueError:
        result_label.config(text="Enter mileage")
        return

    if mileage < 0:
        result_label.config(text="Mileage can't be negative dumbass")
        return

    result_label.config(text=f"Car: {car_name}\nMileage: {mileage:,} miles")

    # A dictionary stores values under descriptive keys.
    car_data = {
        "name": car_name,
        "mileage": mileage,
    }

    # Write the dictionary as readable JSON text.
    try:
        with DATA_FILE.open("w", encoding="utf-8") as file:
            json.dump(car_data, file, indent=4)
    except OSError:
        result_label.config(text="Car could not be saved, Check folder permissions.")
        return

    result_label.config(text=f"{car_name}\n {mileage:,} miles")
    clear_inputs()


def delete_car():
    try:
        DATA_FILE.unlink()
    except FileNotFoundError:
        result_label.config(text="There is no saved car to delete")
    except OSError:
        result_label.config(text="Could not delete the saved car")
        return
    else:
        result_label.config(text="Saved car deleted")

    clear_inputs()


# ==================================================
# 2. MAIN WINDOW
# Customize the window title and starting size here.
# ==================================================

window = tk.Tk()
window.title("Auto Maintenance")
window.geometry("450x450")


# ==================================================
# 3. HEADING
# Customize the heading text, font, and spacing here.
# ==================================================

heading_label = tk.Label(
    window,
    text="Car Maintenance Tracker",
    font=("Arial", 16),
)
heading_label.pack(pady=20)


# ==================================================
# 4. CAR INPUT
# A label explains what to enter in the text box.
# ==================================================

car_label = tk.Label(
    window,
    text="Enter car's year, make, and model:",
)
car_label.pack(pady=5)

car_entry = tk.Entry(window, width=35)
car_entry.pack(pady=5)

# Put the typing cursor in this box when the app opens.
car_entry.focus_set()

# CURRENT MILEAGE INPUT
mileage_label = tk.Label(window, text="Current mileage:")
mileage_label.pack(pady=5)

mileage_entry = tk.Entry(window, width=35)
mileage_entry.pack(pady=5)

# ==================================================
# 5. BUTTON
# command=show_car connects the button to our function.
# ==================================================

show_button = tk.Button(
    window,
    text="Save Car",
    command=show_car,
)
show_button.pack(pady=10)

delete_button = tk.Button(
    window,
    text="Delete saved car",
    command=delete_car,
)
delete_button.pack(pady=5)

# ==================================================
# 6. RESULT
# The show_car function changes this label's text.
# wraplength lets long text wrap onto another line.
# ==================================================

result_label = tk.Label(
    window,
    text="Car will appear here",
    wraplength=400,
)
result_label.pack(pady=10)


# ==================================================
# 7. START THE APP
# Keep this after the code that creates the widgets.
# It handles clicks, typing, and other window events.
# ==================================================

# ==================================================
# LOAD SAVED CAR
# Run after the widgets exist so we can fill them in.
# ==================================================

try:
    with DATA_FILE.open("r", encoding="utf-8") as file:
        saved_car = json.load(file)

    # Check the data before using it.
    if not isinstance(saved_car, dict):
        raise ValueError("Expected a dictionary.")

    saved_name = saved_car.get("name")
    saved_mileage = saved_car.get("mileage")

    if not isinstance(saved_name, str) or not saved_name.strip():
        raise ValueError("Invalid car name.")

    if type(saved_mileage) is not int or saved_mileage < 0:
        raise ValueError("Invalid mileage.")

except FileNotFoundError:
    # Normal on the first run: there is nothing to load yet.
    pass

except (OSError, ValueError):
    result_label.config(text="Could not load saved data. Enter your car again.")

else:
    car_entry.insert(0, saved_name)
    mileage_entry.insert(0, str(saved_mileage))
    result_label.config(text=f"My car: {saved_name}\nMileage: {saved_mileage:,} miles")

window.mainloop()
