# 🧠 CQE Kernel / Policy Separation Contract (v1)

## 0. 核心原则（不可违约）

### P0. Kernel is mathematically pure

Kernel must be:

* deterministic
* stateless
* side-effect free
* graph-agnostic (no semantic interpretation)

> Kernel = argmax path scoring engine only

---

### P1. Policy is allowed to be wrong

Policy may:

* prune edges
* reweight edges
* inject heuristics
* apply grammar constraints
* use entropy / hub penalties

BUT:

> Policy correctness is not required for kernel correctness

---

### P2. Hard separation invariant (CRITICAL)

```
Kernel(input_graph) MUST NOT depend on:
    - layer labels
    - grammar state
    - hub scores
    - entropy state
    - runtime metadata

Only allowed input:
    nodes, edges, weights
```

---

## 1. Kernel Contract (CQEKernel)

### 1.1 Interface

```python
class CQEKernel:
    def query(
        graph: Graph,
        start: Node,
        tau: float,
        max_depth: int
    ) -> QueryResult:
```

---

### 1.2 Allowed assumptions

Kernel may assume:

* graph is directed weighted graph
* weights ∈ [0, 1]
* edges are immutable during execution
* cycles may exist

---

### 1.3 Forbidden behaviors

Kernel MUST NOT:

* ❌ inspect node type (`cat::`, `sym::`)
* ❌ inspect edge type (call/import/category/etc)
* ❌ apply grammar rules
* ❌ apply hub penalties
* ❌ modify graph
* ❌ cache semantic state across queries

---

### 1.4 Kernel math model

Kernel is strictly:

```
score(path) = Π w(e_i)
answer = argmax(score)
prune if score < tau
```

No exceptions.

---

## 2. Policy Contract (CQEPolicy)

Policy is the “dirty layer”

### 2.1 Interface

```python
class CQEPolicy:
    def transform(graph: Graph) -> Graph
    def reweight(edge: Edge) -> float
    def prune(edge: Edge) -> bool
```

---

### 2.2 Allowed operations

Policy may:

* reweight edges
* remove edges
* collapse nodes (optional)
* add virtual edges
* inject layer annotations

---

### 2.3 Policy is NOT allowed to:

* ❌ guarantee determinism
* ❌ assume kernel behavior
* ❌ rely on kernel internal state
* ❌ mutate kernel runtime

---

## 3. Boundary Contract (MOST IMPORTANT PART)

### 3.1 Execution pipeline MUST be:

```
Raw Graph
   ↓
Policy Layer (mutable, heuristic)
   ↓
Transformed Graph (frozen snapshot)
   ↓
Kernel (pure execution)
   ↓
Result
   ↓
Post-process (optional unwrap)
```

---

### 3.2 Hard rule

> Kernel NEVER sees Policy logic.

If it does → system is invalid.

---

## 4. Graph Mutation Rules

### 4.1 Graph immutability during query

```text
Query execution MUST NOT mutate graph state
```

Allowed:

* read-only traversal
* temporary heap state

Forbidden:

* edge modification
* weight rewriting
* node injection

---

## 5. CI / Guardrail System (critical for long-term stability)

### 5.1 Static checks

Fail build if:

#### Kernel violations:

* import of `Policy` inside `kernel.py`
* usage of:

  * `layer`
  * `grammar`
  * `hub`
  * `entropy`

---

### 5.2 Runtime assertions

```python
assert not kernel_uses_metadata(edge)
assert graph.is_frozen()
assert policy_not_in_kernel_stacktrace()
```

---

### 5.3 Dependency rule

```
kernel → NO outgoing dependency to policy
policy → MAY depend on kernel
```

---

## 6. Architectural invariant (the “gold rule”)

> Kernel defines computation
> Policy defines meaning
> Graph defines reality

Never collapse the three.

---

## 7. Failure modes this contract prevents

### ❌ Prevents:

* semantic drift inside kernel
* Dijkstra turning into rule engine
* hub explosion poisoning ranking
* grammar logic leaking into traversal
* non-deterministic query behavior

---

## 8. System classification after applying this

Your system becomes:

> **Deterministic Graph Scoring Engine + External Semantic Compiler**

Not:

* AI graph system
* adaptive search engine
* self-modifying reasoning graph

---

## 9. What this contract allows you to build next (important)

Now you can safely add:

* learned policy layer (ML ranking)
* multiple policies (A/B testing)
* runtime heuristics experiments
* graph enrichment pipelines
* semantic compilers

WITHOUT risking kernel corruption.

---

## 10. Final summary

This contract enforces:

> 🧱 Kernel = physics
> 🧠 Policy = interpretation
> 🧪 Everything else = experimentation