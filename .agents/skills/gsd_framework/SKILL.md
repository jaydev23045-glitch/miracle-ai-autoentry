---
name: gsd_framework
description: Spec-Driven Context Engineering & Modular Execution protocol for Antigravity. Triggers when working on complex accounting features (GST Composition, 194Q TDS, Multi-Bank Contras, Remote Sync) to prevent context rot.
---

# GSD (Get-Shit-Done) Core — Spec-Driven Execution Protocol

> **Purpose**: Prevent context degradation and technical rot during complex accounting feature development by enforcing explicit specification, isolated context engineering, and atomic modular execution steps adhering to the 37 Smart Rules Protocol.

---

## 🛠️ The 3-Phase GSD Workflow in Antigravity

### Phase 1: Context Isolation & Spec Engineering (`implementation_plan.md`)
Before modifying code for a complex accounting feature:
1. **Define Input/Output Contract**: Document exact payload input and DBF output formats.
2. **Identify Target DBF Schema**: Identify affected DBF files (`RKACCT41.DBF`, `RKACCT40.DBF`, `RKACCT01.DBF`, `RKACCM01.DBF`, `RKACCM11.DBF`, `RKACCGID.DBF`).
3. **Verify Smart Rules Compliance**: Check applicable directives in `docs/AI_RULES.md` (e.g. Rule 8 dual narration writing, Rule 15 DB locks, Rule 34 cash isolation, Rule 37 inter-bank contras).
4. **Task Decomposition**: Divide implementation into atomic sub-tasks (max 1 sub-task per execution step).
5. **Create Implementation Plan**: Create `implementation_plan.md` using Planning Mode.

### Phase 2: Modular Step-by-Step Code Execution
1. Implement **one sub-task at a time**.
2. **Isolate Domain Context**: Never mix API router changes, DBF handle changes, and frontend UI changes in a single step.
3. **Immediate Validation**: Test code syntax (`python3 -m py_compile`), imports, and logic after each step before moving to the next.

### Phase 3: Integrity Verification & Walkthrough
1. **Run Integrity Check**: Execute `python backend/verify_integrity.py` to confirm double-entry math and ledger alignment.
2. **DBF Byte Offset & Field Width Integrity**: Verify binary DBF headers, string width limits (`fit_dbf_str`), and `.CDX` index offsets remain uncorrupted.
3. **Create Walkthrough Artifact**: Summarize changes, tests run, and results in `walkthrough.md`.

---

## 💡 How to Trigger GSD Core in Antigravity

Start your request with:
`[GSD] Implement 194Q TDS deduction logic for purchase vouchers`
or
`[GSD] Add Multi-Bank Contra voucher auto-entry system`
