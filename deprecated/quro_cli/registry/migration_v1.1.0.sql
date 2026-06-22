-- Migration: v1.0.0 → v1.1.0
-- Add fingerprint and fidelity columns for semantic drift detection
-- Date: 2026-04-14

-- Add fingerprint column: SHA256(source + normalized_imports)
-- Captures semantic drift when imports change, not just implementation
ALTER TABLE files ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(64);

-- Add fidelity column: method coverage ratio (methods_found / total_methods_in_file)
-- Exposes incomplete indexing to AI consumers
ALTER TABLE files ADD COLUMN IF NOT EXISTS fidelity REAL NOT NULL DEFAULT 1.0;

-- Add index for fingerprint lookups (fingerprint-aware diff in scan)
CREATE INDEX IF NOT EXISTS idx_files_fingerprint ON files(fingerprint);

-- Backfill fidelity for existing files (set to 1.0 by default)
-- Fingerprint will be computed on next scan
UPDATE files SET fidelity = 1.0 WHERE fidelity IS NULL;

-- Comment explaining the change
COMMENT ON COLUMN files.fingerprint IS 'SHA256(source + normalized_imports) — captures dependency context drift';
COMMENT ON COLUMN files.fidelity IS 'Method coverage ratio: methods_found / total_methods_in_file. < 0.5 signals incomplete index.';
