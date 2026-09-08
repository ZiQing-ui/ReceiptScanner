"""
Fuel Receipt OCR Web Application
Interactive web interface for scanning fuel receipts, capturing total amount,
and inspecting raw OCR output text.
"""

import base64
import os
from typing import Optional
import cv2
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
import numpy as np

try:
    from receipt_scanner import FuelReceiptOCR, ReceiptScanResult
except ImportError:
    try:
        from .receipt_scanner import FuelReceiptOCR, ReceiptScanResult
    except ImportError:
        from src.receipt_scanner import FuelReceiptOCR, ReceiptScanResult

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
SAMPLES_DIR = os.path.join(PROJECT_ROOT, "samples")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
CORS(app)  # Enable Cross-Origin Resource Sharing for frontend integration (React, Next.js, Vue, etc.)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

scanner = FuelReceiptOCR()


def annotate_receipt_image(image_bytes: bytes, scan_result: ReceiptScanResult) -> Optional[str]:
    """Draw bounding boxes and highlight total amount line."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        orig_h, orig_w = img.shape[:2]
        target_w = 750
        scale = target_w / float(orig_w)
        target_h = int(orig_h * scale)
        annotated = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)

        for item in scan_result.lines:
            box = item.get("box")
            if not box or len(box) != 4:
                continue

            pts = []
            for pt in box:
                scaled_x = int(pt[0] * scale)
                scaled_y = int(pt[1] * scale)
                pts.append([scaled_x, scaled_y])
            pts = np.array(pts, np.int32).reshape((-1, 1, 2))

            text = item.get("text", "").upper()
            is_total_box = False

            if scan_result.total_line_raw and item.get("text") in scan_result.total_line_raw:
                is_total_box = True
            elif scan_result.formatted_total and scan_result.formatted_total in text:
                is_total_box = True
            elif scan_result.total_amount and f"{scan_result.total_amount:.2f}" in text and "TOTAL" in text:
                is_total_box = True

            if is_total_box:
                cv2.polylines(annotated, [pts], isClosed=True, color=(0, 230, 0), thickness=3)
                min_x = max(5, int(min(p[0][0] for p in pts)))
                min_y = max(20, int(min(p[0][1] for p in pts)) - 6)
                cv2.putText(annotated, f"TOTAL: {scan_result.formatted_total}", (min_x, min_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 0), 2, cv2.LINE_AA)
            else:
                cv2.polylines(annotated, [pts], isClosed=True, color=(200, 160, 40), thickness=1)

        _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
        b64_str = base64.b64encode(buffer).decode("utf-8")
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        app.logger.warning(f"Failed to annotate receipt image: {e}")
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/samples")
def list_samples():
    """List available sample fuel receipts."""
    samples = [
        {
            "id": "shell",
            "name": "Shell Gas Station",
            "description": "Standard receipt with single-line Total Sale ($48.43)",
            "filename": "receipt_shell.png"
        },
        {
            "id": "chevron",
            "name": "Chevron Gas Station",
            "description": "Receipt with subtotal, tax, and Total USD ($64.03)",
            "filename": "receipt_chevron.png"
        },
        {
            "id": "bp",
            "name": "BP Connect",
            "description": "Multi-line layout with Diesel & Total Due ($75.00)",
            "filename": "receipt_bp.png"
        }
    ]
    return jsonify(samples)


@app.route("/api/sample-image/<filename>")
def get_sample_image(filename):
    """Serve sample receipt image."""
    return send_from_directory(SAMPLES_DIR, filename)


@app.route("/api/scan", methods=["POST"])
def scan_uploaded_files():
    """Upload and scan one or multiple receipt images."""
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        uploaded_files = request.files.getlist("file")

    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ""):
        return jsonify({"error": "No files uploaded"}), 400

    receipts = []
    for file in uploaded_files:
        if file.filename == "":
            continue
        try:
            image_bytes = file.read()
            scan_result = scanner.scan_receipt(image_bytes, filename=file.filename)
            annotated_b64 = annotate_receipt_image(image_bytes, scan_result)

            res_dict = scan_result.to_dict()
            res_dict["annotated_image"] = annotated_b64
            receipts.append(res_dict)
        except Exception as e:
            app.logger.warning(f"Error scanning {file.filename}: {e}")
            receipts.append({
                "filename": file.filename,
                "success": False,
                "total_amount": None,
                "formatted_total": None,
                "total_confidence": "NOT FOUND",
                "total_detection_reason": f"Error scanning file: {str(e)}",
                "total_line_raw": None,
                "raw_text": "",
                "annotated_image": None,
                "engine_used": "none"
            })

    valid_totals = [r["total_amount"] for r in receipts if r["total_amount"] is not None]
    grand_total = round(sum(valid_totals), 2)

    return jsonify({
        "receipts": receipts,
        "receipt_count": len(receipts),
        "totals_found_count": len(valid_totals),
        "grand_total": grand_total,
        "formatted_grand_total": f"${grand_total:.2f}"
    })


@app.route("/api/scan-samples", methods=["POST"])
def scan_all_samples():
    """Scan all sample receipts available in samples directory."""
    supported_exts = (".png", ".jpg", ".jpeg", ".webp")
    sample_files = [f for f in os.listdir(SAMPLES_DIR) if f.lower().endswith(supported_exts)]
    sample_files.sort()

    receipts = []
    for fname in sample_files:
        path = os.path.join(SAMPLES_DIR, fname)
        try:
            with open(path, "rb") as f:
                image_bytes = f.read()
            scan_result = scanner.scan_receipt(image_bytes, filename=fname)
            annotated_b64 = annotate_receipt_image(image_bytes, scan_result)

            res_dict = scan_result.to_dict()
            res_dict["annotated_image"] = annotated_b64
            receipts.append(res_dict)
        except Exception as e:
            app.logger.warning(f"Error scanning sample {fname}: {e}")

    valid_totals = [r["total_amount"] for r in receipts if r["total_amount"] is not None]
    grand_total = round(sum(valid_totals), 2)

    return jsonify({
        "receipts": receipts,
        "receipt_count": len(receipts),
        "totals_found_count": len(valid_totals),
        "grand_total": grand_total,
        "formatted_grand_total": f"${grand_total:.2f}"
    })


@app.route("/api/scan-sample/<sample_id>", methods=["POST"])
def scan_sample(sample_id):
    """Scan an individual sample receipt."""
    sample_path = os.path.join(SAMPLES_DIR, sample_id)
    if not os.path.exists(sample_path):
        # Check if extension was omitted
        for ext in [".jpg", ".png", ".jpeg"]:
            candidate = os.path.join(SAMPLES_DIR, sample_id + ext)
            if os.path.exists(candidate):
                sample_path = candidate
                break

    if not os.path.exists(sample_path):
        return jsonify({"error": f"Sample '{sample_id}' not found"}), 404

    filename = os.path.basename(sample_path)
    with open(sample_path, "rb") as f:
        image_bytes = f.read()

    scan_result = scanner.scan_receipt(image_bytes, filename=filename)
    annotated_b64 = annotate_receipt_image(image_bytes, scan_result)

    res_dict = scan_result.to_dict()
    res_dict["annotated_image"] = annotated_b64

    grand_total = res_dict["total_amount"] or 0.0
    return jsonify({
        "receipts": [res_dict],
        "receipt_count": 1,
        "totals_found_count": 1 if res_dict["total_amount"] is not None else 0,
        "grand_total": grand_total,
        "formatted_grand_total": f"${grand_total:.2f}"
    })


if __name__ == "__main__":
    print("Starting Fuel Receipt OCR Scanner on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)

