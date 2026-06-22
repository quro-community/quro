-- Quro Registry PostgreSQL Schema
-- Version: 1.1.0
-- Date: 2026-04-14

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- Core Tables
-- ============================================================================

-- Files table: tracks all files in the workspace
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_path TEXT NOT NULL UNIQUE,
    language VARCHAR(50) NOT NULL, -- 'python', 'typescript', 'javascript'
    content_hash VARCHAR(64) NOT NULL, -- SHA256 hash of file content
    fingerprint VARCHAR(64), -- SHA256(source + normalized_imports) — semantic fingerprint
    fidelity REAL NOT NULL DEFAULT 1.0, -- method coverage ratio (methods_found / total_methods)
    last_indexed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Symbols table: stores all symbols (functions, classes, variables, etc.)
CREATE TABLE IF NOT EXISTS symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind VARCHAR(50) NOT NULL, -- 'function', 'class', 'variable', 'method', 'interface'
    line INTEGER NOT NULL,
    col INTEGER NOT NULL,
    end_line INTEGER,
    end_col INTEGER,
    signature TEXT, -- Full signature for functions/methods
    docstring TEXT,
    type_hint TEXT,
    decorators JSONB, -- Array of decorator names
    role VARCHAR(100), -- 'controller', 'service', 'repository', 'utility', etc.
    intent TEXT, -- High-level purpose description
    behavioral_tags JSONB, -- Array of LSH behavioral tags
    lsh_signature BYTEA, -- MinHash LSH signature (binary)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(file_id, name, line, col)
);

-- Imports table: tracks import statements
CREATE TABLE IF NOT EXISTS imports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    source_module TEXT NOT NULL, -- Module being imported from
    imported_names JSONB NOT NULL, -- Array of imported symbol names
    alias TEXT, -- Import alias (e.g., 'as pd')
    line INTEGER NOT NULL,
    is_relative BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Exports table: tracks exported symbols
CREATE TABLE IF NOT EXISTS exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE,
    export_name TEXT NOT NULL, -- Name as exported (may differ from symbol name)
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Dependencies table: tracks symbol-to-symbol dependencies
CREATE TABLE IF NOT EXISTS dependencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    to_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    dependency_type VARCHAR(50) NOT NULL, -- 'calls', 'imports', 'inherits', 'uses'
    line INTEGER, -- Line where dependency occurs
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(from_symbol_id, to_symbol_id, dependency_type)
);

-- ============================================================================
-- LSH Tables (Semantic Search)
-- ============================================================================

-- LSH Bands: stores MinHash band hashes for similarity search
CREATE TABLE IF NOT EXISTS lsh_bands (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    band_index INTEGER NOT NULL, -- Band number (0 to num_bands-1)
    band_hash BIGINT NOT NULL, -- Hash of the band
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- LSH Config: stores LSH configuration parameters
CREATE TABLE IF NOT EXISTS lsh_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    num_hashes INTEGER NOT NULL DEFAULT 128, -- Number of hash functions
    num_bands INTEGER NOT NULL DEFAULT 16, -- Number of bands
    rows_per_band INTEGER NOT NULL DEFAULT 8, -- Rows per band (num_hashes / num_bands)
    threshold FLOAT NOT NULL DEFAULT 0.3, -- Similarity threshold
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Pitfall Archive (Known Issues)
-- ============================================================================

-- Pitfalls table: stores known code patterns and issues
CREATE TABLE IF NOT EXISTS pitfalls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(100) NOT NULL, -- 'async', 'lock', 'memory', 'security', etc.
    severity VARCHAR(20) NOT NULL, -- 'critical', 'high', 'medium', 'low'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    pattern TEXT, -- Regex or AST pattern to match
    mitigation TEXT, -- How to fix the issue
    examples JSONB, -- Array of code examples
    tags JSONB, -- Array of related tags
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Pitfall Matches: links symbols to detected pitfalls
CREATE TABLE IF NOT EXISTS pitfall_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    pitfall_id UUID NOT NULL REFERENCES pitfalls(id) ON DELETE CASCADE,
    confidence FLOAT NOT NULL, -- 0.0 to 1.0
    context TEXT, -- Additional context about the match
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(symbol_id, pitfall_id)
);

-- ============================================================================
-- NRT (Non-Regression Testing) Alerts
-- ============================================================================

-- NRT Alerts table: stores real-time alerts for code changes
CREATE TABLE IF NOT EXISTS nrt_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_type VARCHAR(50) NOT NULL, -- 'SYMBOL_NOT_FOUND', 'METHOD_SIGNATURE_MISMATCH', etc.
    severity VARCHAR(20) NOT NULL, -- 'critical', 'high', 'medium', 'low'
    symbol_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB, -- Additional structured data
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================================
-- CQE (Categorical Query Engine) Tables
-- ============================================================================

