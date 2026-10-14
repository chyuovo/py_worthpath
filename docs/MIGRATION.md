# Migration tracking

Machine-readable full file/route/model/migration inventory: migration-inventory.json.

Source remains read-only. Existing source compose.yaml changes are pre-existing. Frontend copied byte-for-byte. Original Prisma history is reference only; Alembic will be the only new schema execution path. No Docker files are introduced.

Acceptance is pending until Python routes, MySQL schema, transaction/idempotency/security tests, original checks, and desktop/mobile browser comparisons pass.
