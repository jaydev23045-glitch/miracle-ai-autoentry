---
name: gsd_framework
description: Spec-Driven Context Engineering & Modular Execution protocol for Antigravity. Triggers when working on complex accounting features (GST Composition, 194Q TDS, Multi-Bank Contras) to prevent context rot.
---

# GSD (Get Shit Done) Core - Spec-Driven Execution Protocol

> **Purpose**: Prevent "context rot" during multi-file, heavy-logic feature development by separating architecture design, task decomposition, and code execution into isolated, atomic phases.

---

## 🛠️ The 3-Phase GSD Workflow in Antigravity

### Phase 1: Context Isolation & Spec Engineering (`spec.md`)
Before editing ANY code file for a complex feature:
1. Define the input/output contract (e.g. Gemini extraction format -> DBF double-entry schema).
2. Trace impacted DBF files (e.g. `VOUCHER.DBF`, `ACCMST.DBF`, `RKACCM11.DBF`).
3. Break the feature into atomic sub-tasks (maximum 1 sub-task per execution step).
4. Save the plan in `implementation_plan.md` using Antigravity Planning Mode.

### Phase 2: Modular Step-by-Step Code Execution
1. Implement **one sub-task at a time**.
2. Avoid mixing API changes, UI changes, and DBF writing logic in a single context turn.
3. Validate each step immediately (compile/lint check) before proceeding to the next.

### Phase 3: Integrity & Schema Verification
1. Run `python backend/verify_integrity.py` to verify ledger mapping & calculation integrity.
2. Verify DBF header fields and byte offsets remain uncorrupted.
3. Generate a `walkthrough.md` artifact showing exact verification outcomes.

---

## 💡 How to Trigger GSD Core in Antigravity
Simply start your request with:
`[GSD] Implement 194Q TDS deduction logic for purchase vouchers`
or
`[GSD] Add Multi-Bank Contra voucher auto-entry`
