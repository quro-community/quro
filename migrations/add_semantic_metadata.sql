-- Migration: Add semantic type metadata to symbols table
-- Date: 2026-04-19
-- Purpose: Support OOP-TDA semantic type system (Design 91)

-- Add semantic metadata columns
ALTER TABLE symbols
ADD COLUMN IF NOT EXISTS node_type VARCHAR(20),
ADD COLUMN IF NOT EXISTS is_container BOOLEAN,
ADD COLUMN IF NOT EXISTS is_executor BOOLEAN;

-- Create index for type-aware queries
CREATE INDEX IF NOT EXISTS idx_symbols_node_type ON symbols(node_type);
CREATE INDEX IF NOT EXISTS idx_symbols_is_container ON symbols(is_container);
CREATE INDEX IF NOT EXISTS idx_symbols_is_executor ON symbols(is_executor);

-- Backfill existing symbols with derived metadata
UPDATE symbols
SET
    node_type = CASE
        WHEN symbol_type = 'class' THEN 'class'
        WHEN symbol_type IN ('method', 'async_method') THEN 'method'
        WHEN symbol_type = 'function' THEN 'function'
        WHEN symbol_type = 'module' THEN 'module'
        ELSE 'function'
    END,
    is_container = CASE
        WHEN symbol_type IN ('class', 'module') THEN TRUE
        ELSE FALSE
    END,
    is_executor = CASE
        WHEN symbol_type IN ('method', 'async_method', 'function') THEN TRUE
        ELSE FALSE
    END
WHERE node_type IS NULL;

-- Add comment
COMMENT ON COLUMN symbols.node_type IS 'Semantic node type: class, method, function, module';
COMMENT ON COLUMN symbols.is_container IS 'True for structural nodes (Classes, Modules)';
COMMENT ON COLUMN symbols.is_executor IS 'True for behavioral nodes (Methods, Functions)';
