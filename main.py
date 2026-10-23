import tkinter as tk


# ==================================================
# 1. BUTTON ACTIONS
# Functions here describe what happens when you click.
# ==================================================


def show_car():
    # Read the text box and remove spaces at either end.
    car_name = car_entry.get().strip()

    # Show a helpful message if the text box is empty.
    if not car_name:
        result_label.config(text="Enter Car Here")
        return

    # Update the result label with the entered name.
    result_label.config(text=f"Shitbox: {car_name}")


# ==================================================
# 2. MAIN WINDOW
# Customize the window title and starting size here.
# ==================================================

window = tk.Tk()
window.title("Auto Maintenance")
window.geometry("450x300")


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


# ==================================================
# 5. BUTTON
# command=show_car connects the button to our function.
# ==================================================

show_button = tk.Button(
    window,
    text="Show car",
    command=show_car,
)
show_button.pack(pady=10)


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

window.mainloop()