-- CQE Categories: stores category nodes in the knowledge graph
CREATE TABLE IF NOT EXISTS cqe_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_name TEXT NOT NULL UNIQUE, -- e.g., 'async', 'lock', 'vram'
    description TEXT,
    parent_category_id UUID REFERENCES cqe_categories(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- CQE Edges: stores edges between categories with MI scores
CREATE TABLE IF NOT EXISTS cqe_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_category_id UUID NOT NULL REFERENCES cqe_categories(id) ON DELETE CASCADE,
    to_category_id UUID NOT NULL REFERENCES cqe_categories(id) ON DELETE CASCADE,
    mi_score FLOAT NOT NULL DEFAULT 0.0, -- Mutual information score
    sample_count INTEGER NOT NULL DEFAULT 0, -- Number of samples used to compute MI
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(from_category_id, to_category_id)
);

-- CQE Reflections: stores query reflection logs for MI training
CREATE TABLE IF NOT EXISTS cqe_reflections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id UUID NOT NULL,
    layer VARCHAR(50) NOT NULL, -- 'translation', 'engine', 'interface'
    entry_atom TEXT NOT NULL,
    path_mi FLOAT NOT NULL,
    payload_count INTEGER NOT NULL,
    reflection_data JSONB NOT NULL, -- Full reflection payload
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Shadow Draft System (Neural Compiler)
-- ============================================================================

-- Shadow Drafts: stores shadow draft metadata
CREATE TABLE IF NOT EXISTS shadow_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol_name TEXT NOT NULL,
    language VARCHAR(50) NOT NULL, -- 'python', 'typescript'
    target_path TEXT NOT NULL,
    atoms JSONB NOT NULL, -- Array of DSL atoms
    status VARCHAR(50) NOT NULL, -- 'PENDING', 'SIMULATING', 'MATERIALIZED', 'REJECTED'
    risk_score FLOAT,
    checksum VARCHAR(64), -- SHA256 of atoms
    skeleton_code TEXT, -- Generated skeleton code
    rejection_report JSONB, -- Rejection details if status=REJECTED
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Twin Simulations: stores Monte Carlo simulation results
CREATE TABLE IF NOT EXISTS twin_simulations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    draft_id UUID REFERENCES shadow_drafts(id) ON DELETE CASCADE,
    atoms JSONB NOT NULL,
    iterations INTEGER NOT NULL,
    deadlock_detected BOOLEAN NOT NULL,
    risk_score FLOAT NOT NULL,
    witness_traces JSONB, -- Deadlock witness traces if detected
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Morphism Tables (Symbol Relationships)
-- ============================================================================

-- Morphism Types: edge types for symbol-to-symbol relationships
CREATE TABLE IF NOT EXISTS morphism_types (
    id SERIAL PRIMARY KEY,
    type_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Morphism Edges: typed relationships between symbols
CREATE TABLE IF NOT EXISTS morphism_edges (
    id SERIAL PRIMARY KEY,
    from_symbol_id UUID NOT NULL,
    to_symbol_id UUID NOT NULL,
    morphism_type_id INTEGER NOT NULL REFERENCES morphism_types(id) ON DELETE CASCADE,
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(from_symbol_id, to_symbol_id, morphism_type_id)
);

-- ============================================================================
-- Workspace Metadata
-- ============================================================================

-- Workspace Scans: tracks workspace scan history
CREATE TABLE IF NOT EXISTS workspace_scans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scan_type VARCHAR(50) NOT NULL, -- 'full', 'incremental'
    files_scanned INTEGER NOT NULL,
    symbols_found INTEGER NOT NULL,
    dependencies_mapped INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- QRA (Quantum Reasoning Archive): stores reasoning chains
CREATE TABLE IF NOT EXISTS qra_chains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol_name TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    tags JSONB, -- Array of tags
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Files indexes
CREATE INDEX IF NOT EXISTS idx_files_path ON files(file_path);
CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_fingerprint ON files(fingerprint);

-- Symbols indexes
CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_symbols_role ON symbols(role);
CREATE INDEX IF NOT EXISTS idx_symbols_name_trgm ON symbols USING gin(name gin_trgm_ops);

-- Imports indexes
CREATE INDEX IF NOT EXISTS idx_imports_file_id ON imports(file_id);
CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source_module);

-- Exports indexes
CREATE INDEX IF NOT EXISTS idx_exports_file_id ON exports(file_id);
CREATE INDEX IF NOT EXISTS idx_exports_symbol_id ON exports(symbol_id);

