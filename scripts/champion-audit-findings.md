# Champion AMS: Diagnostic Findings (pre-refactor)

Source checked: `github.com/zed2608/Champion-Management-System` at commit `aa3e305`, the Final Project Documentation PDF (309 pp.), the User's Manual PDF (59 pp.) and the Work Plan PDF.
Line numbers refer to that commit. Every item below was read in the code or the PDFs unless it is marked *(inferred)*.

---

## 0. Fix this today (outside the refactor)

1. **Live database password is public.** The repo is public and contains a committed `.env` (DB_HOST = an Aiven cloud MySQL host). `.env.example` also contains a real-looking Aiven username and password in comments. Even though `.gitignore` lists `.env`, the file was committed before that rule, so Git still tracks it.
   - Rotate the Aiven password now, then `git rm --cached .env remember_config.json __pycache__ -r` and scrub the history (e.g. `git filter-repo`), or make the repo private.
2. **The running system is cloud-hosted, not offline LAN.** The documentation (Scope, Delimitations, Ch. 4, User Manual's "immune to internet hackers") says strictly offline LAN. The actual `.env` points to `*.aivencloud.com`. The panel can catch this. Either migrate to a local MySQL 8.0 server (`scripts/migrate_db_to_lan.py` already exists) or revise the wording.

---

## 1. Database and concurrency

| # | Finding | Where |
|---|---|---|
| 1.1 | **Issuance race condition.** Stock is checked with a plain `SELECT`, then decremented with `UPDATE ... quantity_available - %s` with no row lock and no `quantity_available >= %s` guard. Two terminals can issue the last unit at the same time, and stock can go negative. | `views/borrowing.py` `execute_borrow` (~1094–1160) |
| 1.2 | **No rollback anywhere.** `grep rollback` returns 0 hits. Every multi-step write (issue, return, project save, maintenance resolve) can half-commit on error. | whole repo |
| 1.3 | **Connection leak, so the pool runs out.** `ProfileView` takes a pooled connection in `__init__` and never returns it. The pool has 10 slots, so after enough Profile visits (or several terminals) every module reports "Database connection failed." | `views/profile.py:17` |
| 1.4 | **The documented O(1) hash table does not exist on the QR path.** The only dict cache is `InventoryView.tool_hash_table`. It is rebuilt per page and used only to open an item modal. Issuance and retrieval scans query MySQL directly. Figure 129 and Ch. 2–4 describe a cache that scanning does not use. | `views/inventory.py:29,459,582,777`; `views/borrowing.py:1009` |
| 1.5 | **No canonical schema.** Tables are created in `create_tables.py`, then patched by `db_patch*.py`, `db_upgrade.py`, `fix_db.py`, and by runtime `CREATE/ALTER/DROP TABLE` inside views (`help.py:214` can **DROP** help tables, `borrowing.py` runs ALTER inside a return, `maintenance.py`, `inventory.py`, `tracking.py`, `main.py`). DDL causes an implicit commit in MySQL and needs ALTER privilege at runtime. | many |
| 1.6 | **A fresh install is broken.** `create_tables.py` creates `project_requirements.requirement_id` with no `status` column, but the code uses `pr.req_id` and `pr.status`. It also omits `projects.archived_at`, `user.archived_at`, `transaction.condition_return_notes` and `tool_issues`. | `create_tables.py` vs `borrowing.py:899,1131,1140` |
| 1.7 | **Condition is stored per tool row, not per unit.** Returning one damaged unit of a 10-unit tool sets `tool.condition='Damaged'` and blocks all 10 from issuance. The next "Good" return resets it and hides the damaged unit. | `borrowing.py execute_return`, `add_tool_to_cart` |
| 1.8 | **The system creates phantom stock itself.** When resolving a Damaged or Needs Repair issue, the "restock qty" adds to both `quantity_available` and `quantity_total`. Damaged units never left `quantity_total`, so total is inflated. | `views/maintenance.py:532` |
| 1.9 | **Fractional consumables are miscounted.** Each issued unit is one `transaction` row, and fractions round up (2.5 becomes 3 rows). "Issued" is computed with `COUNT(*)`, so it disagrees with the decimal inventory. | `borrowing.py execute_borrow/execute_return` |
| 1.10 | **Soft-delete problems.** Tools can be archived while units are still deployed (`inventory.py execute_archive`, ~1134). Archived or locked users can still be verified as borrowers (`verify_borrower` does not check status). `projects` has both `is_archived` and `archived_at`. FKs use `ON DELETE CASCADE` from tool and user to `transaction`, so a hard delete would wipe history. | `create_tables.py`, `inventory.py`, `borrowing.py` |
| 1.11 | **Worker-to-project link is a comma-separated text column.** `workers_assigned LIKE '%WKR-2026-001%'` also matches `WKR-2026-0011`. | `borrowing.py:~895`, `projects.py` |
| 1.12 | **ERD and code disagree** (Figure 92). The ERD has `maintenance_issue` (transaction_id, reported_by INT FK, resolved_by, resolved_at) but the code has `tool_issues` (reported_by VARCHAR, is_resolved). The ERD has `transaction.assignee_id/issuance_date/start_date/end_date/retrieval_date` but the code has `user_id/borrow_date/return_date`. The ERD quantities are INT but the code uses DECIMAL. The ERD is missing help, ticket, backup_logs and requirements tables. | Figure 92 |
| 1.13 | **Timezone is hard-coded.** `DATE_ADD(..., INTERVAL 8 HOUR)` is applied in Issuance history only, as a fix for the UTC cloud DB. On a local Manila-time server, times would show 8 hours ahead, and other modules do not apply it. | `borrowing.py` (5 places) |
| 1.14 | Employee ID generation reads the max ID and adds 1 with no lock or retry, so two admins registering at once collide. Lexical `ORDER BY` also breaks after 999. | `role_management.py execute_register` |

## 2. Validation, RBAC and state machine

| # | Finding | Where |
|---|---|---|
| 2.1 | **RBAC is UI-only.** It is enforced only in `DashboardApp.show_frame` (hides 4 modules) and by disabling widgets when `role.lower()=="staff"`. No data function checks the role. Ch. 5 Recommendation #1 confirms evaluators found this. | `dashboard.py:397–410`, `inventory.py:243,808` |
| 2.2 | **Documented Staff access ≠ code.** The docs show *Project Management (Staff)* (Fig. 116) and Staff drafting. The code blocks Project Management for Staff entirely, yet `projects.py` still has non-admin branches. | `dashboard.py`, `projects.py` |
| 2.3 | **Archived or inactive users can log in.** Login checks only `status == 'Locked'`. | `main.py:249` |
| 2.4 | **Project lock is not enforced.** `Approved` projects remain editable even after tools are issued against them. Edit runs `DELETE FROM project_requirements` and re-inserts, which wipes `Fulfilled` flags. Status updates have no `WHERE status = <old>` guard. **Restoring an archived project sets it to `Approved`**, which reopens a Completed project for issuance. | `projects.py:716,997`; `maintenance.py:981` |
| 2.5 | **The 4 dates are not stored on the transaction.** Only `borrow_date` and `return_date` exist. Start and end come from a live join on `projects`, so editing a project silently rewrites history. Nothing checks issuance against the project window. | `borrowing.py`, `reports.py` overdue |
| 2.6 | **Return-condition notes are not required** for Damaged/Lost, although TODO.md marks it done. The success box shows twice and says "Restocked" for Damaged items that are not restocked. | `borrowing.py execute_return` |
| 2.7 | Inventory edit computes `qty_diff` from data loaded when the modal opened. A concurrent issuance makes the "can't go below deployed" check wrong. | `inventory.py execute_update` |
| 2.8 | All Workers share the bcrypt hash of a hard-coded string. Use `NULL` and `CHECK`. | `role_management.py:189` |
| 2.9 | Duplicate full names are rejected outright, so two real employees with the same name (common in PH) cannot both be registered. | `role_management.py`, `profile.py` |
| 2.10 | Passwords are `.strip()`ed at login. bcrypt 5.0 raises `ValueError` above 72 bytes, which surfaces as "Database/System Error". "Forgot Username" reveals any employee ID to anyone who knows an email. | `main.py`, `role_management.py` |
| 2.11 | There are no length caps on search boxes or text fields. SQL is parameterised (good), but search uses `LIKE '%q%'` across 8 columns with no limit on input. | all views |

## 3. Happy path vs unhappy path

| # | Finding | Where |
|---|---|---|
| 3.1 | **The Issuance/Retrieval scanner blocks the Tk main loop.** It is a `while True` OpenCV loop with `cv2.imshow`, which freezes the whole app. If the camera unplugs mid-scan, `ret=False` breaks the loop silently. There is no debounce, no timeout, and no glare or contrast preprocessing. | `borrowing.py:835` |
| 3.2 | The login scanner never tells the user when the camera fails to open. It stays on "Initializing camera feed..." forever. | `main.py open_scanner/scan_loop` |
| 3.3 | **Backup can report success on a partial dump.** A non-zero mysqldump exit is accepted if the file is ≥512 bytes (disk full or LAN drop). The password is passed on the command line (`--password=`), so it is visible in the process list. | `maintenance.py:1300,1316` |
| 3.4 | **Restore has no safety net.** There is no pre-restore safety backup and no check of the file. A corrupt or partial `.sql` is applied up to the first error, leaving a half-restored DB. | `maintenance.py _run_restore` |
| 3.5 | **Logout "No" kills timers.** `confirm_logout` cancels the clock, auto-refresh and inactivity timers *before* asking. Choosing "No" leaves the session without auto-logout. | `dashboard.py:253` |
| 3.6 | Dashboard Matplotlib figures are created with `plt.subplots` and never `plt.close`d, so memory leaks on every Dashboard visit. | `dashboard.py:909,1216` |
| 3.7 | Background threads read Tk widgets (`self.start_date.get()` inside `_fetch_abc`) and call `self.after` from worker threads. Tkinter is not thread-safe. | `reports.py:~214` |
| 3.8 | There is no real pagination. Inventory is capped at `LIMIT 100` (the other ~1,900 tools are invisible unless searched). The Audit tab has **no LIMIT**. Rows are rendered as one CTk widget per cell, which causes the "freeze" in the FAQ. | `inventory.py:546`, `tracking.py load_audit` |
| 3.9 | The issuance history query groups separate issuances by (type, tool, user, status) into one row, so individual 4-date records disappear from that view. | `borrowing.py:551–618` |

## 4. Audit trail / ISO claims

- **The audit trail is erasable.** `log_action` deletes everything beyond the newest 10,000 rows on every insert (`database.py:53`). This contradicts "unalterable", "cannot be erased" and the ISO 9001 claims in the docs and the manual. There is no hash chain, no session ID (Ch. 4 claims "cross-referencing all actions by user session IDs"), and no DB-level protection against `UPDATE/DELETE` on logs.
- Login attempts and account activity sub-modules (Figs. 32–33) are not implemented as screens.

## 5. UI/UX

- Light theme with white cards, 11–13 px fonts and green-on-white status text. This is not glance-friendly on a shop floor, and red/green status colours are not colour-blind safe.
- Inactivity timeout is **5 min** in code (`dashboard.py:277`) but **15 min** in every document.
- Scanner is a separate OpenCV window, not an in-app HUD. There is no beep, no bounding box on the decoded QR and no toast system (`show_toast` is called with `hasattr` guards but never defined in `dashboard.py`).

---

## 6. Documentation ↔ system mismatches (fix in code or in the manuscript)

| Topic | Documentation says | System does |
|---|---|---|
| Deployment | Strictly offline LAN | Aiven cloud MySQL via `.env` |
| Python version | 3.11 | `__pycache__/*.cpython-314.pyc` committed (built on 3.14) |
| Requirements | CTk, OpenCV, pyzbar, bcrypt, Pillow, Matplotlib, NumPy | Also pins **PyQt5 + PyQt6** (unused); `python-dotenv`, `qrcode` unpinned |
| Inactivity logout | 15 minutes | 5 minutes |
| ABC thresholds | A = top 20% items, B = 30%, C = 50% (Ch. 1–3); Ch. 5 says "A = top **70%**" | Cumulative usage share: A ≤ 70%, B ≤ 90%, C rest (`reports.py:262,1453`). Three different definitions. |
| 7 reports | Prompt/memory lists "Inventory Summary" | Code and manuscript: ABC, Usage, Employee Activity, Project Allocation, Damage/Loss, Low Stock, Overdue (no Inventory Summary) |
| Project workflow | Four different lists: "Pending, Declined, Ongoing, Completed/Archived"; "Pending, Reviewed, Ongoing, Completed"; "Pending, Reviewed, Approved, Ongoing, Completed" | Pending → Approved → Ongoing → Completed, plus Cancelled ("Declined" is stored as Cancelled); Ongoing is also auto-set by issuance |
| Requirement lock | Locked "once Ongoing / once tools deployed" | Editable while Approved even with tools out; restore sets Approved |
| Worker login | Manual p.8 / Fig. 136: "Worker Identification via QR… logs you in" | Workers are hard-blocked from login (`main.py`) |
| Manual entry | FAQ: "manual typing is disabled" for worker IDs | Employee ID fields accept typed input + Enter |
| Retrieve flow | Manual Guide B: scan the tool | Code requires the Employee ID first |
| Damaged routing | "Automatically creates an actionable ticket in Maintenance" | Only sets `tool.condition`; a ticket appears when the Maintenance tab next runs its auto-sync query |
| Audit trail | Unalterable, cannot be erased, session IDs | Auto-pruned at 10k rows; no session IDs |
| Hash table | O(1) cache used during QR scanning and search | Search is SQL `LIKE`; scanning hits the DB; cache only in Inventory modal |
| Tagging | "QR/RFID" (Fig. 97) | QR only |
| Registration | Flowchart (Fig. 5) collects security questions | No security questions |
| Restore flowchart | Fig. 8 text is a copy of the Backup text | — |
| Manual section names | "Inactive Archived Projects" describes deactivated users | Tab is Archived Employees |
| Figure refs | Algorithm text cites Figures 93/95/96 | Actual figures are 129–132 |
| Min hardware | Ch. 1/CBA: Core i7, 8 GB | Manual: i5 or i7 |
| Search module | A standalone global Search module (DFD Fig. 54) | Per-table search boxes only |
| Staff dashboard / PM | Fig. 116 Project Management (Staff) | Staff cannot open Project Management |

---

## Recommended defaults the master prompt bakes in

- **4-date rule.** The literal `Issuance ≤ Project Start` would block every top-up issuance once a project has started. The prompt therefore enforces `Start ≤ End` (hard), `Issuance ≤ End` (hard, using server time), `Retrieval ≥ Issuance` (hard, server time), and `Issuance < Start` as an *allowed early-staging* case. It snapshots start and due dates onto each transaction so history never changes.
- **Server-side RBAC.** Since this is a desktop app with no API server, the "server side" is a service layer that every view must call. It re-reads the user's role and status from MySQL on each privileged call, and it is backed by restricted MySQL grants per role and by DB triggers that block log tampering.
