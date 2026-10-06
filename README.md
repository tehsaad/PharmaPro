# PharmaPro 1.0.0: ready-to-run downloads

These are the finished **PharmaPro** programs, an offline pharmacy management system. Each file is the complete application: no Python, database server or internet connection is needed.
The source code is on the [`source-code`](../../tree/source-code) branch.

| File | For | Size |
|---|---|---|
| [`Windows/PharmaPro.exe`](Windows/PharmaPro.exe) | Windows 10 / 11, 64-bit | 78 MB |
| [`Linux/pharmapro_1.0.0_amd64.deb`](Linux/pharmapro_1.0.0_amd64.deb) | Ubuntu 22.04+, Debian 12+, Linux Mint 21+ (installer) | 98 MB |
| [`Linux/PharmaPro`](Linux/PharmaPro) | Any x86-64 Linux with glibc 2.34+ (portable single file) | 99 MB |

Open a file above and click **Download raw file** (the ⬇ icon).

## Windows

1. Create a folder such as `C:\PharmaPro` and put `PharmaPro.exe` in it.
2. Double-click `PharmaPro.exe`. To make a shortcut: right-click → *Send to* → *Desktop*.
3. If Windows shows **"Windows protected your PC"**, click **More info → Run anyway**. This appears because the file isn't code-signed.

Your data is stored in folders created **next to** `PharmaPro.exe`: `data\`, `backups\`, `logs\`, `receipts\` and `exports\`.

## Ubuntu / Debian / Mint (.deb)

```bash
sudo apt install ./pharmapro_1.0.0_amd64.deb
```

Then open **PharmaPro** from the applications menu, or run `pharmapro`. Your data is stored in `~/.local/share/PharmaPro`.
To uninstall: `sudo apt remove pharmapro`. Your data folder is kept.

## Other Linux (portable file)

```bash
chmod +x PharmaPro
./PharmaPro
```

Your data is stored next to the file. On a minimal system you may need `libxcb-cursor0 libxkbcommon-x11-0 libegl1`.

## First start

- Opening takes a few seconds, because the program unpacks itself on each launch. Only one copy runs at a time.
- To explore with fictional demo data, use **Settings → Data safety → Load sample data**. This only works while the database is empty.
- Enter your pharmacy's name, address, phone, receipt printer and paper size in **Settings**.

## Keep your data safe

- Use **Backup → Back up to USB / folder…** regularly.
- Moving to a new computer: copy the program **and** the `data` folder.
- Updating: replace only the program file and keep the `data` folder.

## Verify downloads

```bash
sha256sum -c SHA256SUMS.txt
```
