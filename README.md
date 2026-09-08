# Fuel Receipt OCR Scanner - Batch Processing, Grand Total & State Extraction

An OCR application designed specifically for scanning fuel receipts, capturing the **Total Amount** from individual receipts, extracting the **Malaysian State** of the petrol station location, displaying the **Raw OCR Output Text**, and summing all receipts to a **Grand Total**.

Additional fuel metadata (pump numbers, fuel grade, volume, rate, date/time, payment method) is excluded as requested.

---

## 🌟 Key Features

1. **Malaysian State of Petrol Station Extraction**:
   - Accurately identifies and maps the petrol station's location to strictly one of the 16 official Malaysian states / federal territories:
     - **Johor**, **Kedah**, **Kelantan**, **Melaka**, **Negeri Sembilan**, **Pahang**, **Penang**, **Perak**, **Perlis**, **Selangor**, **Terengganu**, **Sabah**, **Sarawak**, **Kuala Lumpur**, **Putrajaya**, **Labuan**
   - Handles addresses, districts, towns, postal codes, and common OCR abbreviations (e.g. `PETALING JAYA` / `SEL.` -> `Selangor`, `TANGKAK` -> `Johor`, `PADANG BESAR` -> `Perlis`, `SUNGAI BESI` -> `Kuala Lumpur`).

2. **Batch Multi-Image Upload & Scanning**:
   - Drag and drop or browse **multiple receipt images at once** (PNG, JPG, JPEG, WEBP).
   - Each receipt is analyzed individually with the deep learning OCR engine.
   - Quick one-click testing with bundled sample receipts.

3. **Grand Total Calculation**:
   - Automatically sums all individual receipt totals into a prominent **Grand Total** banner.
   - Displays receipt counts and capture statistics (e.g. `12 / 12 Totals Captured`).

4. **Individual Receipt Capture**:
   - Extracts the final receipt total (e.g. `$111.70`, `$60.00`, `$137.86`, `$200.00`, `$128.29`, `$69.30`).
   - Supports single-line totals, multi-line total layouts, and international receipt formats (RM, USD, $, etc.).
   - Distinguishes final totals from subtotals, pump numbers, taxes, and litres/gallons.

5. **Full Raw Output Text Display**:
   - Displays the exact line-by-line OCR transcription for every receipt.
   - Line counts, monospace formatting, and one-click **"Copy Raw Text"** for each individual receipt.
   - **Export All Data (JSON)** button to download all results.

6. **Dual OCR Engine**:
   - **RapidOCR (Default)**: Deep-learning ONNX PP-OCR model running locally offline; highly accurate across thermal fonts and low-contrast receipt paper.
   - **Windows.Media.Ocr (Fallback)**: Native offline Windows OCR engine.

---

## 🚀 Quick Start

### 1. Launch the Web Interface

```powershell
python run.py
```
Open your browser at **`http://127.0.0.1:5000`**.

- Drag & drop one or multiple fuel receipt images into the dropzone.
- Or click **"⚡ Scan All 5 Sample Receipts"** to run batch OCR immediately.
- View the **Grand Total** at the top and each receipt's captured total and raw text below!

---

### 2. Command-Line (CLI) Scanning

You can scan multiple receipts directly from the terminal:

```powershell
# Scan multiple images
python run.py samples/images.jpg samples/sample2.jpg samples/sample4.jpg

# Or scan an entire directory of receipts
python run.py samples
```

Sample CLI Output:
```text
=================================================================
              FUEL RECEIPT OCR SCANNER REPORT
=================================================================
File         : images.jpg
OCR Engine   : RapidOCR (ONNX)
Scan Status  : SUCCESS

-----------------------------------------------------------------
                     RAW OCR OUTPUT TEXT
-----------------------------------------------------------------
[01] SM SERVICE STATIOM S6
[02] PEIALINJAYA
...
[43] TOTAL
[44] RH111.70
...

-----------------------------------------------------------------
                   CAPTURED TOTAL AMOUNT
-----------------------------------------------------------------
TOTAL AMOUNT : $111.70  [Confidence: HIGH]
Detection    : Multi-line total ('TOTAL' followed by 'RH111.70')
Total Line   : "TOTAL -> RH111.70"
=================================================================

=================================================================
                     BATCH SCAN SUMMARY
=================================================================
Total Receipts Processed : 8
Totals Successfully Found: 8 of 8
GRAND TOTAL AMOUNT       : $914.74
=================================================================
```

---

### 3. Running the Test Suite

```powershell
python run.py --test
```
Runs the automated test suite verifying OCR accuracy, batch processing, and Grand Total summation.

---

## 📁 Project Structure

```text
Solution1/
├── run.py                          # Unified CLI and Web launcher
├── README.md                       # Documentation
├── src/
│   ├── receipt_scanner.py          # Core OCR engine & total extractor
│   ├── app.py                      # Flask web server & REST API
│   ├── templates/
│   │   └── index.html              # Batch Web UI template
│   └── static/
│       ├── style.css               # Styling & responsive design
│       └── app.js                  # Client logic & asynchronous fetch
├── samples/
│   ├── images.jpg                  # Sample receipt 1 (Total: $111.70)
│   ├── sample2.jpg                 # Sample receipt 2 (Total: $60.00)
│   ├── sample3.jpg                 # Sample receipt 3 (Total: $137.86)
│   ├── sample4.jpg                 # Sample receipt 4 (Total: $200.00)
│   ├── sample5.jpg                 # Sample receipt 5 (Total: $137.86)
│   └── sample6.jpg                 # Sample receipt 6 (Total: $128.29)
└── tests/
    └── test_scanner.py             # Test suite
```

