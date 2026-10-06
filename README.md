# PharmaPro

**Offline pharmacy management for independent pharmacies.** PharmaPro handles the medicine catalogue, batches and expiry, stock receiving, point of sale with receipts, and profit reporting. It runs on one computer and needs no internet connection.

- Runs completely offline. There are no accounts, cloud, telemetry or network calls.
- Every batch keeps its own purchase cost, selling price and expiry date.
- Sales draw stock **First-Expiry-First-Out (FEFO)**. Expired stock can never be sold.
- Profit comes from the **actual cost of the batch sold**, so it stays correct for past sales even after prices change.
- Every stock entry and sale is one database transaction: it either saves completely or not at all.

---

## Features

| Area | What it does |
|---|---|
| **Dashboard** | Stock value, today's and this month's sales and profit, low-stock / expiring / expired counts, a 14-day sales chart, a "needs attention" list and recent sales |
| **Medicines** | Add, edit, deactivate and remove medicines. Search instantly by code, name, generic name or manufacturer. Filter by category or status. See stock, price, nearest expiry and batches |
| **Add Stock** | Enter a whole supplier invoice with many medicines at once (batch, expiry, quantity, purchase and selling price). Warns when a price is below cost. Saves atomically |
| **Inventory** | Every batch with quantity, cost, price, expiry, days left, supplier, value and status. Filters: All, Low Stock, Out of Stock, Expiring Soon, Expired |
| **Sales / POS** | USB barcode scanner or code/name entry. Scanning the same item again raises its quantity. FEFO batch selection with an optional manual batch choice. Discount, cash received and change. Hold and resume sales, sales history |
| **Receipts** | Unique numbers (`RX-YYYYMMDD-NNNN`), print preview, physical printing (thermal 80 mm / 58 mm or A4) and PDF export. Reprinting asks for confirmation, so receipts aren't printed twice by accident |
| **Purchases** | Supplier invoices with the per-batch cost of every line |
| **Expenses** | Rent, electricity, salaries, transportation, maintenance and other. Used for net profit |
| **Reports** | Sales, Purchases, Stock, Profit, Expenses, Expiry, Low Stock and Top Selling. Date filters, search and sorting, with PDF and CSV export |
| **Analytics** | Presets (Today … This Year, Custom). Revenue, COGS, gross and net profit, number of sales, average sale. Charts: sales and profit over time, revenue vs cost, top sellers, sales by category, low stock |
| **Backup & Restore** | One-click backup, backup to USB, automatic daily backup and a list of backups. Restore always asks first and keeps a safety copy |
| **Settings** | Pharmacy details, receipt footer, paper size, printer, low-stock threshold, expiry warning days and currency |

### Business rules enforced

1. Stock never goes negative. The services check it, and a database `CHECK` constraint enforces it too.
2. Expired batches cannot be sold. A batch counts as expired **on and after** its expiry date.
3. Every sale has a timestamp and a unique receipt number.
4. Every purchase keeps its actual purchase price per batch.
5. Profit = selling price × qty − *batch* cost × qty, frozen on each sale line.
6. Sales and stock entries are fully transactional, with rollback on any error.
7. Removing a medicine that has history only *deactivates* it.
8. Changing prices later never changes past sales or past profit.

---

## Architecture

```
PharmaPro/
├── main.py                     # entry point (Qt app, logging, error handler)
├── PharmaPro-onefile.spec      # PyInstaller: single-file exe (Windows / Linux)
├── PharmaPro.spec              # PyInstaller: folder build
├── .github/workflows/build.yml # CI: tests + builds both executables
├── requirements.txt
├── app/
│   ├── config.py               # paths (data/, backups/, logs/…) and logging
│   ├── context.py              # wires database + services together
│   ├── models/                 # SQLAlchemy ORM models (one file per table)
│   ├── database/
│   │   ├── database.py         # engine, transactional sessions, SQLite pragmas
│   │   └── repositories/       # query helpers (parameterised SQL only)
│   ├── services/               # business logic – no UI code
│   │   ├── medicine_service.py   inventory_service.py   purchase_service.py
│   │   ├── sales_service.py      (FEFO, stock deduction, receipt numbers)
│   │   ├── profit_service.py     expense_service.py     reporting_service.py
│   │   ├── receipt_service.py    backup_service.py      settings_service.py
│   │   ├── sample_data.py        errors.py (friendly error types)
│   ├── analytics/              # time series, top sellers, category totals (SQL + pandas)
│   ├── printing/               # Qt print preview / printer output
│   ├── ui/                     # PySide6 screens, dialogs, theme, icons, charts
│   ├── utils/                  # validators, formatting, constants
│   └── resources/icons/        # application icon (svg/png/ico)
├── tests/                      # pytest: services, rules, UI smoke tests, offline test
├── packaging/                  # build scripts + icon generator
├── data/                       # pharmapro.db (created automatically)
└── backups/                    # database backups
```

