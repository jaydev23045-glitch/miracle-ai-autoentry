"""
Unit tests for transaction nature classifier (Issue #11 Fix).
"""

import sys
import os
import unittest

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from transaction_classifier import classify_transaction_nature


class TestTransactionClassifier(unittest.TestCase):

    def test_bank_charges(self):
        self.assertEqual(
            classify_transaction_nature("SMS CHG FOR Q2", tx_type="Payment"),
            "Indirect Expenses"
        )
        self.assertEqual(
            classify_transaction_nature("BANK CHARGES INCL GST", tx_type="Payment"),
            "Indirect Expenses"
        )

    def test_cash_movements(self):
        self.assertEqual(
            classify_transaction_nature("ATM CASH WITHDRAWAL", tx_type="Payment"),
            "Cash in Hand"
        )
        self.assertEqual(
            classify_transaction_nature("CASH DEPOSIT AT BRANCH", tx_type="Receipt"),
            "Cash in Hand"
        )

    def test_statutory_taxes(self):
        self.assertEqual(
            classify_transaction_nature("GSTPMT CHALLAN PAYMENT", tx_type="Payment"),
            "Duties & Taxes"
        )
        self.assertEqual(
            classify_transaction_nature("TDS PAYMENT U/S 194C", tx_type="Payment"),
            "Duties & Taxes"
        )

    def test_salary_and_payroll(self):
        self.assertEqual(
            classify_transaction_nature("SALARY FOR AUGUST 2026", tx_type="Payment"),
            "Indirect Expenses"
        )
        self.assertEqual(
            classify_transaction_nature("SALARY CREDIT FROM INFOSYS", tx_type="Receipt"),
            "Indirect Income"
        )

    def test_loan_emi_and_investments(self):
        self.assertEqual(
            classify_transaction_nature(
                "ACH D- HDFC HOME LOAN EMI", amount=50000, tx_type="Payment"
            ),
            "Secured Loans"
        )
        self.assertEqual(
            classify_transaction_nature("ZERODHA BROKING DEBIT", tx_type="Payment"),
            "Investments"
        )

    def test_utilities_and_bills(self):
        self.assertEqual(
            classify_transaction_nature("MSEB ELECTRICITY BILL", tx_type="Payment"),
            "Indirect Expenses"
        )
        self.assertEqual(
            classify_transaction_nature("AIRTEL BROADBAND RECHARGE", tx_type="Payment"),
            "Indirect Expenses"
        )

    def test_reversals_and_refunds(self):
        self.assertEqual(
            classify_transaction_nature(
                "REFUND FOR FAILED TXN", party_name="AMAZON", tx_type="Receipt"
            ),
            "Sundry Debtors"
        )


if __name__ == "__main__":
    unittest.main()
