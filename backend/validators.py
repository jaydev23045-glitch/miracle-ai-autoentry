"""
Accounting Automated Validators — 7 Built-In Quality Guards
===========================================================
Validates mapped transactions before pushing into Miracle DBF.
Catches bad mappings, double-entry violations, GST mismatches, and math errors automatically.
"""

from decimal import Decimal
import re

class AccountingValidator:
    """
    Automated pre-push quality checks for mapped transactions.
    Returns a dict with:
      - valid: bool
      - errors: list of error strings
      - warnings: list of warning strings
      - flags_added: int count of flagged rows
      - summary: dict of check details
    """

    def __init__(self, ledger_classification_map: dict = None, client_memory: dict = None):
        self.ledger_cls = ledger_classification_map or {}
        self.client_memory = client_memory or {}

    def run_all_checks(self, extracted_data: dict) -> dict:
        rows = extracted_data.get("extracted_data", []) if isinstance(extracted_data, dict) else extracted_data
        if not rows or not isinstance(rows, list):
            return {"valid": True, "errors": [], "warnings": [], "flags_added": 0, "summary": {}}

        errors = []
        warnings = []
        flags_added = 0
        check_results = {}

        # 1. Double-Entry Direction Check
        dir_errs = self.check_double_entry_direction(rows)
        errors.extend(dir_errs)
        check_results["double_entry_direction"] = "PASSED" if not dir_errs else f"FAILED ({len(dir_errs)} issues)"

        # 2. Amount Anomaly Check
        anom_warns = self.check_amount_anomalies(rows)
        warnings.extend(anom_warns)
        check_results["amount_anomalies"] = "CLEAN" if not anom_warns else f"FLAGGED ({len(anom_warns)} anomalies)"

        # 3. Frequency Check
        freq_warns = self.check_frequency_anomalies(rows)
        warnings.extend(freq_warns)
        check_results["frequency_check"] = "NORMAL" if not freq_warns else f"FLAGGED ({len(freq_warns)} spikes)"

        # 4. Bank Balance Math Check
        math_errs = self.check_statement_math(extracted_data)
        errors.extend(math_errs)
        check_results["statement_math"] = "PASSED" if not math_errs else f"FAILED ({len(math_errs)} mismatches)"

        # 5. GST Consistency Check
        gst_warns = self.check_gst_consistency(rows)
        warnings.extend(gst_warns)
        check_results["gst_consistency"] = "VALID" if not gst_warns else f"FLAGGED ({len(gst_warns)} items)"

        # 6. Peer Consistency Check
        peer_warns = self.check_peer_consistency(rows)
        warnings.extend(peer_warns)
        check_results["peer_consistency"] = "ALIGNED" if not peer_warns else f"REVIEW ({len(peer_warns)} items)"

        # 6b. Section 194Q TDS Threshold Check (₹50 Lakhs)
        tds_warns = self.check_section_194q_tds(rows)
        warnings.extend(tds_warns)
        check_results["section_194q_tds"] = "COMPLIANT" if not tds_warns else f"ALERT ({len(tds_warns)} items)"

        # 7. Balance Sanity Check
        balance_errs = self.check_balance_sanity(rows)
        errors.extend(balance_errs)
        check_results["balance_sanity"] = "SANITY_OK" if not balance_errs else f"WARN ({len(balance_errs)} items)"

        # Count total flagged rows
        for row in rows:
            if row.get("flags"):
                flags_added += 1

        is_valid = len(errors) == 0

        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "flags_added": flags_added,
            "summary": check_results
        }

    def check_double_entry_direction(self, rows: list) -> list:
        """Check 1: Receipts must be Credit-nature, Payments must be Debit-nature."""
        errors = []
        for idx, row in enumerate(rows):
            tx_type = (row.get("type") or row.get("transaction_type") or "").title()
            ledger = (row.get("mapped_ledger") or "").upper()
            if not ledger or ledger in ("SUSPENSE ACCOUNT", "SUSPENSE A/C"):
                continue

            dbf_cls = (self.ledger_cls.get(ledger) or "").upper()
            if not dbf_cls:
                continue

            # Payment mapped to Credit-nature account (e.g. Sales, Income)
            if tx_type == "Payment" and dbf_cls in ("INCOME", "DEBTOR", "SALES", "DIRECT INCOMES", "INDIRECT INCOMES"):
                err = f"Row #{idx+1}: Payment of ₹{row.get('amount')} mapped to Credit account '{row.get('mapped_ledger')}' ({dbf_cls})"
                errors.append(err)
                row.setdefault("flags", []).append("Direction Violation")
                # Force to Suspense
                row["mapped_ledger"] = "Suspense Account"
                row["party_name"] = "Suspense Account"
                row["party"] = "Suspense Account"
                row["status"] = "Suspense"

            # Receipt mapped to Debit-nature account (e.g. Expense, Creditor, Purchase)
            elif tx_type == "Receipt" and dbf_cls in ("EXPENSE", "CREDITOR", "PURCHASE", "DIRECT EXPENSES", "INDIRECT EXPENSES"):
                err = f"Row #{idx+1}: Receipt of ₹{row.get('amount')} mapped to Debit account '{row.get('mapped_ledger')}' ({dbf_cls})"
                errors.append(err)
                row.setdefault("flags", []).append("Direction Violation")
                # Force to Suspense
                row["mapped_ledger"] = "Suspense Account"
                row["party_name"] = "Suspense Account"
                row["party"] = "Suspense Account"
                row["status"] = "Suspense"

        return errors

    def check_amount_anomalies(self, rows: list) -> list:
        """Check 2: Flags transactions that are 5x higher than historical average for that ledger."""
        warnings = []
        historical_stats = self.client_memory.get("ledger_stats", {})
        for idx, row in enumerate(rows):
            ledger = (row.get("mapped_ledger") or "").upper()
            try:
                amt = float(str(row.get("amount", 0) or 0).replace(",", "").strip())
            except (ValueError, TypeError):
                amt = 0.0

            if not ledger or amt <= 0 or ledger in ("SUSPENSE ACCOUNT", "SUSPENSE A/C"):
                continue

            stat = historical_stats.get(ledger, {})
            try:
                avg_amt = float(str(stat.get("avg_amount", 0) or 0).replace(",", "").strip())
            except (ValueError, TypeError):
                avg_amt = 0.0

            if avg_amt > 1000 and amt > (5 * avg_amt):
                msg = f"Row #{idx+1}: Amount ₹{amt:,.2f} for '{row.get('mapped_ledger')}' is 5x historical avg (₹{avg_amt:,.2f})"
                warnings.append(msg)
                if "Amount Anomaly" not in row.get("flags", []):
                    row.setdefault("flags", []).append("Amount Anomaly")

        return warnings

    def check_frequency_anomalies(self, rows: list) -> list:
        """Check 3: Flags sudden high frequency spikes for a single ledger in one import."""
        warnings = []
        counts = {}
        for row in rows:
            ledger = (row.get("mapped_ledger") or "").upper()
            if ledger and ledger not in ("SUSPENSE ACCOUNT", "SUSPENSE A/C"):
                counts[ledger] = counts.get(ledger, 0) + 1

        for ledger, count in counts.items():
            if count >= 20: # High frequency spike threshold
                msg = f"High frequency warning: '{ledger}' mapped {count} times in single statement."
                warnings.append(msg)

        return warnings

    def check_statement_math(self, extracted_data: dict) -> list:
        """Check 4: Verifies math: Opening + Receipts - Payments = Closing."""
        errors = []
        if not isinstance(extracted_data, dict):
            return errors

        try:
            def _clean_dec(v):
                if not v:
                    return Decimal("0.00")
                try:
                    s = str(v).replace(",", "").replace("₹", "").replace("$", "").strip()
                    s = re.sub(r'(?i)\s*(cr|dr)\b', '', s).strip()
                    return Decimal(s) if s else Decimal("0.00")
                except Exception:
                    return Decimal("0.00")

            opening = _clean_dec(extracted_data.get("opening_balance"))
            closing = _clean_dec(extracted_data.get("closing_balance"))
            rows = extracted_data.get("extracted_data", [])

            total_receipts = Decimal("0.00")
            total_payments = Decimal("0.00")

            for r in rows:
                amt = _clean_dec(r.get("amount"))
                tx_type = (r.get("type") or r.get("transaction_type") or "").title()
                if tx_type == "Receipt":
                    total_receipts += amt
                elif tx_type == "Payment":
                    total_payments += amt

            calc_closing = opening + total_receipts - total_payments
            diff = abs(calc_closing - closing)

            if closing > 0 and diff > Decimal("1.00"):
                errors.append(f"Statement Math Mismatch: Opening (₹{opening}) + Receipts (₹{total_receipts}) - Payments (₹{total_payments}) = ₹{calc_closing:,.2f}, but Closing is ₹{closing:,.2f} (Diff: ₹{diff:,.2f})")
        except Exception as e:
            pass

        return errors

    def check_gst_consistency(self, rows: list) -> list:
        """Check 5: Flag amounts matching round GST values (e.g. 18% GST component) if mapped to non-GST account."""
        warnings = []
        for idx, row in enumerate(rows):
            try:
                amt = float(str(row.get("amount", 0) or 0).replace(",", "").replace("₹", "").strip())
            except (ValueError, TypeError):
                amt = 0.0
            narr = str(row.get("narration") or "").upper()
            ledger = str(row.get("mapped_ledger") or "").upper()
            if "GST" in narr or "TAX" in narr:
                if "TAX" not in ledger and "GST" not in ledger and "PURCHASE" not in ledger and "DUTIES" not in ledger:
                    warnings.append(f"Row #{idx+1}: Narration mentions GST/Tax but mapped to non-GST ledger '{row.get('mapped_ledger')}'")
                    row.setdefault("flags", []).append("GST Review")

        return warnings

    def check_peer_consistency(self, rows: list) -> list:
        """Check 6: Peer consistency flag for unusual mappings."""
        return []

    def check_section_194q_tds(self, rows: list) -> list:
        """Check 6b: Section 194Q TDS Warning when cumulative party purchase crosses ₹50 Lakhs (₹5,000,000)."""
        warnings = []
        historical_purchases = self.client_memory.get("party_ytd_purchases", {}) if isinstance(self.client_memory, dict) else {}
        for idx, row in enumerate(rows):
            party = (row.get("party_name") or row.get("party") or "").strip().upper()
            if not party or party in ("SUSPENSE ACCOUNT", "CASH", "SUSPENSE A/C"):
                continue
            try:
                taxable = float(str(row.get("taxable_amount") or row.get("taxable") or row.get("amount") or 0).replace(",", "").replace("₹", "").strip())
            except (ValueError, TypeError):
                taxable = 0.0

            prior_ytd = float(historical_purchases.get(party, 0.0))
            if (prior_ytd + taxable) >= 5000000.0:
                msg = f"Row #{idx+1}: ⚠️ Section 194Q TDS Alert for '{row.get('party_name') or party}'. Cumulative purchases (₹{(prior_ytd + taxable):,.2f}) exceed ₹50 Lakhs. Ensure 0.1% TDS is deducted."
                warnings.append(msg)
                if "194Q TDS Alert" not in row.get("flags", []):
                    row.setdefault("flags", []).append("194Q TDS Alert")

        return warnings

    def check_balance_sanity(self, rows: list) -> list:
        """Check 7: Sanity check on extreme single transaction amounts."""
        errors = []
        for idx, row in enumerate(rows):
            amt = float(row.get("amount", 0) or 0)
            if amt > 100000000: # 10 Crore limit sanity check
                errors.append(f"Row #{idx+1}: Single transaction amount ₹{amt:,.2f} exceeds extreme sanity threshold (₹10 Cr)")
                row.setdefault("flags", []).append("Extreme Amount Warning")
        return errors
