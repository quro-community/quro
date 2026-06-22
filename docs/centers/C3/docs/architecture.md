# C3 Architecture — Semantic Analysis and CQE Refinement Hub

## Overview

C3 is a **Hub** center (290 symbols) that orchestrates semantic analysis and CQE refinement in the Quro system. It acts as a coordination hub for TDA node role classification, CQE quality evaluation refinement, gate type validation, MCP tool dispatch, and workspace scanning.

**Archetype:** Hub — C3 fans out from entry points to downstream subsystems.
**Strategy:** Top-down — explore entry points first, then trace downstream calls to coupled centers.
**Coupling cluster:** SC38 (coupled with C0, C1, C2, C4, C5, C6, C7, C8, C9)

## Hub Architecture

```
                     ┌─────────────────────────────────┐
                     │        C3 — Hub Layer            │
                     │  Semantic Analysis & CQE Refine  │
                     └────┬──────┬──────┬──────┬───────┘
                          │      │      │      │
          ┌───────────────┘      │      │      └───────────────┐
          │                      │      │                      │
          ▼                      ▼      ▼                      ▼
   ┌────────────┐    ┌──────────────┐    ┌────────────┐  ┌──────────┐
   │ TDA        │    │ CQE          │    │ MCP        │  │ Workspace│
   │ Classifier │    │ Refinement   │    │ Tool       │  │ Scanner  │
   │ (C0/C1/C2) │    │ (C4/C5/C6)   │    │ Dispatch   │  │ (C8/C9)  │
   └────────────┘    └──────────────┘    │ (C5/C7)    │  └──────────┘
                                         └────────────┘
```

## Core Capabilities

### 1. TDA Node Role Classification
- **Entry:** `sym::classify_node_role::upstream_navigator::325`
- Classifies nodes in the TDA energy landscape into roles (emitter, converter, sink, attractor)
- Provides upstream navigation for tracing call chains
- Bridges TDA analysis from C0/C1/C2 into actionable role metadata

### 2. CQE Refinement
- **Entry:** `sym::SemanticCQERefiner::refiner::128`
- Refines code quality evaluation results using semantic analysis
- Computes quality metrics and confidence scores
- Coordinates with C4 (quality reporting) and C5/C6 (quality pipeline)

### 3. Gate Result Types
- **Entry:** `sym::GateResult::types::13`
- Defines the type system for gate operation results
- Handles result validation, transformation, and routing

### 4. MCP Tool Dispatch
- **Entry:** `sym::call_tool`
- Invokes MCP tools via a unified dispatch interface
- Resolves tool names to implementations
- Manages tool execution lifecycle

### 5. Workspace Scanning
- **Entry:** `sym::scan_workspace`
- Scans filesystem workspace for code symbols
- Feeds symbol data into indexing and analysis pipelines
- Coordinates with C8 (MinHash LSH) for similarity detection

## Key Design Decisions

1. **Entry-point-driven:** All major capabilities are exposed through well-defined entry points, enabling top-down navigation.
2. **Hub fanout:** C3 fans out to 9 coupled centers (C0–C9), acting as the coordination nexus for semantic analysis.
3. **Top-down navigation:** Exploration starts at entry points and follows call chains downstream.
4. **Protocol-driven dispatch:** MCP tool dispatch follows a registration + resolution pattern.

## Files (Key Source)

| Entry Point | Key Files |
|-------------|-----------|
| `classify_node_role::upstream_navigator::325` | TDA classification modules |
| `SemanticCQERefiner::refiner::128` | CQE refinement engine |
| `GateResult::types::13` | Gate type definitions |
| `call_tool` | MCP tool dispatch modules |
| `scan_workspace` | Workspace scanner modules |
