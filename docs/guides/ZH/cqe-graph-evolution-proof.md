# CQE Graph 演化收敛性证明

> **目标**：证明 CQE Graph 在 Fix Plan + Invariants 约束下不会无限震荡，必收敛到稳定态。
>
> **受众**：需要理解 CQE 修复系统为什么不会出现"无限修复循环"的开发者。

---

## 1. 系统抽象

将 CQE Graph 建模为离散时间状态空间：

```text
G₀ → G₁ → G₂ → ... → Gₙ
```

每一步的状态转移定义为：

```text
G_{t+1} = F(G_t, P_t)
```

其中：

| 符号 | 含义 |
|------|------|
| `F` | Fix Plan 应用函数 —— 将一组修复作用于当前图 |
| `P_t` | Stability Filter 筛选后的修复集合 |

---

## 2. 关键约束

系统内置两类约束，共同保证收敛性。

### 2.1 Invariants（硬约束）

所有图必须属于合法状态空间：

```text
G ∈ 𝒢_valid
```

具体条目：

- **out-degree ≤ C**（结构有效，Structural Validity）
- **alias DAG**（别名一致性，Alias Consistency）
- **path decay constraint**（路径衰减约束，Path Decay）

> 状态空间被限制在 **有限可行集合** 内。

### 2.2 Fix Plan Stability（软约束）

定义单步结构变化量：

```text
Δ(G_t) = structural change magnitude
```

过滤规则：

```text
if Δ(G_t) < ε → no update  （变动不足阈值则跳过）
```

以及：

| 机制 | 作用 |
|------|------|
| 幂等去重 `applied_hashes` | 同一修复不重复应用 |
| 节点冻结 `node_modified_counts` | 每个节点修改次数有上限 |

---

## 3. 关键数学引理

### 引理 1：状态空间有限性

前提：

- 节点总数有限
- 每个节点 out-degree 有上限 `C`
- alias mapping 受 DAG 约束

因此：

```text
|𝒢_valid| < ∞
```

即合法状态空间的大小是有限的。

---

### 引理 2：单步不可逆增长被限制

Fix Plan 包含：

- frozen nodes（冻结节点不可再修改）
- deduplication（幂等去重）
- Δ threshold（变动阈值过滤微小变化）

推出：

```text
每个 G_t 的"可修改自由度"单调递减
```

---

## 4. 核心结论：收敛性

定义 Lyapunov-like 势函数：

```text
V(G) = number of active mutable graph edits remaining
```

性质：

| 性质 | 说明 |
|------|------|
| `V(G) ≥ 0` | 势函数非负 |
| `V(G_{t+1}) ≤ V(G_t)` | 每步单调不增 |

递降机制：

- **freeze** → 永久减少 `V`
- **dedup** → 阻止 `V` 回升
- **invariants** → 剪枝状态空间，避免无效探索

---

## 5. 收敛定理

### 定理表述

```text
∃ T < ∞ :
G_T = G_{T+1} = G_{T+2} = ...
```

即：存在有限时间 `T`，之后系统进入不动点，状态不再变化。

### 证明纲要

1. `V(G)` 为非负整数
2. `V(G)` 单调不增
3. 状态空间 `𝒢_valid` 有限
4. 每一步只有两种可能：**fix**（应用修复）或 **skip**（跳过）
5. 因此系统无法进行无限非平凡演化

> 必然进入固定点（fixed point）。

---

## 6. 固定点定义

```text
G* = F(G*, P*)
```

满足全部条件：

- **无 violation**：所有 Invariants 通过
- **无 applicable fix**：Stability Filter 阻断所有候选修复，或 Detox 检测到 0 个问题
- **entropy stable**：`Δ(G) < ε`
- **invariants satisfied**：硬约束全部满足

---

## 7. 最终结论

从 CQE 视角，Graph Evolution 是一个：

> 在有限状态空间内运行的、带单调约束的修复系统。

因此：

```text
✔ 必收敛
✔ 不存在无限修复循环
✔ 最终进入稳定图结构
```
