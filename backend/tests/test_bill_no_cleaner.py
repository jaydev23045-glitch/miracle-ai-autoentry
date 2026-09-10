"""
Unit tests for bill number cleaning, party prefix stripping, and trailing zero preservation.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.excel_parser import clean_extracted_bill_no
from dbf_handler import MiracleDBFHandler


class TestBillNoCleaner(unittest.TestCase):

    def test_party_prefix_stripping(self):
        # Case 1: Sub-word overlap ("NDIA" in "Labindia Instruments pvt")
        self.assertEqual(
            clean_extracted_bill_no("NDIA/3364", "Labindia Instruments pvt"),
            "3364"
        )
        # Case 2: Exact party word prefix ("LABINDIA/3364")
        self.assertEqual(
            clean_extracted_bill_no("LABINDIA/3364", "Labindia Instruments pvt"),
            "3364"
        )
        # Case 3: Full party name prefix ("Shridhar Ganeshan/3354")
        self.assertEqual(
            clean_extracted_bill_no("Shridhar Ganeshan/3354", "Shridhar Ganeshan"),
            "3354"
        )
        # Case 4: Space-separated party name prefix ("Dr Rahul Warke 3363")
        self.assertEqual(
            clean_extracted_bill_no("Dr Rahul Warke 3363", "Dr Rahul Warke"),
            "3363"
        )
        # Case 5: Party acronym/initials prefix ("BYLNCH/3355" for "The Dean and Managing Trustee, B.Y.Nair Charitable Hospital")
        self.assertEqual(
            clean_extracted_bill_no("BYLNCH/3355", "The Dean and Managing Trustee, B.Y.Nair Charitable Hospital"),
            "3355"
        )

    def test_trailing_zero_preservation(self):
        # Ensure float .0 suffix is stripped without ruining bill numbers ending in zero (e.g. 3370)
        self.assertEqual(clean_extracted_bill_no("3370.0"), "3370")
        self.assertEqual(clean_extracted_bill_no("3360"), "3360")
        self.assertEqual(clean_extracted_bill_no("3350.0"), "3350")
        self.assertEqual(clean_extracted_bill_no("100.0"), "100")

    def test_genuine_invoice_series(self):
        # Genuine series prefixes should NOT be stripped
        self.assertEqual(
            clean_extracted_bill_no("INV-2026/3364", "Labindia Instruments pvt"),
            "INV-2026/3364"
        )
        self.assertEqual(
            clean_extracted_bill_no("SS/3364", "Labindia Instruments pvt"),
            "SS/3364"
        )
        self.assertEqual(
            clean_extracted_bill_no("GST/26-27/3364", "Labindia Instruments pvt"),
            "GST/26-27/3364"
        )

    def test_no_inv_placeholder(self):
        self.assertEqual(clean_extracted_bill_no("NO_INV_2026-07-02_Cash"), "")


if __name__ == "__main__":
    unittest.main()