**Layers:** the UI calls services, services use repositories and models, and repositories talk to SQLite. Services raise friendly `PharmaError` messages, which the UI shows as they are. Unexpected errors are written to `logs/pharmapro.log`, and the pharmacist sees a plain-language message.

**Money** is stored as exact integer paisa and handled as `Decimal` in Python, so there is no floating-point drift in totals.

**Concurrency:** write transactions use SQLite `BEGIN IMMEDIATE`. The stock check and the stock deduction for a sale can never interleave.

## Technology

Python 3.11+ · PySide6 (Qt Widgets) · SQLite · SQLAlchemy 2 · pandas · matplotlib · ReportLab · pytest · PyInstaller

---

## Installation (from source)

**Windows (PowerShell or Command Prompt):**
```bat
cd PharmaPro
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
cd PharmaPro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You only need internet access once, to download the dependencies. After that, everything runs offline.

## Running the application

```bash
python main.py
```

To start with fictional demonstration data (medicines, batches, ~2 months of sales, expenses):

```bash
python main.py --sample-data
```

You can also load demo data later from **Settings → Data safety → Load sample data**. This only works while the database is empty, so demo data never mixes with real records.

To keep data in a different folder: `python main.py --home "D:\PharmaProData"`, or set the `PHARMAPRO_HOME` environment variable.

### Keyboard shortcuts

| Keys | Action |
|---|---|
| `Ctrl+N` | New sale |
| `Ctrl+F` | Search on the current screen |
| `Ctrl+S` | Save (Add Stock, Settings, export the current Report) |
| `Ctrl+P` | Print receipt |
| `Ctrl+Enter` | Complete sale (POS) |
| `Delete` | Remove the selected cart item (POS) |
| `F1`–`F10` | Switch between screens |
| `Enter` / `Esc` | Confirm / close dialogs |

### Barcode scanners

Standard USB scanners act like a keyboard. On the **Sales / POS** screen the cursor sits in the scan field, so scanning a code adds the item; scanning it again adds one more. Store a pack's barcode in the medicine's **Barcode** field, or use the medicine code as the barcode.

## Testing

```bash
# Linux/macOS
QT_QPA_PLATFORM=offscreen python -m pytest -q
# Windows
python -m pytest -q
```

92 tests cover medicine creation, editing, search and duplicate codes; single and multi-medicine stock entry and batch handling; sales, stock deduction, insufficient stock, expired-stock blocking and FEFO; profit, expenses and net profit; receipt numbering, receipts, reports and analytics; backup and restore; transaction rollback; UI workflows driven through the real widgets; and a full run with networking disabled.

## Database location

| Running from | Database |
|---|---|
| Source | `PharmaPro/data/pharmapro.db` |
| Packaged app | `data\pharmapro.db` next to `PharmaPro.exe` (or the Linux `PharmaPro` file) |
| Packaged app in a read-only folder (e.g. Program Files) | `%LOCALAPPDATA%\PharmaPro\data\pharmapro.db` |

The **About** screen and **Settings → Data safety** both show the exact path in use.

## Backup and restore

- **Backup → Back up now** creates `backups/PharmaPro_Backup_YYYY-MM-DD_HHMM.db`. It is safe to run while the app is in use, because it uses SQLite's online backup API.
- **Back up to USB / folder…** saves a copy anywhere you choose. Do this regularly: a backup on the same computer won't help if that computer fails.
- **Automatic backup:** one copy per day when PharmaPro starts (on by default). The newest 30 are kept; you can change this in Settings.
- **Restore** checks that the file is a valid, undamaged PharmaPro backup and asks for confirmation. It saves your current data as `PharmaPro_BeforeRestore_….db` before replacing it, so a restore can always be undone.

## Ready-to-run executables (single file)

PharmaPro ships as **one self-contained file** per platform. The target computer does not need Python or any other software.

| Platform | File | How to run |
|---|---|---|
| Windows 10 / 11 (64-bit) | `PharmaPro.exe` | Copy it anywhere (e.g. `C:\PharmaPro\`) and double-click |
| Linux x86-64 (Ubuntu 22.04+, Debian 12+, Fedora 35+, Mint 21+) | `PharmaPro` | `chmod +x PharmaPro` then double-click or run `./PharmaPro` |
| Ubuntu / Debian / Mint (installer) | `pharmapro_1.0.0_amd64.deb` | `sudo apt install ./pharmapro_1.0.0_amd64.deb`, then open **PharmaPro** from the applications menu or run `pharmapro`. Data is stored in `~/.local/share/PharmaPro` |

- **Your data lives next to the executable,** in `data\`, `backups\`, `logs\`, `receipts\` and `exports\` folders created on first launch. Put the file in a folder you can write to (for example `C:\PharmaPro\`, not the Desktop of another user). If that folder is read-only, PharmaPro uses `%LOCALAPPDATA%\PharmaPro` (Windows) or `~/.local/share/PharmaPro` (Linux) instead.
- **First launch takes a few seconds.** The single file unpacks itself to a temporary folder each time it starts. Only one copy of PharmaPro can run at a time.
- **Updating:** replace the executable with the new one. Your `data` folder is untouched. Back up first anyway.
- **Windows SmartScreen** may say "Windows protected your PC" because the file isn't code-signed. Click **More info → Run anyway**. Signing the `.exe` with a code-signing certificate removes this warning.
- **Linux requirements:** a normal desktop install already has everything. On a minimal system, install the Qt runtime libraries: `sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libegl1` (Debian/Ubuntu).

## Building the executables

**Windows** (on a Windows PC with Python 3.11+):

```bat
packaging\build_windows.bat
```

This creates a virtual environment, installs dependencies, runs the tests and produces **`dist\PharmaPro.exe`**. Run `packaging\build_windows.bat onedir` for a folder build (`dist\PharmaPro\PharmaPro.exe`) that starts faster.

**Linux:**

```bash
bash packaging/build_linux.sh          # -> dist/PharmaPro (single file)
bash packaging/build_linux.sh onedir   # -> dist/PharmaPro/PharmaPro
bash packaging/build_deb.sh            # -> dist/pharmapro_1.0.0_amd64.deb (after the single-file build)
```

For the widest compatibility, build with a Python that targets an old glibc (e.g. `uv python install 3.12`), or on the oldest distribution you want to support.

**Manually:** `pyinstaller --noconfirm --clean PharmaPro-onefile.spec` (single file) or `PharmaPro.spec` (folder).

**Automatically (GitHub Actions):** `.github/workflows/build.yml` tests and builds both executables on real Windows and Linux machines on every push. Pushing a tag such as `v1.0.0` attaches `PharmaPro.exe` and `PharmaPro` to a GitHub Release.

The single-file spec strips Qt components PharmaPro doesn't use (QML/Quick, virtual keyboard, PDF plugin, translations). On Linux it also leaves out the build machine's own system libraries, so the binary runs on other distributions.

## Troubleshooting

| Problem | What to do |
|---|---|
| "No printer found" | Install the receipt printer's driver in Windows, then choose it in **Settings → Receipt printer**. You can always **Save PDF** instead |
| Receipt cut off or too wide | Pick the matching **Paper size** (Thermal 80 mm / 58 mm / A4) in Settings and use **Test print** |
| Scanner adds nothing | Click into the scan field on the POS screen. Check that the scanner sends *Enter* after each code (most do by default) and that the code matches a medicine's code or barcode |
| "Insufficient stock" | The quantity is more than the non-expired stock. The message shows how many units are available and how many are expired |
| "Expired medicine" | The only remaining stock is past its expiry date. Remove it from the shelf. It stays listed under **Inventory → Expired** |
| Database warning at start-up | Restore the latest backup from the **Backup** screen |
| Anything else | Technical details are written to `logs/pharmapro.log` (no patient data is collected) |

## Privacy

PharmaPro collects no patient information and sends nothing anywhere. The only files it writes are the database, backups, logs, receipts and exports, all inside its own folder.
