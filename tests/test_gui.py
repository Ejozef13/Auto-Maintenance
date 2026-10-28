"""Real Tk interaction tests. Requires a desktop session (DISPLAY on Linux)."""
import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import FormDialog, MaintenanceApp


@unittest.skipUnless(os.environ.get("DISPLAY"), "GUI tests need a display")
class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "garage_data.json"
        self.app = MaintenanceApp(self.path)
        self.app.update()
        self.addCleanup(self.close_app)

    def close_app(self):
        if self.app is not None:
            self.app.destroy()

    def dialog(self):
        return next(w for w in self.app.winfo_children() if isinstance(w, FormDialog))

    def fill(self, dialog, values):
        for name, value in values.items():
            widget = dialog.inputs[name]
            if name == "notes":
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
            else:
                widget.delete(0, "end")
                widget.insert(0, str(value))

    def add_car(self):
        self.app.car_dialog()
        form = self.dialog()
        self.fill(form, {"name": "2015 Honda Civic", "mileage": "85000", "notes": "Daily driver"})
        form.submit()
        self.app.update()
        return self.app.selected_id

    def add_record(self, service="Oil change", mileage="85000"):
        self.app.record_dialog(service=service)
        form = self.dialog()
        self.fill(form, {"date": "2025-10-01", "mileage": mileage, "cost": "49.95", "notes": "Synthetic"})
        form.submit()
        self.app.update()

    def test_complete_desktop_workflow_and_restart(self):
        car_id = self.add_car()
        self.add_record()
        self.add_record("Tire rotation", "86000")
        self.assertEqual(len(self.app.tree.get_children()), 2)
        self.assertEqual(self.app.current_car()["mileage"], 86000)
        self.app.search.set("synthetic")
        self.assertEqual(len(self.app.tree.get_children()), 2)
        self.app.filter_service.set("Tire rotation")
        self.assertEqual(len(self.app.tree.get_children()), 1)
        record_id = self.app.tree.get_children()[0]
        self.app.tree.selection_set(record_id)
        self.app.edit_record()
        self.fill(self.dialog(), {"notes": "Rotated front to rear", "cost": "0"})
        self.dialog().submit()
        self.app.update()
        edited = next(r for r in self.app.current_car()["records"] if r["id"] == record_id)
        self.assertEqual(edited["cost_cents"], 0)
        self.app.tree.selection_set(record_id)
        with patch("main.messagebox.askyesno", return_value=True):
            self.app.delete_record()
        self.assertEqual(len(self.app.tree.get_children()), 1)
        self.app.destroy()
        self.app = MaintenanceApp(self.path)
        self.app.update()
        self.app.open_car(car_id)
        self.assertEqual(len(self.app.current_car()["records"]), 1)
        self.assertEqual(self.app.current_car()["mileage"], 86000)
        with patch("main.messagebox.askyesno", return_value=False):
            self.app.delete_car()
        self.assertEqual(len(self.app.garage.cars), 1)
        with patch("main.messagebox.askyesno", return_value=True):
            self.app.delete_car()
        self.assertEqual(self.app.garage.cars, [])

    def test_invalid_form_stays_open_without_saving(self):
        self.app.car_dialog()
        form = self.dialog()
        self.fill(form, {"name": "Civic", "mileage": "-1"})
        form.submit()
        self.assertTrue(form.winfo_exists())
        self.assertIn("negative", form.error.cget("text"))
        self.assertEqual(self.app.garage.cars, [])
        self.fill(form, {"mileage": "85000"})
        form.submit()
        self.app.update()
        self.app.record_dialog()
        form = self.dialog()
        self.fill(form, {"date": "2025-02-30"})
        form.submit()
        self.assertIn("real date", form.error.cget("text"))
        self.assertEqual(self.app.current_car()["records"], [])

    def test_csv_export_and_numeric_sort(self):
        self.add_car()
        self.add_record(mileage="900")
        self.add_record("Brakes", "10000")
        self.app.sort_history("mileage")
        rows = self.app.tree.get_children()
        self.assertEqual(self.app.tree.item(rows[0], "values")[2], "900")
        destination = Path(self.folder.name) / "history.csv"
        with patch("main.filedialog.asksaveasfilename", return_value=str(destination)):
            self.app.export_csv()
        with destination.open(newline="") as file:
            rows = list(csv.reader(file))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], ["Car", "Date", "Service", "Mileage", "Cost (USD)", "Notes"])
        self.assertEqual(rows[1][4], "49.95")

    def test_diagram_panel_opens_correct_service_form(self):
        self.add_car()
        self.app.tabs.select(0)
        self.app.update()
        diagram_frame = self.app.tabs.nametowidget(self.app.tabs.tabs()[0])
        import tkinter as tk

        def canvases(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Canvas):
                    yield child
                yield from canvases(child)

        canvas = next(canvases(diagram_frame))
        canvas.event_generate("<Motion>", x=70, y=70)
        canvas.event_generate("<Button-1>", x=70, y=70)
        self.app.update()
        self.assertEqual(self.dialog().inputs["service"].get(), "Oil change")


if __name__ == "__main__":
    unittest.main()
