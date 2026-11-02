"""Auto Maintenance desktop app. Run with: python3 main.py

Sections below separate appearance, reusable dialogs, garage cards,
maintenance history, and the car diagram. Data/file rules live in maintenance.py.
"""

# ==================================================
# 1. IMPORTS AND APPEARANCE — customize these first
# ==================================================
import csv
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from maintenance import SERVICES, Garage, GarageStore, display_money, latest_record

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "garage_data.json"
BG = "#101827"
PANEL = "#1c293c"
TEXT = "#e8eef6"
MUTED = "#a5b6cb"
ACCENT = "#62d6b0"
CAR_COLOR = "#3c8db5"
FONT_FAMILY = "Helvetica"


# ==================================================
# 2. REUSABLE FORM WINDOW
# A modal dialog waits for input without opening another
# Tk instance. ttk widgets use the theme set by the app.
# ==================================================
class FormDialog(tk.Toplevel):
    def __init__(self, parent, title, fields, on_save):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(parent)
        self.on_save = on_save
        self.inputs = {}
        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)
        for row, (key, label, value, choices) in enumerate(fields):
            ttk.Label(body, text=label).grid(row=row * 2, column=0, sticky="w", pady=(8, 3))
            if key == "notes":
                widget = tk.Text(body, width=48, height=4, bg=PANEL, fg=TEXT,
                                 insertbackground=TEXT, wrap="word", relief="flat")
                widget.insert("1.0", value)
            elif choices:
                widget = ttk.Combobox(body, values=choices, width=46)
                widget.set(value)
            else:
                widget = ttk.Entry(body, width=48)
                widget.insert(0, str(value))
            widget.grid(row=row * 2 + 1, column=0, sticky="ew")
            self.inputs[key] = widget
        self.error = ttk.Label(body, text="", foreground="#ffb4aa", wraplength=400)
        self.error.grid(row=len(fields) * 2, column=0, sticky="w", pady=10)
        buttons = ttk.Frame(body)
        buttons.grid(row=len(fields) * 2 + 1, column=0, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=5)
        ttk.Button(buttons, text="Save", command=self.submit).pack(side="left")
        self.bind("<Escape>", lambda event: self.destroy())
        self.grab_set()
        first = next(iter(self.inputs.values()))
        first.focus_set()

    def submit(self):
        values = {}
        for key, widget in self.inputs.items():
            values[key] = widget.get("1.0", "end-1c") if isinstance(widget, tk.Text) else widget.get()
        try:
            self.on_save(values)
        except (ValueError, OSError) as error:
            self.error.config(text=str(error))
        else:
            self.destroy()


