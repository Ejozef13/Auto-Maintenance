# Auto-Maintenance

A local desktop garage and maintenance log for car enthusiasts. Built with Python's
Tkinter library, with commented sections to make the project easier to learn and customize.
No account, subscription, web server, or third-party Python package is required.

## Run on CachyOS / Arch Linux

Python and Tkinter are already working if `python3 -m tkinter` opens a window.
If you need to install them, update the system and install the packages together:

```bash
sudo pacman -Syu python tk
```

Keep `main.py` and `maintenance.py` in the same folder, then run:

```bash
cd ~/Projects/Auto-Maintenance
python3 main.py
```

Requires Python 3.10 or newer. Use one running copy of the app per data file.

## What you can do

- Add multiple cars to a garage of selectable car cards.
- Edit each car's name, odometer, and details such as VIN, engine, or personal notes.
- Record oil changes, spark plugs, cabin filters, tire rotations, tire replacements,
  brakes, battery, coolant, and transmission fluid. Type your own service name too.
- Record the date, odometer, total cost, and notes for each service.
- Switch between a top-down car diagram and a complete maintenance history table.
- See the latest date/mileage, miles since service, and recorded cost on diagram panels.
  Click a panel to log another service of that type.
- Search history, filter by service, sort by clicking column headings, and edit or delete records.
  Double-click a row to read full notes or edit it.
- See current mileage, number of records, latest service date, and total recorded spending.
- Export a car's complete history as CSV to open in Excel or LibreOffice Calc.
- Delete a car and its records after confirming.

The diagram shows eight common services; transmission fluid and custom services
appear in the history table. Part locations are illustrative and vary by car.
This version records maintenance, rather than calculating manufacturer service schedules.
Mileage is in miles; costs are in USD. Blank costs are stored as zero.
On smaller displays, use the scrollbars to reach the full diagram, table, and garage.

## Saving and your previous version

Every successful Save or confirmed deletion updates `garage_data.json` beside the
program. Closing the app preserves saved records. Canceling a form leaves them unchanged.
New car/service forms close after saving, so the next form starts fresh.
A service mileage above the car's current odometer raises the odometer automatically.
Historical services with lower mileage can be entered too. Deleting or correcting a
record does not reduce the current odometer; use Edit car if it needs correction.

On first launch, if `garage_data.json` does not exist but the original `car_data.json`
does, the app imports that single car. It leaves the original file untouched. After
importing, all changes use `garage_data.json`, so the legacy file is no longer current.
Keep your original `car_data.json` in the project folder when upgrading to import it.

Saves write a temporary file before replacing the main file. The preceding good
version is kept in `garage_data.json.bak`. This is one previous version, not a complete
backup archive. Copy your data somewhere separate occasionally. These files contain
plain text, so store them on a computer you trust.

If a data file is invalid, the app displays an error and stops rather than overwriting it.
To restore a backup: close the app, copy the damaged file somewhere safe, then copy
`garage_data.json.bak` to `garage_data.json` before reopening. JSON files can be inspected
in a text editor, but editing them manually requires preserving their structure.

The supplied `.gitignore` keeps personal JSON files, backups, Python cache files,
and exported CSV files out of new Git commits. Do not commit your personal garage file.

## Find your way around the code

| File / section | What it controls |
| --- | --- |
| `main.py`, section 1 | Colors, font, and data-file location |
| `main.py`, section 2 | Reusable popup forms |
| `main.py`, sections 3–4 | Main window and garage cards |
| `main.py`, sections 5–6 | Selected car and maintenance actions |
| `main.py`, section 7 | History table, search, sorting, and CSV export |
| `main.py`, section 8 | Car drawing, arrows, service panels |
| `maintenance.py`, section 1 | Service names, number/date/cost validation |
| `maintenance.py`, sections 2–3 | JSON format checks, loading, backups, saving |
| `maintenance.py`, section 4 | Adding, editing, and deleting data |
| `tests/` | Storage and real desktop interaction tests |

`MaintenanceApp` is a class: it groups the window's data and functions, like a Java
class. `self` refers to the particular app object, similar to Java's `this`.
`Garage` manages data independently of the interface. Widgets call its methods,
then redraw using the saved data. Each car and record has its own unique ID, so
matching names never mix up their histories.

Money is stored as integer cents instead of floating-point dollars. For example,
`4995` means `$49.95`. Records belong to the car's `records` list in the JSON file.
The file has a format version so future changes can deliberately migrate old data.

## Verify the app

```bash
python3 -m unittest discover -s tests -v
```

Storage tests do not need a display. GUI tests need a running desktop (`DISPLAY`
on Linux); otherwise they are explicitly skipped. They use temporary data files,
not your real garage. The full suite currently contains 18 tests.

Manual check: add two cars, log different services, switch between them, close and
reopen the app, then check that each car retained only its own records. Try an invalid
date or negative mileage to see validation. Export a CSV and open it in a spreadsheet.

## Save this upgrade with Git

After copying the new files into your local project and testing them:

```bash
git status
git add main.py maintenance.py README.md .gitignore tests/
git diff --cached
git commit -m "Build multi-car garage and maintenance history app"
git push origin main
```

`git diff --cached` shows the staged changes that the commit will include.
Press `q` to exit its viewer if needed. Use your current branch name if it isn't `main`.
