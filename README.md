# Odoo Attendance Automator 🕒

A lightweight, automated Python script to bulk-register check-in and check-out times in Odoo for all working days (Monday to Friday) of a given month. It uses the Odoo XML-RPC API and automatically handles local-to-UTC time conversions.

## How to use

### Install

1. Nix Flake
2. direnv

### Setup

1. direnv allow
2. edit .env

```bash
ODOO_URL=
ODOO_DB=
ODOO_USER=
ODOO_TOKEN=
```

3. edit the script with month and year to register or delete

### Run

```bash
uv run python odoo_add.py
```

```bash
uv run python odoo_del.py
```
