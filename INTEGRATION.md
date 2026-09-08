# ReceiptScanner Integration Guide (for Frontend & TypeScript Developers)

This guide explains how to integrate the **Fuel Receipt OCR & Malaysian State Extraction Service** into a TypeScript/JavaScript frontend application (React, Next.js, Vue, Angular, or Vanilla TS).

---

## 1. Quick Start: Running the OCR Backend

The OCR engine runs as a lightweight REST API backend with **CORS enabled**.

### Option A: Local Python Environment
```bash
# 1. Clone or copy the repository
cd ReceiptScanner

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the API service (runs on http://127.0.0.1:5000)
python run.py
```

### Option B: Docker Container
```bash
# Build and run container
docker build -t receipt-scanner .
docker run -p 5000:5000 receipt-scanner
```

The API service will be accessible at:
```
http://127.0.0.1:5000
```

---

## 2. API Reference

### `POST /api/scan`
Uploads and processes one or more receipt images.

- **Content-Type**: `multipart/form-data`
- **Form Data Keys**:
  - `file`: A single receipt image file (or `files` for multiple images)
- **Supported Formats**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`

#### Success Response (`200 OK`)
```json
{
  "receipts": [
    {
      "filename": "sample.jpg",
      "success": true,
      "total_amount": 111.70,
      "formatted_total": "$111.70",
      "state": "Selangor",
      "total_confidence": "HIGH",
      "total_detection_reason": "Single-line regex match ('TOTAL: 111.70')",
      "total_line_raw": "TOTAL: 111.70",
      "raw_text": "PETRONAS\n...\nTOTAL: 111.70\nTHANK YOU",
      "annotated_image": "data:image/jpeg;base64,...",
      "engine_used": "RapidOCR"
    }
  ],
  "receipt_count": 1,
  "totals_found_count": 1,
  "grand_total": 111.70,
  "formatted_grand_total": "$111.70"
}
```

#### Field Descriptions:
| Field | Type | Description |
| :--- | :--- | :--- |
| `total_amount` | `number \| null` | Extracted numeric total amount (e.g. `111.70`). |
| `formatted_total` | `string \| null` | Formatted string (e.g. `"$111.70"`). |
| `state` | `string \| null` | Extracted Malaysian state/territory (one of the 16 official states). |
| `total_confidence` | `string` | `"HIGH"`, `"MEDIUM"`, `"LOW"`, or `"NOT FOUND"`. |
| `raw_text` | `string` | Complete raw text recognized by OCR, line by line. |
| `annotated_image` | `string \| null` | Base64 JPEG with bounding boxes around recognized text lines. |
| `grand_total` | `number` | Sum of all captured totals in the batch. |



---

## 3. TypeScript Client Implementation

Copy the following into your TypeScript codebase (e.g., `src/types/receipt.ts` and `src/services/receiptScanner.ts`).

### `types/receipt.ts`
```typescript
export type MalaysiaState =
  | "Johor"
  | "Kedah"
  | "Kelantan"
  | "Melaka"
  | "Negeri Sembilan"
  | "Pahang"
  | "Penang"
  | "Perak"
  | "Perlis"
  | "Selangor"
  | "Terengganu"
  | "Sabah"
  | "Sarawak"
  | "Kuala Lumpur"
  | "Putrajaya"
  | "Labuan";

export type TotalConfidence = "HIGH" | "MEDIUM" | "LOW" | "NOT FOUND";

export interface ReceiptItem {
  filename: string;
  success: boolean;
  total_amount: number | null;
  formatted_total: string | null;
  state: MalaysiaState | null;
  total_confidence: TotalConfidence;
  total_detection_reason?: string;
  total_line_raw?: string | null;
  raw_text: string;
  annotated_image?: string | null;
  engine_used: string;
}

export interface ScanApiResponse {
  receipts: ReceiptItem[];
  receipt_count: number;
  totals_found_count: number;
  grand_total: number;
  formatted_grand_total: string;
}
```

### `services/receiptScanner.ts`
```typescript
import { ScanApiResponse, ReceiptItem } from "../types/receipt";

const OCR_API_URL = process.env.NEXT_PUBLIC_OCR_API_URL || "http://127.0.0.1:5000";

/**
 * Scan a single receipt image
 */
export async function scanSingleReceipt(file: File): Promise<ReceiptItem> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${OCR_API_URL}/api/scan`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`OCR Scan failed (${response.status}): ${errorText}`);
  }

  const data: ScanApiResponse = await response.json();
  return data.receipts[0];
}

/**
 * Scan multiple receipt images in batch and calculate grand total
 */
export async function scanMultipleReceipts(files: File[]): Promise<ScanApiResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`${OCR_API_URL}/api/scan`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Batch scan failed (${response.status}): ${errorText}`);
  }

  return response.json();
}
```

---

## 4. Testing with `cURL`

```bash
# Scan single receipt
curl -X POST http://127.0.0.1:5000/api/scan -F "file=@samples/sample6.jpg"

# Scan multiple receipts
curl -X POST http://127.0.0.1:5000/api/scan \
  -F "files=@samples/sample.jpg" \
  -F "files=@samples/sample6.jpg"
```
