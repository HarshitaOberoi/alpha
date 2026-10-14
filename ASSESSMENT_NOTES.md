# ASSESSMENT NOTES — CapitalRecon

**App name:** CapitalRecon
**Stack:** Django + Django REST Framework (backend), React + Vite (frontend), PostgreSQL (with SQLite fallback for local dev).

---

## Demo Video Walkthrough

<video width="100%" controls>
  <source src="Untitled design.mp4" type="video/mp4">
</video>

[Download video](Untitled design.mp4)

---

## 1. Setup from a fresh clone

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# Create the database in PostgreSQL (optional):
#   createdb capitalrecon
# Configure DATABASE_URL / DB_* env vars (see .env.example).
# For local dev without Postgres, leave DB_ENGINE unset and SQLite is used.

python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The API base URL can be overridden with `VITE_API_BASE` (default `http://localhost:8000/api`).

### Run the tests (single command)

```bash
cd backend && python manage.py test capitalrecon.tests -v 2
```

---

## 2. Environment (`.env.example`)

The root `.env.example` lists all variables. Copy it to `.env` and fill in real values. Key variables:

- `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — PostgreSQL connection. Set `DB_ENGINE=django.db.backends.postgresql` to use Postgres; omit it for SQLite.
- `CORS_ALLOWED_ORIGINS`
- `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID` (optional bonus)

No real secrets are committed.

---

## 3. Data model

- **Organization** (`slug` unique, `name`) — tenant. Every record has an `organization` FK.
- **CapitalCall** (`organization`, `call_number`, `call_date`, `due_date`).
- **LineItem** (`capital_call`, `organization`, `investor_entity`, `reference`, `amount_called`, `amount_funded`, `status`). `remaining = amount_called - amount_funded`. Status: `open` / `partially_funded` / `funded`.
- **Transaction** (`organization`, `date`, `description`, `amount` (Decimal), `type` credit/debit, `bank_reference`, `status`, `needs_review_reason`). Unique constraint on `(organization, bank_reference)`. Status: `suggested` / `needs_review` / `reconciled` / `ignored`.
- **Match** (`transaction`, `line_item`, `status`, `reason`). Status: `proposed` / `approved` / `rejected`.

---

## 4. API endpoints

All requests require the header `X-Organization: <slug>`. Missing → `400`; unknown slug → `404`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/organizations/` | List organizations (no header required). |
| POST | `/api/import/` | Upload a CSV as multipart field `file`. Returns `{imported, duplicates, errors:[{line, message}]}`. |
| GET | `/api/transactions/` | List transactions for the org, newest first, with embedded `matches`. |
| GET | `/api/line-items/` | List line items with `amount_called`, `amount_funded`, `remaining`, `status`. |
| POST | `/api/matches/{id}/approve/` | Approve a proposed match. Returns `409` on overpayment or double-approval. |
| POST | `/api/matches/{id}/reject/` | Reject a proposed match. |
| POST | `/api/transactions/{id}/ignore/` | Ignore a `suggested` or `needs_review` transaction. Returns `409` if `reconciled`. |

---

## 5. Matching rules (summary)

1. **Eligible line items:** same org, `remaining > 0`, `call_date <= transaction.date`.
2. **Reference check:** normalize reference (uppercase, strip non-alphanumeric) and look for it in the normalized description or bank reference.
   - One hit, amount ≤ remaining → `suggested` (full or partial).
   - One hit, amount > remaining → `needs_review`, no match (overpayment).
   - Multiple hits → propose all, `needs_review`.
   - If any reference hit, skip step 3.
3. **Name + amount check:** investor name (normalized, trailing LLC/LP/LTD/INC dropped) found as whole words in the description **and** amount equals remaining.
   - One hit → `suggested`.
   - Multiple hits → propose all, `needs_review`.
   - None → `needs_review`, no match.

A reason is stored on every match and on every `needs_review` transaction.

---

## 6. Assumptions & trade-offs

- **Database:** PostgreSQL is the required database. For local development and running tests without a Postgres instance, the settings fall back to SQLite when `DB_ENGINE` / `DATABASE_URL` are unset. All migrations are standard Django migrations and run on either engine. In production/assessment set `DB_ENGINE=django.db.backends.postgresql` and the `DB_*` vars.
- **Decimal storage:** amounts are `DecimalField(max_digits=14, decimal_places=2)`. CSV amounts are parsed with `Decimal` (thousands separators stripped), never `float`.
- **Approvals are atomic:** `approve_match` runs in one transaction, locks the line item, match and transaction rows with `select_for_update`, re-checks the amount and that the match is still `proposed`/transaction not `reconciled`, so a duplicate approval returns `409` and never double-funds.
- **Debits** are stored as `ignored` immediately (they can never pay a capital call).
- **Duplicates** are detected per `(organization, bank_reference)` both against existing rows and within the same file, and reported with their line number.
- **Organization scoping:** a middleware reads `X-Organization`; all querysets are filtered to `request.organization`. A record from another org returns `404` (DRF's `get_object` raises `NotFound`), never `403`.
- **Reason for `needs_review`:** stored in `Transaction.needs_review_reason` and surfaced in the transaction list and UI.
- **Frontend:** a single React page (`App.jsx`) with an organization switcher, CSV upload, transaction table (with approve/reject/ignore actions and per-row loading states), and a line-item panel.

---

## 7. Next steps (out of scope)

- Implement the optional Airtable sync for `needs_review` transactions (stub fields `airtable_record_id` / `airtable_sync_status` already exist on `Transaction`).
- Add pagination for large transaction lists (files may contain thousands of rows).
- Add authentication/roles (currently org is chosen via header, as specified).
- Add a Django admin view for reviewing matches.

---

## 8. Integrity

> I completed this assessment without using AI assistance.
