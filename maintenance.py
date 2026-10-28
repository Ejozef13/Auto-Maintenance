"""Data rules and JSON storage. This file does not create any windows."""

# ==================================================
# 1. IMPORTS AND CUSTOMIZABLE SERVICE NAMES
# ==================================================
import copy
import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

SERVICES = (
    "Oil change", "Spark plugs", "Cabin air filter", "Tire rotation",
    "Tire replacement", "Brakes", "Battery", "Coolant", "Transmission fluid",
)


def whole_number(text, label="Mileage"):
    """Convert form text into a nonnegative integer, or explain the error."""
    try:
        value = int(str(text).strip())
    except ValueError:
        raise ValueError(f"{label} must be a whole number, like 85000.") from None
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def money_cents(text):
    """Store money as integer cents to avoid floating-point rounding errors."""
    try:
        amount = Decimal(str(text).strip() or "0")
        if not amount.is_finite() or amount < 0 or amount > Decimal("999999999"):
            raise ValueError("Cost must be between 0 and 999999999.")
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Cost can have at most two decimal places.")
        return int(amount * 100)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Enter a nonnegative cost with at most two decimals, like 49.95.") from error


def display_money(cents):
    return f"${cents // 100:,}.{cents % 100:02d}"


def make_record(service, performed_on, mileage, cost, notes=""):
    """Validate an entry before it can reach the saved data."""
    service = service.strip()
    if not service:
        raise ValueError("Choose or type a service name.")
    try:
        parsed_date = date.fromisoformat(performed_on)
        if parsed_date.isoformat() != performed_on:
            raise ValueError
    except ValueError:
        raise ValueError("Use a real date in YYYY-MM-DD format, like 2026-10-28.") from None
    if parsed_date > date.today():
        raise ValueError("A completed service cannot have a future date.")
    return {
        "id": uuid4().hex,
        "service": service,
        "date": performed_on,
        "mileage": whole_number(mileage),
        "cost_cents": money_cents(cost),
        "notes": notes.strip(),
    }


def latest_record(car, service):
    """Latest means newest date, then highest mileage on that date."""
    matching = [r for r in car["records"] if r["service"].casefold() == service.casefold()]
    return max(matching, key=lambda r: (r["date"], r["mileage"]), default=None)


# ==================================================
# 2. VALIDATE FILE CONTENTS BEFORE USING THEM
# A bad file must not silently become an empty garage.
# ==================================================
def validate_data(data):
    def require(condition):
        if not condition:
            raise ValueError("The garage file has an unsupported or invalid structure.")

    def nonnegative_int(value):
        return type(value) is int and value >= 0

    require(isinstance(data, dict) and type(data.get("version")) is int and data["version"] == 1)
    require(isinstance(data.get("cars"), list))
    identifiers = set()
    for car in data["cars"]:
        require(isinstance(car, dict))
        require(isinstance(car.get("id"), str) and bool(car["id"]))
        require(car["id"] not in identifiers)
        identifiers.add(car["id"])
        require(isinstance(car.get("name"), str) and bool(car["name"].strip()))
        require(nonnegative_int(car.get("mileage")))
        require(isinstance(car.get("notes"), str))
        require(isinstance(car.get("records"), list))
        record_ids = set()
        for record in car["records"]:
            require(isinstance(record, dict))
            require(isinstance(record.get("id"), str) and bool(record["id"]))
            require(record["id"] not in record_ids)
            record_ids.add(record["id"])
            require(isinstance(record.get("service"), str) and bool(record["service"].strip()))
            require(isinstance(record.get("date"), str))
            try:
                require(date.fromisoformat(record["date"]).isoformat() == record["date"])
            except ValueError:
                raise ValueError("The garage file contains an invalid date.") from None
            require(nonnegative_int(record.get("mileage")))
            require(record["mileage"] <= car["mileage"])
            require(nonnegative_int(record.get("cost_cents")))
            require(isinstance(record.get("notes"), str))
    return data


