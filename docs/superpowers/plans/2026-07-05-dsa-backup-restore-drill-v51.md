# DSA Backup Restore Drill V51

Date: 2026-07-05

Scope: local-only SQLite backup/restore drill tooling. This does not delete or overwrite production data, does not deploy production, and does not approve public launch.

## Goal

Provide a repeatable local dry-run for database backup and restore proof:

- Read a SQLite database.
- Create a timestamped backup copy in a chosen output directory.
- Restore that backup into a separate restored copy.
- Run `PRAGMA integrity_check` and table row-count comparison.
- Return machine-readable evidence.

## Boundaries

- Default verifier uses temporary databases only.
- Operational script must never delete source databases, history reports, user data, API key metadata, billing records, or cache files.
- No AI calls and no live market-data calls.
- Do not include real API keys or secrets in the backup report.
- Staging/production restore evidence still requires human approval before public launch.

## Verifier

Add `scripts/verify_platform_backup_restore_drill_v51.py`.

Expected OK marker:

- `DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK`
