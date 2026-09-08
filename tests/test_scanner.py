"""
Automated unit and integration tests for Fuel Receipt OCR Scanner.
"""

import io
import os
import sys
import unittest

# Ensure src is on path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(os.path.dirname(BASE_DIR), "src")
SAMPLES_DIR = os.path.join(os.path.dirname(BASE_DIR), "samples")
sys.path.insert(0, SRC_DIR)

from receipt_scanner import FuelReceiptOCR
from app import app


class TestFuelReceiptOCR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scanner = FuelReceiptOCR()
        cls.sample2_img = os.path.join(SAMPLES_DIR, "sample2.jpg")
        cls.sample4_img = os.path.join(SAMPLES_DIR, "sample4.jpg")
        cls.sample6_img = os.path.join(SAMPLES_DIR, "sample6.jpg")
        cls.sample10_img = os.path.join(SAMPLES_DIR, "sample10.jpeg")

    def test_scan_sample2_grand_total_cash(self):
        """Test capturing total amount and raw text from sample2.jpg ($60.00)."""
        self.assertTrue(os.path.exists(self.sample2_img))
        result = self.scanner.scan_receipt(self.sample2_img)

        self.assertTrue(result.success)
        self.assertEqual(result.total_amount, 60.00)
        self.assertEqual(result.formatted_total, "$60.00")
        self.assertEqual(result.total_confidence, "HIGH")
        self.assertTrue(len(result.raw_text) > 0)
        self.assertIn("60.00", result.raw_text)

    def test_scan_sample4_receipt(self):
        """Test capturing total amount from sample4.jpg ($200.00)."""
        self.assertTrue(os.path.exists(self.sample4_img))
        result = self.scanner.scan_receipt(self.sample4_img)

        self.assertTrue(result.success)
        self.assertEqual(result.total_amount, 200.00)
        self.assertEqual(result.formatted_total, "$200.00")
        self.assertEqual(result.total_confidence, "HIGH")
        self.assertIn("200.00", result.raw_text)

    def test_scan_sample6_receipt(self):
        """Test capturing total amount from sample6.jpg ($128.29)."""
        self.assertTrue(os.path.exists(self.sample6_img))
        result = self.scanner.scan_receipt(self.sample6_img)

        self.assertTrue(result.success)
        self.assertEqual(result.total_amount, 128.29)
        self.assertEqual(result.formatted_total, "$128.29")
        self.assertEqual(result.state, "Johor")

    def test_scan_multiple_and_grand_total(self):
        """Test scanning multiple receipts and computing Grand Total."""
        items = [
            ("sample2.jpg", self.sample2_img),
            ("sample4.jpg", self.sample4_img),
            ("sample6.jpg", self.sample6_img)
        ]
        results, grand_total = self.scanner.scan_multiple(items)
        self.assertEqual(len(results), 3)
        self.assertEqual(grand_total, 388.29)  # 60 + 200 + 128.29 = 388.29

    def test_raw_output_text_present(self):
        """Verify raw text is captured line by line."""
        result = self.scanner.scan_receipt(self.sample2_img)
        self.assertTrue(len(result.raw_text.splitlines()) > 5)
        self.assertTrue(len(result.lines) > 5)

    def test_state_extraction(self):
        """Verify Malaysia state extraction strictly matches the 16 allowed states."""
        allowed_states = {
            "Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan",
            "Pahang", "Penang", "Perak", "Perlis", "Selangor",
            "Terengganu", "Sabah", "Sarawak", "Kuala Lumpur", "Putrajaya", "Labuan"
        }

        # Test sample3 -> Kuala Lumpur
        res3 = self.scanner.scan_receipt(os.path.join(SAMPLES_DIR, "sample3.jpg"))
        self.assertEqual(res3.state, "Kuala Lumpur")
        self.assertIn(res3.state, allowed_states)

        # Test sample6 -> Johor
        res6 = self.scanner.scan_receipt(os.path.join(SAMPLES_DIR, "sample6.jpg"))
        self.assertEqual(res6.state, "Johor")
        self.assertIn(res6.state, allowed_states)

        # Test sample9 -> Perlis
        res9 = self.scanner.scan_receipt(os.path.join(SAMPLES_DIR, "sample9.jpg"))
        self.assertEqual(res9.state, "Perlis")
        self.assertIn(res9.state, allowed_states)

        # Test sample.jpg -> Selangor
        res_sel = self.scanner.scan_receipt(os.path.join(SAMPLES_DIR, "sample.jpg"))
        self.assertEqual(res_sel.state, "Selangor")
        self.assertIn(res_sel.state, allowed_states)


class TestFlaskWebApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_index_page(self):
        """Verify UI home page loads."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Fuel Receipt OCR Scanner", response.data)

    def test_scan_samples_batch_api(self):
        """Verify scan-samples batch endpoint returns list and Grand Total."""
        response = self.client.post("/api/scan-samples")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("receipts", data)
        self.assertIn("grand_total", data)
        self.assertTrue(data["grand_total"] > 0)
        self.assertTrue(data["receipt_count"] >= 5)

    def test_scan_upload_multiple_api(self):
        """Verify uploading multiple files in one request."""
        sample2_path = os.path.join(SAMPLES_DIR, "sample2.jpg")
        sample4_path = os.path.join(SAMPLES_DIR, "sample4.jpg")

        with open(sample2_path, "rb") as f1, open(sample4_path, "rb") as f2:
            data = {
                "files": [
                    (io.BytesIO(f1.read()), "sample2.jpg"),
                    (io.BytesIO(f2.read()), "sample4.jpg")
                ]
            }
            response = self.client.post("/api/scan", data=data, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 200)
        res_json = response.get_json()
        self.assertEqual(res_json["receipt_count"], 2)
        self.assertEqual(res_json["grand_total"], 260.00)  # 60.00 + 200.00


if __name__ == "__main__":
    unittest.main()