-- Dependencies indexes
CREATE INDEX IF NOT EXISTS idx_dependencies_from ON dependencies(from_symbol_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_to ON dependencies(to_symbol_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_type ON dependencies(dependency_type);

-- LSH indexes
CREATE INDEX IF NOT EXISTS idx_lsh_bands_symbol ON lsh_bands(symbol_id);
CREATE INDEX IF NOT EXISTS idx_lsh_bands_hash ON lsh_bands(band_hash);
CREATE INDEX IF NOT EXISTS idx_lsh_bands_band_idx ON lsh_bands(band_index);

-- Pitfall indexes
CREATE INDEX IF NOT EXISTS idx_pitfalls_category ON pitfalls(category);
CREATE INDEX IF NOT EXISTS idx_pitfalls_severity ON pitfalls(severity);
CREATE INDEX IF NOT EXISTS idx_pitfall_matches_symbol ON pitfall_matches(symbol_id);
CREATE INDEX IF NOT EXISTS idx_pitfall_matches_pitfall ON pitfall_matches(pitfall_id);

-- NRT indexes
CREATE INDEX IF NOT EXISTS idx_nrt_alerts_type ON nrt_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_nrt_alerts_severity ON nrt_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_nrt_alerts_resolved ON nrt_alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_nrt_alerts_created ON nrt_alerts(created_at);

-- CQE indexes
CREATE INDEX IF NOT EXISTS idx_cqe_categories_name ON cqe_categories(category_name);
CREATE INDEX IF NOT EXISTS idx_cqe_edges_from ON cqe_edges(from_category_id);
CREATE INDEX IF NOT EXISTS idx_cqe_edges_to ON cqe_edges(to_category_id);
CREATE INDEX IF NOT EXISTS idx_cqe_reflections_query ON cqe_reflections(query_id);

-- Shadow draft indexes
CREATE INDEX IF NOT EXISTS idx_shadow_drafts_symbol ON shadow_drafts(symbol_name);
CREATE INDEX IF NOT EXISTS idx_shadow_drafts_status ON shadow_drafts(status);
CREATE INDEX IF NOT EXISTS idx_twin_simulations_draft ON twin_simulations(draft_id);

-- Workspace indexes
CREATE INDEX IF NOT EXISTS idx_workspace_scans_created ON workspace_scans(created_at);
CREATE INDEX IF NOT EXISTS idx_qra_chains_symbol ON qra_chains(symbol_name);

-- ============================================================================
-- Triggers for updated_at timestamps
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_files_updated_at BEFORE UPDATE ON files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_symbols_updated_at BEFORE UPDATE ON symbols
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pitfalls_updated_at BEFORE UPDATE ON pitfalls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lsh_config_updated_at BEFORE UPDATE ON lsh_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cqe_edges_updated_at BEFORE UPDATE ON cqe_edges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shadow_drafts_updated_at BEFORE UPDATE ON shadow_drafts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert default LSH config
INSERT INTO lsh_config (num_hashes, num_bands, rows_per_band, threshold)
VALUES (128, 16, 8, 0.3)
ON CONFLICT DO NOTHING;

-- Insert common CQE categories
INSERT INTO cqe_categories (category_name, description) VALUES
    ('async', 'Asynchronous operations and coroutines'),
    ('lock', 'Locking and synchronization primitives'),
    ('vram', 'VRAM and GPU memory management'),
    ('io', 'Input/output operations'),
    ('error', 'Error handling and exceptions'),
    ('security', 'Security-related code patterns'),
    ('performance', 'Performance-critical code'),
    ('test', 'Testing and test utilities')
ON CONFLICT DO NOTHING;

-- Insert morphism type seeds
INSERT INTO morphism_types (type_name, description) VALUES
    ('CALLS', 'Symbol calls another symbol'),
    ('DEFINES', 'File defines a symbol'),
    ('IMPORTS', 'Symbol imports from a module'),
    ('HERITAGE', 'Class inheritance relationship'),
    ('SIMILAR', 'LSH-based code similarity'),
    ('ACQUIRES_BEFORE', 'Resource acquisition ordering'),
    ('EMITS_TO', 'Event/signal emission'),
    ('GATE_FOR', 'Gate/check before execution'),
    ('FUNCTOR_MAPPING', 'Functor/categorical mapping'),
    ('MONAD_BIND', 'Monadic bind operation'),
    ('MUTATES_SHARED', 'Shared state mutation'),
    ('NATURAL_TRANSFORMATION', 'Category theory natural transformation'),
    ('ISOMORPHISM', 'Structural equivalence')
ON CONFLICT (type_name) DO NOTHING;