# ==================================================
# 3. LOAD AND SAVE
# Writes use a temporary file + atomic replacement so a
# failed write does not truncate the existing garage.
# The previous good version is retained as .json.bak.
# ==================================================
class GarageStore:
    def __init__(self, path):
        self.path = Path(path)
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")

    def load(self):
        try:
            with self.path.open(encoding="utf-8") as file:
                return validate_data(json.load(file))
        except FileNotFoundError:
            return {"version": 1, "cars": []}

    @staticmethod
    def _atomic_write(path, contents):
        # An exclusive temporary name also works when two processes attempt a write.
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as file:
                file.write(contents)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, data):
        validate_data(data)
        contents = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if self.path.exists():
            previous = self.path.read_text(encoding="utf-8")
            validate_data(json.loads(previous))
            self._atomic_write(self.backup_path, previous)
        self._atomic_write(self.path, contents)

    def import_legacy(self, legacy_path):
        """Copy the original single car into a new garage; leave the old file intact."""
        legacy_path = Path(legacy_path)
        if self.path.exists() or not legacy_path.exists():
            return False
        with legacy_path.open(encoding="utf-8") as file:
            old = json.load(file)
        if not isinstance(old, dict) or not isinstance(old.get("name"), str) or not old["name"].strip():
            raise ValueError("The old car_data.json does not contain a valid car name.")
        if type(old.get("mileage")) is not int or old["mileage"] < 0:
            raise ValueError("The old car_data.json does not contain valid mileage.")
        self.save({"version": 1, "cars": [{
            "id": uuid4().hex, "name": old["name"].strip(),
            "mileage": old["mileage"], "notes": "", "records": [],
        }]})
        return True


# ==================================================
# 4. DATA MODEL
# Work on a copy; only update memory after saving works.
# The UI uses IDs instead of car names, so duplicate
# names never mix up two cars or their records.
# ==================================================
class Garage:
    def __init__(self, store):
        self.store = store
        self.data = store.load()

    @property
    def cars(self):
        return self.data["cars"]

    def car(self, car_id):
        return next(car for car in self.cars if car["id"] == car_id)

    def _commit(self, candidate):
        self.store.save(candidate)
        self.data = candidate

    def save_car(self, name, mileage, notes="", car_id=None):
        name = name.strip()
        if not name:
            raise ValueError("Enter a car name, such as 2015 Honda Civic.")
        mileage = whole_number(mileage)
        candidate = copy.deepcopy(self.data)
        if car_id is None:
            car_id = uuid4().hex
            candidate["cars"].append({"id": car_id, "name": name, "mileage": mileage,
                                      "notes": notes.strip(), "records": []})
        else:
            car = next(c for c in candidate["cars"] if c["id"] == car_id)
            highest = max((r["mileage"] for r in car["records"]), default=0)
            if mileage < highest:
                raise ValueError(f"Current mileage must be at least {highest:,}, the highest recorded service mileage.")
            car.update(name=name, mileage=mileage, notes=notes.strip())
        self._commit(candidate)
        return car_id

    def delete_car(self, car_id):
        candidate = copy.deepcopy(self.data)
        candidate["cars"] = [c for c in candidate["cars"] if c["id"] != car_id]
        self._commit(candidate)

    def save_record(self, car_id, service, performed_on, mileage, cost, notes="", record_id=None):
        record = make_record(service, performed_on, mileage, cost, notes)
        candidate = copy.deepcopy(self.data)
        car = next(c for c in candidate["cars"] if c["id"] == car_id)
        if record_id is None:
            car["records"].append(record)
        else:
            index = next(i for i, r in enumerate(car["records"]) if r["id"] == record_id)
            record["id"] = record_id
            car["records"][index] = record
        # A newer service mileage also updates the car's current odometer.
        car["mileage"] = max(car["mileage"], record["mileage"])
        self._commit(candidate)
        return record["id"]

    def delete_record(self, car_id, record_id):
        candidate = copy.deepcopy(self.data)
        car = next(c for c in candidate["cars"] if c["id"] == car_id)
        car["records"] = [r for r in car["records"] if r["id"] != record_id]
        self._commit(candidate)