# ==================================================
# 3. APPLICATION WINDOW AND SHARED NAVIGATION
# One Garage object supplies the data for every view.
# ==================================================
class MaintenanceApp(tk.Tk):
    def __init__(self, data_path=DATA_FILE):
        super().__init__()
        self.title("Auto Maintenance | My Garage")
        self.geometry("1180x820")
        self.minsize(820, 600)
        self.configure(bg=BG)
        self.ai_window = None
        self.selected_id = None
        self.sort_column = "date"
        self.sort_descending = True
        self.configure_theme()
        self.store = GarageStore(data_path)
        try:
            imported = self.store.import_legacy(Path(data_path).parent / "car_data.json")
            self.garage = Garage(self.store)
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Cannot load saved data",
                f"{error}\n\nYour files have not been overwritten. Close the app and check "
                f"{data_path}. A previous version may be available as garage_data.json.bak.",
                parent=self,
            )
            self.destroy()
            raise RuntimeError("Cannot safely load the garage.") from error

        self.header = ttk.Frame(self, padding=(24, 18))
        self.header.pack(fill="x")
        ttk.Label(self.header, text="AUTO / MAINTENANCE", style="Brand.TLabel").pack(side="left")
        ttk.Button(self.header, text="My garage", command=self.show_garage).pack(side="right")
        self.fullscreen_button = ttk.Button(self.header, command=self.toggle_fullscreen)
        self.fullscreen_button.pack(side="right", padx=8)
        ttk.Button(self.header, text="Quit", command=self.destroy).pack(side="right")
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        self.set_fullscreen(True)
        self.content = ttk.Frame(self, padding=(24, 0, 24, 12))
        self.content.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Saved locally | Miles | Costs in USD | One app window at a time")
        ttk.Label(self, textvariable=self.status, padding=(24, 10), style="Muted.TLabel").pack(fill="x")
        self.show_garage()
        if imported:
            self.status.set("Imported your previous car. The original car_data.json was left unchanged.")

    def set_fullscreen(self, enabled):
        self.attributes("-fullscreen", enabled)
        self.fullscreen_button.configure(
            text="Windowed (F11)" if enabled else "Full screen (F11)")

    def toggle_fullscreen(self, event=None):
        self.set_fullscreen(not self.attributes("-fullscreen"))
        return "break"

    def exit_fullscreen(self, event=None):
        self.set_fullscreen(False)
        return "break"

    def configure_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=(FONT_FAMILY, 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG)
        style.configure("Brand.TLabel", font=(FONT_FAMILY, 15, "bold"), foreground=ACCENT)
        style.configure("Title.TLabel", font=(FONT_FAMILY, 23, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", background=PANEL, padding=(12, 8))
        style.map("TButton", background=[("active", "#34516a")], foreground=[("active", TEXT)])
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground=PANEL, foreground=TEXT, arrowsize=16)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=32, borderwidth=0)
        style.map("Treeview", background=[("selected", "#315b72")], foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background=BG, foreground=ACCENT, padding=8)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), background=PANEL)
        style.map("TNotebook.Tab", background=[("selected", "#315b72")])

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def current_car(self):
        return self.garage.car(self.selected_id)

    def set_status(self, text):
        self.status.set(text)

    # ==================================================
    # 4. GARAGE — scrollable cards, one per car
    # ==================================================
    def show_garage(self):
        self.selected_id = None
        self.clear_content()
        heading = ttk.Frame(self.content)
        heading.pack(fill="x", pady=(4, 16))
        ttk.Label(heading, text="My Garage", style="Title.TLabel").pack(side="left")
        ttk.Button(heading, text="+ Add car", command=self.car_dialog).pack(side="right")
        count = len(self.garage.cars)
        ttk.Label(self.content, text=f"{count} cars | Choose a car to open its service history",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 14))
        container = ttk.Frame(self.content)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        cards = ttk.Frame(canvas)
        window_id = canvas.create_window(0, 0, window=cards, anchor="nw")
        cards.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        for col in range(2):
            cards.columnconfigure(col, weight=1, uniform="cards")
        if not count:
            ttk.Label(cards, text="Your garage is empty.\nAdd your first car to get started.",
                      font=(FONT_FAMILY, 15), justify="center", padding=50).grid(row=0, column=0, columnspan=2)
        for index, car in enumerate(self.garage.cars):
            card = tk.Frame(cards, bg=PANEL, padx=18, pady=16, highlightbackground="#34516a", highlightthickness=1)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=8)
            picture = tk.Canvas(card, width=270, height=105, bg=PANEL, highlightthickness=0)
            picture.pack(fill="x")
            import hashlib
            key = hashlib.sha256(car["id"].encode()).hexdigest()
            portrait_path = Path(self.store.path).parent / "ai_data" / (key + ".png")
            try:
                image = tk.PhotoImage(file=str(portrait_path))
                factor = max(1, (image.width() + 269) // 270, (image.height() + 104) // 105)
                picture.portrait_image = image.subsample(factor, factor)
                picture.create_image(135, 52, image=picture.portrait_image)
            except tk.TclError:
                self.draw_side_car(picture)
            tk.Label(card, text=car["name"], bg=PANEL, fg=TEXT, font=(FONT_FAMILY, 15, "bold"),
                     wraplength=300, justify="left").pack(anchor="w", pady=(10, 6))
            total = sum(r["cost_cents"] for r in car["records"])
            tk.Label(card, text=f'{car["mileage"]:,} miles  |  {len(car["records"])} services\n'
                     f'Recorded cost: {display_money(total)}', bg=PANEL, fg=MUTED,
                     justify="left").pack(anchor="w", pady=(0, 12))
            ttk.Button(card, text="Open car >", command=lambda cid=car["id"]: self.open_car(cid)).pack(anchor="w")

    @staticmethod
    def draw_side_car(canvas):
        canvas.create_polygon(20, 70, 36, 48, 80, 43, 110, 18, 186, 18, 218, 44,
                              254, 52, 265, 75, 20, 75, fill=CAR_COLOR, outline=ACCENT, width=2)
        canvas.create_polygon(91, 43, 115, 23, 150, 23, 150, 43, fill=BG)
        canvas.create_polygon(156, 23, 182, 23, 205, 43, 156, 43, fill=BG)
        for x in (65, 220):
            canvas.create_oval(x - 17, 62, x + 17, 96, fill=BG, outline=MUTED, width=3)
            canvas.create_oval(x - 7, 72, x + 7, 86, fill=MUTED)

    def car_dialog(self, edit=False):
        car = self.current_car() if edit else None
        fields = [
            ("name", "Car name / year, make, model", car["name"] if car else "", None),
            ("mileage", "Current odometer (miles)", car["mileage"] if car else "", None),
            ("notes", "Car details / VIN / engine / notes (optional)", car["notes"] if car else "", None),
        ]

        def save(values):
            car_id = self.garage.save_car(values["name"], values["mileage"], values["notes"],
                                          car["id"] if car else None)
            self.open_car(car_id)
            self.set_status("Car saved. Add maintenance records below.")

        FormDialog(self, "Edit car" if edit else "Add car", fields, save)

    def delete_car(self):
        car = self.current_car()
        if not messagebox.askyesno("Delete car?", f'Delete {car["name"]} and all {len(car["records"])} '
                                  'maintenance records?\nThis removes them from your garage.', parent=self):
            return
        try:
            self.garage.delete_car(car["id"])
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not save", str(error), parent=self)
            return
        self.show_garage()
        self.set_status("Car deleted. The previous file version is in garage_data.json.bak.")

    # ==================================================
    # 5. SELECTED CAR — summary, diagram and history tabs
    # ==================================================
    def open_car(self, car_id, tab=0):
        self.selected_id = car_id
        self.clear_content()
        car = self.current_car()
        title = ttk.Frame(self.content)
        title.pack(fill="x", pady=(4, 8))
        ttk.Label(title, text=car["name"], style="Title.TLabel", wraplength=650).pack(side="left")
        ttk.Button(title, text="Delete car", command=self.delete_car).pack(side="right", padx=4)
        ttk.Button(title, text="Edit car", command=lambda: self.car_dialog(True)).pack(side="right", padx=4)
        total = sum(r["cost_cents"] for r in car["records"])
        last_date = max((r["date"] for r in car["records"]), default="No records")
        ttk.Label(self.content, text=f'{car["mileage"]:,} miles  |  {len(car["records"])} service records  |  '
                  f'Recorded cost: {display_money(total)}  |  Latest service: {last_date}',
                  style="Muted.TLabel").pack(anchor="w", pady=5)
        if car["notes"]:
            preview = " ".join(car["notes"].split())
            if len(preview) > 140:
                preview = preview[:140] + "... (Edit car for full notes)"
            ttk.Label(self.content, text=preview, wraplength=1050).pack(anchor="w", pady=5)
        actions = ttk.Frame(self.content)
        actions.pack(fill="x", pady=(6, 12))
        ttk.Button(actions, text="+ Add maintenance", command=self.record_dialog).pack(side="left")
        ttk.Button(actions, text="Export history to CSV", command=self.export_csv).pack(side="left", padx=8)
        ttk.Button(actions, text="AI Garage", command=self.open_ai_garage).pack(side="left", padx=8)
        self.tabs = ttk.Notebook(self.content)
        self.tabs.pack(fill="both", expand=True)
        diagram = ttk.Frame(self.tabs)
        history = ttk.Frame(self.tabs)
        self.tabs.add(diagram, text="Car diagram")
        self.tabs.add(history, text="Maintenance history")
        self.build_diagram(diagram, car)
        self.build_history(history)
        self.tabs.select(tab)

    def open_ai_garage(self):
        # One AI session at a time; closing it releases pending result handlers.
        if self.ai_window is not None and self.ai_window.winfo_exists():
            self.ai_window.close()
        from ai_ui import AIGarageWindow
        try:
            self.ai_window = AIGarageWindow(
                self, self.current_car(), Path(self.store.path).parent / "ai_data")
        except (ValueError, OSError) as error:
            messagebox.showerror("AI Garage", str(error), parent=self)

    # ==================================================
    # 6. SERVICE FORMS — add/edit without losing history
    # Old services can be logged; newer mileage advances
    # the odometer. Deleting a record never lowers it.
    # ==================================================
    def record_dialog(self, record=None, service="Oil change"):
        car = self.current_car()
        fields = [
            ("service", "Service (choose one or type your own)", record["service"] if record else service, SERVICES),
            ("date", "Date performed (YYYY-MM-DD)", record["date"] if record else date.today().isoformat(), None),
            ("mileage", "Odometer at service (miles)", record["mileage"] if record else car["mileage"], None),
            ("cost", "Total cost (USD, optional)", f'{record["cost_cents"] // 100}.{record["cost_cents"] % 100:02d}' if record else "", None),
            ("notes", "Notes / parts / oil grade / shop (optional)", record["notes"] if record else "", None),
        ]

        def save(values):
            self.garage.save_record(car["id"], values["service"], values["date"], values["mileage"],
                                    values["cost"], values["notes"], record["id"] if record else None)
            self.open_car(car["id"], tab=1)
            self.set_status("Maintenance saved to garage_data.json.")

        FormDialog(self, "Edit maintenance" if record else "Add maintenance", fields, save)

    def selected_record(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Choose a record", "Select a row in the history table first.", parent=self)
            return None
        return next(r for r in self.current_car()["records"] if r["id"] == selected[0])

    def edit_record(self):
        record = self.selected_record()
        if record:
            self.record_dialog(record)

    def delete_record(self):
        record = self.selected_record()
        if not record or not messagebox.askyesno("Delete record?", f'Delete {record["service"]} '
                                                 f'from {record["date"]}?', parent=self):
            return
        try:
            self.garage.delete_record(self.selected_id, record["id"])
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not save", str(error), parent=self)
            return
        self.open_car(self.selected_id, tab=1)
        self.set_status("Record deleted. Current odometer was kept unchanged.")

    # ==================================================
    # 7. HISTORY TABLE — search, filter, numeric sorting
    # IDs connect rows to records, even with duplicates.
    # ==================================================
    def build_history(self, parent):
        toolbar = ttk.Frame(parent, padding=(4, 10))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Search:").pack(side="left", padx=(0, 5))
        self.search = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.search, width=22).pack(side="left")
        self.filter_service = tk.StringVar(value="All services")
        options = ["All services"] + sorted({r["service"] for r in self.current_car()["records"]} | set(SERVICES))
        ttk.Combobox(toolbar, textvariable=self.filter_service, values=options,
                     state="readonly", width=21).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Edit selected", command=self.edit_record).pack(side="right", padx=4)
        ttk.Button(toolbar, text="Delete selected", command=self.delete_record).pack(side="right", padx=4)
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True)
        columns = ("date", "service", "mileage", "cost_cents", "notes")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for name, label, width in zip(columns, ("Date", "Service", "Mileage", "Cost (USD)", "Notes"),
                                       (120, 180, 110, 100, 360)):
            self.tree.heading(name, text=label, command=lambda key=name: self.sort_history(key))
            self.tree.column(name, width=width, minwidth=90, anchor="w")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.history_summary = ttk.Label(parent, padding=8, style="Muted.TLabel")
        self.history_summary.pack(anchor="w")
        self.tree.bind("<Double-1>", lambda event: self.edit_record() if self.tree.identify_region(event.x, event.y) == "cell" else None)
        self.search.trace_add("write", lambda *args: self.refresh_history())
        self.filter_service.trace_add("write", lambda *args: self.refresh_history())
        self.refresh_history()

    def sort_history(self, column):
        self.sort_descending = not self.sort_descending if self.sort_column == column else False
        self.sort_column = column
        self.refresh_history()

    def refresh_history(self):
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().casefold()
        service = self.filter_service.get()
        records = [r for r in self.current_car()["records"]
                   if (service == "All services" or r["service"] == service)
                   and query in f'{r["service"]} {r["date"]} {r["mileage"]} {r["notes"]}'.casefold()]
        records.sort(key=lambda r: r[self.sort_column].casefold() if isinstance(r[self.sort_column], str)
                     else r[self.sort_column], reverse=self.sort_descending)
        for record in records:
            self.tree.insert("", "end", iid=record["id"], values=(record["date"], record["service"],
                             f'{record["mileage"]:,}', display_money(record["cost_cents"]),
                             record["notes"].replace("\n", " | ")))
        self.history_summary.config(text=f'{len(records)} records shown | '
                                    f'{display_money(sum(r["cost_cents"] for r in records))} shown total'
                                    ' | Double-click a row to view or edit full notes')

    def export_csv(self):
        records = self.current_car()["records"]
        if not records:
            messagebox.showinfo("No records", "Add a maintenance record before exporting.", parent=self)
            return
        destination = filedialog.asksaveasfilename(parent=self, title="Export full car history",
                                                  initialfile="maintenance_history.csv", defaultextension=".csv",
                                                  filetypes=[("CSV spreadsheet", "*.csv")])
        if not destination:
            return
        protected = (self.store.path, self.store.backup_path, self.store.path.parent / "car_data.json")
        if Path(destination).resolve() in {path.resolve() for path in protected}:
            messagebox.showerror("Choose a CSV file", "Export to a separate .csv file, not your saved garage data.", parent=self)
            return
        try:
            with open(destination, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Car", "Date", "Service", "Mileage", "Cost (USD)", "Notes"])
                for r in sorted(records, key=lambda r: (r["date"], r["mileage"]), reverse=True):
                    # Prefix spreadsheet formulas in free-text cells to keep exports as data.
                    def text_cell(value):
                        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
                    writer.writerow([text_cell(self.current_car()["name"]), r["date"], text_cell(r["service"]),
                                     r["mileage"], f'{r["cost_cents"] // 100}.{r["cost_cents"] % 100:02d}',
                                     text_cell(r["notes"])])
        except OSError as error:
            messagebox.showerror("Export failed", str(error), parent=self)
        else:
            self.set_status("Exported the full history for this car to CSV.")

    # ==================================================
    # 8. CAR DIAGRAM — drawn with Canvas, no image files
    # Each service panel points to a representative part.
    # Click a panel to log that type of maintenance.
    # ==================================================
    def build_diagram(self, parent, car):
        ttk.Label(parent, text="Latest recorded services | Click a panel to add an entry | Front of car at top",
                  style="Muted.TLabel", padding=10).pack(anchor="w")
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0, scrollregion=(0, 0, 1060, 680))
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=canvas.xview)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        xscroll.grid(row=1, column=0, sticky="ew")
        yscroll.grid(row=0, column=1, sticky="ns")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        # Top-down body, wheels, windows, engine, battery and seats.
        canvas.create_text(530, 22, text="FRONT", fill=MUTED, font=(FONT_FAMILY, 10, "bold"))
        for x in (416, 610):
            for y in (145, 455):
                canvas.create_rectangle(x, y, x + 34, y + 85, fill="#080c13", outline=MUTED, width=2)
        canvas.create_polygon(470, 50, 590, 50, 614, 88, 622, 550, 595, 600,
                              465, 600, 438, 550, 446, 88, smooth=True,
                              fill=CAR_COLOR, outline=ACCENT, width=3)
        canvas.create_rectangle(465, 95, 595, 210, fill=PANEL, outline=MUTED)
        canvas.create_rectangle(480, 118, 558, 182, fill="#556879", outline=TEXT, width=2)
        canvas.create_text(519, 150, text="ENGINE", fill=TEXT, font=(FONT_FAMILY, 9, "bold"))
        canvas.create_rectangle(566, 110, 589, 145, fill=ACCENT)
        canvas.create_polygon(462, 235, 598, 235, 586, 290, 474, 290, fill=BG, outline=MUTED)
        for x in (478, 540):
            canvas.create_rectangle(x, 315, x + 43, 380, fill=PANEL, outline=MUTED)
        canvas.create_rectangle(474, 410, 586, 460, fill=PANEL, outline=MUTED)
        canvas.create_polygon(474, 485, 586, 485, 598, 530, 462, 530, fill=BG, outline=MUTED)
        canvas.create_line(450, 560, 610, 560, fill=ACCENT, width=3)
        canvas.create_text(530, 635, text="Illustration | Part locations vary by vehicle\n"
                           "Recorded history only; check your owner's manual for service intervals.",
                           fill=MUTED, justify="center", font=(FONT_FAMILY, 9))
        panels = [
            ("Oil change", 16, 48, 500, 170),
            ("Spark plugs", 16, 194, 510, 130),
            ("Tire rotation", 16, 340, 430, 490),
            ("Tire replacement", 16, 486, 430, 205),
            ("Battery", 744, 48, 578, 125),
            ("Cabin air filter", 744, 194, 580, 265),
            ("Brakes", 744, 340, 620, 200),
            ("Coolant", 744, 486, 580, 195),
        ]
        for index, (service, x, y, target_x, target_y) in enumerate(panels):
            tag = f"panel{index}"
            start_x = x + 298 if x < 500 else x
            canvas.create_line(start_x, y + 58, target_x, target_y, arrow=tk.LAST,
                               fill=ACCENT, width=2)
            canvas.create_rectangle(x, y, x + 298, y + 124, fill=PANEL, outline="#34516a", tags=tag)
            canvas.create_text(x + 14, y + 20, text=service, fill=ACCENT, anchor="w",
                               font=(FONT_FAMILY, 12, "bold"), tags=tag)
            last = latest_record(car, service)
            details = (f'{last["date"]}  |  {last["mileage"]:,} miles\n'
                       f'{max(0, car["mileage"] - last["mileage"]):,} miles since  |  '
                       f'{display_money(last["cost_cents"])}') if last else "No service recorded yet"
            canvas.create_text(x + 14, y + 62, text=details, fill=TEXT, anchor="w", width=270,
                               font=(FONT_FAMILY, 10), tags=tag)
            canvas.create_text(x + 14, y + 105, text="+ Log service", fill=MUTED, anchor="w", tags=tag)
            canvas.tag_bind(tag, "<Button-1>", lambda event, name=service: self.record_dialog(service=name))
            canvas.tag_bind(tag, "<Enter>", lambda event: canvas.config(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda event: canvas.config(cursor=""))

        # Compress vertical spacing on shorter windows while keeping text readable.
        # For very small windows, scrollbars keep every panel reachable.
        previous_scale = 1.0

        def fit_height(event):
            nonlocal previous_scale
            scale = min(1.0, max(0.60, (event.height - 18) / 680))
            canvas.scale("all", 0, 0, 1, scale / previous_scale)
            canvas.configure(scrollregion=(0, 0, 1060, 680 * scale))
            previous_scale = scale

        canvas.bind("<Configure>", fit_height)
        canvas.bind("<Button-4>", lambda event: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda event: canvas.yview_scroll(1, "units"))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"))


# ==================================================
# 9. ENTRY POINT — importing this file won't open a GUI
# ==================================================
if __name__ == "__main__":
    try:
        app = MaintenanceApp()
    except RuntimeError:
        pass  # The startup dialog already explains why the file cannot be loaded.
    else:
        app.mainloop()
