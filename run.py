"""
Fuel Receipt OCR Scanner - Unified Launcher
Run web server, scan images via CLI, or run test suite.
"""

import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_DIR)


def main():
    parser = argparse.ArgumentParser(
        description="Fuel Receipt OCR Scanner - Extract Receipts, Totals & Grand Total"
    )
    parser.add_argument(
        "images",
        nargs="*",
        default=[],
        help="Path(s) to receipt images or directory of receipts to scan via CLI"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the interactive Web UI (default if no images specified)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Web server host (default: 127.0.0.1; use 0.0.0.0 for Docker/remote)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Web server port (default: 5000)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the automated test suite"
    )
    parser.add_argument(
        "--generate-samples",
        action="store_true",
        help="Generate synthetic sample receipts in samples/"
    )

    args = parser.parse_args()

    if args.generate_samples:
        from samples.generate_sample_receipts import main as gen_main
        gen_main()
        return

    if args.test:
        import unittest
        suite = unittest.defaultTestLoader.discover(os.path.join(BASE_DIR, "tests"))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)

    if args.images:
        from receipt_scanner import (
            FuelReceiptOCR,
            print_batch_receipt_scan_report,
            print_receipt_scan_report,
        )
        scanner = FuelReceiptOCR()

        # Collect image files (expanding directories if passed)
        supported_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
        collected_files = []
        for item in args.images:
            if os.path.isdir(item):
                for f in sorted(os.listdir(item)):
                    if f.lower().endswith(supported_exts):
                        collected_files.append(os.path.join(item, f))
            elif os.path.isfile(item):
                collected_files.append(item)
            else:
                print(f"Warning: File or path not found: {item}")

        if not collected_files:
            print("No valid receipt images found.")
            sys.exit(1)

        if len(collected_files) == 1:
            res = scanner.scan_receipt(collected_files[0])
            print_receipt_scan_report(res, collected_files[0])
        else:
            image_inputs = [(os.path.basename(p), p) for p in collected_files]
            results, grand_total = scanner.scan_multiple(image_inputs)
            print_batch_receipt_scan_report(results)
        return

    # Default: launch Web UI / REST API
    from app import app
    print("\n=======================================================")
    print(" Fuel Receipt OCR Scanner Web & API Service running at:")
    print(f" http://{args.host}:{args.port}")
    print(" Press Ctrl+C to stop.")
    print("=======================================================\n")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
