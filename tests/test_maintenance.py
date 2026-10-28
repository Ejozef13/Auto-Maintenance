"""Data tests run without a display: python3 -m unittest discover -s tests -v"""
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from maintenance import Garage, GarageStore, latest_record, make_record, money_cents


class GarageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "garage_data.json"
        self.store = GarageStore(self.path)
        self.garage = Garage(self.store)

    def car(self, name="Civic", mileage=85000):
        return self.garage.save_car(name, mileage, "2.0L engine")

    def record(self, car_id, mileage=85000, service="Oil change", when="2025-10-01"):
        return self.garage.save_record(car_id, service, when, mileage, "49.95", "Full synthetic")

    def test_multiple_cars_and_records_survive_reload(self):
        first, second = self.car(), self.car("Miata", 100000)
        self.record(first)
        self.record(second, service="Spark plugs")
        loaded = Garage(self.store)
        self.assertEqual(len(loaded.cars), 2)
        self.assertEqual(loaded.car(first)["records"][0]["service"], "Oil change")
        self.assertEqual(loaded.car(second)["records"][0]["service"], "Spark plugs")
        self.assertEqual(loaded.car(first)["records"][0]["cost_cents"], 4995)

    def test_same_names_have_independent_ids(self):
        first, second = self.car(), self.car()
        self.record(first)
        self.assertNotEqual(first, second)
        self.assertEqual(self.garage.car(second)["records"], [])

    def test_edit_and_delete_record_keep_current_odometer(self):
        car_id = self.car()
        record_id = self.record(car_id, 90000)
        self.assertEqual(self.garage.car(car_id)["mileage"], 90000)
        self.garage.save_record(car_id, "Spark plugs", "2025-10-02", 88000, "100", "NGK", record_id)
        self.assertEqual(len(self.garage.car(car_id)["records"]), 1)
        self.assertEqual(self.garage.car(car_id)["records"][0]["id"], record_id)
        self.garage.delete_record(car_id, record_id)
        self.assertEqual(self.garage.car(car_id)["records"], [])
        self.assertEqual(self.garage.car(car_id)["mileage"], 90000)

    def test_car_edit_cannot_undercut_record_mileage(self):
        car_id = self.car()
        self.record(car_id)
        with self.assertRaises(ValueError):
            self.garage.save_car("Civic", 100, "", car_id)
        self.garage.save_car("Daily Civic", 90000, "Updated", car_id)
        self.assertEqual(self.garage.car(car_id)["name"], "Daily Civic")

    def test_delete_car_does_not_delete_other_car(self):
        first, second = self.car(), self.car("Miata")
        self.record(first)
        self.record(second)
        self.garage.delete_car(first)
        loaded = Garage(self.store)
        self.assertEqual([c["id"] for c in loaded.cars], [second])
        self.assertEqual(len(loaded.car(second)["records"]), 1)

    def test_latest_is_by_date_then_mileage_not_insertion_order(self):
        car_id = self.car()
        self.record(car_id, 83000, when="2025-10-02")
        self.record(car_id, 82000, when="2025-10-01")
        self.record(car_id, 84000, service="oil CHANGE", when="2025-10-02")
        self.assertEqual(latest_record(self.garage.car(car_id), "Oil change")["mileage"], 84000)
        self.assertIsNone(latest_record(self.garage.car(car_id), "Brakes"))

    def test_legacy_import_is_non_destructive_and_runs_once(self):
        legacy = self.path.parent / "car_data.json"
        original = '{"name": "Old Civic", "mileage": 42000}'
        legacy.write_text(original)
        self.assertTrue(self.store.import_legacy(legacy))
        self.assertEqual(Garage(self.store).cars[0]["name"], "Old Civic")
        self.assertEqual(legacy.read_text(), original)
        self.assertFalse(self.store.import_legacy(legacy))
        self.assertEqual(len(Garage(self.store).cars), 1)

    def test_backup_keeps_previous_good_version(self):
        self.car()
        first_version = self.path.read_text()
        self.car("Miata")
        self.assertEqual(self.store.backup_path.read_text(), first_version)
        self.assertEqual(len(json.loads(self.path.read_text())["cars"]), 2)

    def test_failed_replace_preserves_file_and_memory(self):
        self.car()
        original = self.path.read_text()
        with patch("maintenance.os.replace", side_effect=OSError("Disk unavailable")):
            with self.assertRaises(OSError):
                self.car("Miata")
        self.assertEqual(self.path.read_text(), original)
        self.assertEqual(len(self.garage.cars), 1)
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_failed_final_replace_preserves_original_after_backup(self):
        self.car()
        original = self.path.read_text()
        import os
        real_replace = os.replace

        def fail_primary(source, destination):
            if destination == self.path:
                raise OSError("Disk unavailable")
            return real_replace(source, destination)

        with patch("maintenance.os.replace", side_effect=fail_primary):
            with self.assertRaises(OSError):
                self.car("Miata")
        self.assertEqual(self.path.read_text(), original)
        self.assertEqual(self.store.backup_path.read_text(), original)
        self.assertEqual(len(self.garage.cars), 1)

    def test_corrupt_file_is_not_overwritten(self):
        self.path.write_text("broken JSON")
        with self.assertRaises(ValueError):
            Garage(self.store)
        with self.assertRaises(ValueError):
            self.store.save({"version": 1, "cars": []})
        self.assertEqual(self.path.read_text(), "broken JSON")

    def test_invalid_structure_is_rejected(self):
        self.path.write_text('{"version": 1, "cars": [{"name": "Oops"}]}')
        with self.assertRaises(ValueError):
            Garage(self.store)

    def test_invalid_form_values(self):
        for service, when, mileage, cost in [
            ("", "2025-10-01", "100", "10"),
            ("Oil change", "2025-02-30", "100", "10"),
            ("Oil change", "20251001", "100", "10"),
            ("Oil change", (date.today() + timedelta(days=1)).isoformat(), "100", "10"),
            ("Oil change", "2025-10-01", "-1", "10"),
            ("Oil change", "2025-10-01", "1.5", "10"),
            ("Oil change", "2025-10-01", "abc", "10"),
            ("Oil change", "2025-10-01", "100", "-1"),
            ("Oil change", "2025-10-01", "100", "NaN"),
            ("Oil change", "2025-10-01", "100", "Infinity"),
            ("Oil change", "2025-10-01", "100", "0.001"),
        ]:
            with self.subTest(service=service, when=when, mileage=mileage, cost=cost):
                with self.assertRaises(ValueError):
                    make_record(service, when, mileage, cost)

    def test_cost_and_custom_service(self):
        self.assertEqual(money_cents(""), 0)
        self.assertEqual(money_cents("0.29"), 29)
        car_id = self.car()
        self.record(car_id, service="Differential fluid")
        self.assertIsNotNone(latest_record(self.garage.car(car_id), "Differential fluid"))


if __name__ == "__main__":
    unittest.main()
