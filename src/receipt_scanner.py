"""
Fuel Receipt OCR Scanner
Extracts raw OCR text, detects fuel receipt metadata, and captures the total amount.
Supports RapidOCR (default ONNX engine) and Windows.Media.Ocr (winocr) fallback.
"""

from dataclasses import asdict, dataclass, field
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("receipt_scanner")


@dataclass
class OCRLine:
    text: str
    confidence: float
    box: Optional[List[List[float]]] = None
    y_center: float = 0.0
    x_left: float = 0.0


@dataclass
class ReceiptScanResult:
    filename: str = ""
    success: bool = False
    total_amount: Optional[float] = None
    formatted_total: Optional[str] = None
    total_confidence: str = "NOT FOUND"  # "HIGH", "MEDIUM", "LOW", "NOT FOUND"
    total_detection_reason: str = ""
    total_line_raw: Optional[str] = None
    state: Optional[str] = None
    raw_text: str = ""
    lines: List[Dict[str, Any]] = field(default_factory=list)
    engine_used: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FuelReceiptOCR:
    """OCR Engine and Fuel Receipt Parser."""

    KNOWN_STATIONS = [
        "SHELL", "CHEVRON", "EXXON", "MOBIL", "TEXACO", "SPEEDWAY",
        "SUNOCO", "7-ELEVEN", "7 ELEVEN", "CIRCLE K", "MARATHON",
        "PHILLIPS 66", "VALERO", "COSTCO", "SAM'S CLUB", "SAMS CLUB",
        "CASEY'S", "CASEYS", "WAWA", "BUC-EE'S", "BUCEES", "LOVE'S", "LOVES",
        "PILOT", "FLYING J", "QUIKTRIP", "MURPHY USA", "ARCO", "SINCLAIR",
        "CITGO", "RACETRAC", "KUM & GO", "KROGER", "SHEETZ", "GULF", "ESSO",
        "PETRO-CANADA", "CALTEX", "BP CONNECT", "BP", "REPSOL", "ENI",
        "TOTAL ENERGIES", "TOTAL OIL"
    ]

    FUEL_GRADES = [
        "REGULAR UNLEADED", "UNLEADED REGULAR", "UNLEADED PLUS", "PREMIUM UNLEADED",
        "REGULAR", "PLUS", "MIDGRADE", "PREMIUM", "SUPER", "SUPREME", "ULTRA",
        "V-POWER", "DIESEL #2", "DIESEL #1", "DIESEL", "ULTRA LOW SULFUR DIESEL",
        "ULSD", "E-85", "E85", "BIODIESEL", "87 UNL", "89 MID", "91 PREM", "93 PREM",
        "87 REG", "87", "89", "91", "93"
    ]

    def __init__(self, preferred_engine: str = "auto"):
        self.preferred_engine = preferred_engine
        self._rapid_ocr = None
        self._winocr_available = False
        self._init_engines()

    def _init_engines(self):
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._rapid_ocr = RapidOCR()
            logger.info("RapidOCR initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize RapidOCR: {e}")

        try:
            import winocr
            self._winocr_available = True
            logger.info("winocr initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize winocr: {e}")

    @staticmethod
    def preprocess_image(image_input: Union[str, bytes, np.ndarray, Image.Image]) -> np.ndarray:
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image not found at path: {image_input}")
            img = cv2.imread(image_input)
            if img is None:
                pil_img = Image.open(image_input).convert("RGB")
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, Image.Image):
            rgb_img = image_input.convert("RGB")
            img = cv2.cvtColor(np.array(rgb_img), cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, np.ndarray):
            img = image_input.copy()
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        if img is None or img.size == 0:
            raise ValueError("Failed to load or decode image.")

        h, w = img.shape[:2]
        if w < 700:
            scale = 700 / float(w)
            new_w = 700
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        elif w > 2400:
            scale = 2400 / float(w)
            new_w = 2400
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        return img

    def _run_rapidocr(self, img_bgr: np.ndarray) -> List[OCRLine]:
        """Execute RapidOCR and parse lines with coordinates."""
        raw_result, _ = self._rapid_ocr(img_bgr)
        if not raw_result:
            return []

        lines: List[OCRLine] = []
        for item in raw_result:
            box = item[0]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            text = str(item[1]).strip()
            score = float(item[2])
            if not text:
                continue

            y_coords = [p[1] for p in box]
            x_coords = [p[0] for p in box]
            y_center = sum(y_coords) / len(y_coords)
            x_left = min(x_coords)

            lines.append(OCRLine(
                text=text,
                confidence=score,
                box=box,
                y_center=y_center,
                x_left=x_left
            ))

        # Sort lines top to bottom, then left to right
        lines.sort(key=lambda l: (round(l.y_center / 15.0), l.x_left))
        return lines

    def _run_winocr(self, img_bgr: np.ndarray) -> List[OCRLine]:
        """Execute Windows.Media.Ocr fallback."""
        import winocr
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        result = winocr.recognize_pil_sync(pil_img)
        lines: List[OCRLine] = []

        raw_lines = result.get("lines", [])
        for line_item in raw_lines:
            text = line_item.get("text", "").strip()
            if not text:
                continue
            words = line_item.get("words", [])
            if words:
                first_rect = words[0].get("bounding_rect", {})
                x = first_rect.get("x", 0.0)
                y = first_rect.get("y", 0.0)
                h = first_rect.get("height", 10.0)
                w = first_rect.get("width", 20.0)
                box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                y_center = y + (h / 2.0)
                x_left = x
            else:
                box = None
                y_center = 0.0
                x_left = 0.0

            lines.append(OCRLine(
                text=text,
                confidence=0.90,
                box=box,
                y_center=y_center,
                x_left=x_left
            ))

        lines.sort(key=lambda l: (round(l.y_center / 15.0), l.x_left))
        return lines

    def ocr_image(self, img_bgr: np.ndarray) -> Tuple[List[OCRLine], str]:
        """Run available OCR engine."""
        engine_used = "none"
        lines: List[OCRLine] = []

        if self.preferred_engine != "winocr" and self._rapid_ocr is not None:
            try:
                lines = self._run_rapidocr(img_bgr)
                engine_used = "RapidOCR (ONNX)"
            except Exception as e:
                logger.warning(f"RapidOCR execution failed: {e}")

        if not lines and self._winocr_available:
            try:
                lines = self._run_winocr(img_bgr)
                engine_used = "Windows.Media.Ocr"
            except Exception as e:
                logger.error(f"WinOCR execution failed: {e}")

        return lines, engine_used

    def scan_receipt(
        self,
        image_input: Union[str, bytes, np.ndarray, Image.Image],
        filename: str = ""
    ) -> ReceiptScanResult:
        """
        Scan individual fuel receipt:
        1. Preprocess image.
        2. Perform OCR and extract raw text.
        3. Capture total amount.
        """
        if not filename and isinstance(image_input, str):
            filename = os.path.basename(image_input)

        try:
            img = self.preprocess_image(image_input)
        except Exception as e:
            return ReceiptScanResult(
                filename=filename,
                success=False,
                total_amount=None,
                formatted_total=None,
                total_confidence="NOT FOUND",
                total_detection_reason=f"Failed to load image: {str(e)}",
                total_line_raw=None,
                raw_text="",
                lines=[],
                engine_used="none"
            )

        lines, engine_used = self.ocr_image(img)

        # Build clean raw text representation
        raw_lines_text = [line.text for line in lines]
        raw_text = "\n".join(raw_lines_text)

        # Extract Malaysian state of the petrol station location
        state = self._extract_state(raw_lines_text)

        # Estimate expected total if volume & rate are visible
        expected_total = self._estimate_expected_total(raw_lines_text)

        # Capture total amount
        total_amount, confidence, reason, total_line = self._extract_total_amount(
            raw_lines_text, lines, expected_total
        )

        formatted_total = f"${total_amount:.2f}" if total_amount is not None else None

        serializable_lines = [
            {
                "text": line.text,
                "confidence": round(line.confidence, 3),
                "box": line.box,
                "y_center": round(line.y_center, 1)
            }
            for line in lines
        ]

        return ReceiptScanResult(
            filename=filename,
            success=(total_amount is not None or len(raw_text.strip()) > 0),
            total_amount=total_amount,
            formatted_total=formatted_total,
            total_confidence=confidence,
            total_detection_reason=reason,
            total_line_raw=total_line,
            state=state,
            raw_text=raw_text,
            lines=serializable_lines,
            engine_used=engine_used
        )

    MALAYSIA_STATES = [
        "Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan",
        "Pahang", "Penang", "Perak", "Perlis", "Selangor",
        "Terengganu", "Sabah", "Sarawak", "Kuala Lumpur", "Putrajaya", "Labuan"
    ]

    STATE_MAPPINGS = {
        "Johor": [
            r"\bJOHOR\b", r"\bJOHORE\b", r"\bTANGKAK\b", r"\bJOHOR\s*BAHRU\b",
            r"\bBATU\s*PAHAT\b", r"\bMUAR\b", r"\bKLUANG\b", r"\bKULAI\b",
            r"\bPASIR\s*GUDANG\b", r"\bSEGAMAT\b", r"\b8[0-6]\d{3}\b", r"\b849[0O]{2}\b"
        ],
        "Kedah": [
            r"\bKEDAH\b", r"\bALOR\s*SETAR\b", r"\bSUNGAI\s*PETANI\b", r"\bKULIM\b",
            r"\bLANGKAWI\b", r"\b0[5-9]\d{3}\b"
        ],
        "Kelantan": [
            r"\bKELANTAN\b", r"\bKOTA\s*BHARU\b", r"\b1[5-8]\d{3}\b"
        ],
        "Melaka": [
            r"\bMELAKA\b", r"\bMALACCA\b", r"\bAYER\s*KEROH\b", r"\b7[5-8]\d{3}\b"
        ],
        "Negeri Sembilan": [
            r"\bNEGERI\s*SEMBILAN\b", r"\bN\.?\s*SEMBILAN\b", r"\bSEREMBAN\b",
            r"\bPORT\s*DICKSON\b", r"\bNILAI\b", r"\bSENAWANG\b", r"\b7[0-3]\d{3}\b"
        ],
        "Pahang": [
            r"\bPAHANG\b", r"\bKUANTAN\b", r"\bTEMERLOH\b", r"\bBENTONG\b", r"\b2[5-8]\d{3}\b"
        ],
        "Penang": [
            r"\bPENANG\b", r"\bPULAU\s*PINANG\b", r"\bGEORGE\s*TOWN\b",
            r"\bBUTTERWORTH\b", r"\bBAYAN\s*LEPAS\b", r"\b1[0-4]\d{3}\b"
        ],
        "Perak": [
            r"\bPERAK\b", r"\bIPOH\b", r"\bTAIPING\b", r"\bTELUK\s*INTAN\b", r"\b3[0-6]\d{3}\b"
        ],
        "Perlis": [
            r"\bPERLIS\b", r"\bPADANG\s*BESAR\b", r"\bKANGAR\b", r"\b0[1-2]\d{3}\b"
        ],
        "Selangor": [
            r"\bSELANGOR\b", r"\bSEL\.\b", r"\bSLAGOR\b", r"\bSHAH\s*ALAM\b",
            r"\bSHAHALA\b", r"\bPETALING\s*JAYA\b", r"\bPEIALINJAYA\b", r"\bKLANG\b",
            r"\bSUBANG\b", r"\bDAMANSARA\b", r"\bPUCHONG\b", r"\bSUNWAY\b",
            r"\bBANDAR\s*SUNWAY\b", r"\bKANACAPURAM\b", r"\bHUKIM\s*PETALING\b",
            r"\b4[0-8]\d{3}\b", r"4740SA", r"4GBB0"
        ],
        "Terengganu": [
            r"\bTERENGGANU\b", r"\bTRENGGANU\b", r"\bKUALA\s*TERENGGANU\b",
            r"\bKEMAMAN\b", r"\b2[0-4]\d{3}\b"
        ],
        "Sabah": [
            r"\bSABAH\b", r"\bKOTA\s*KINABALU\b", r"\bSANDAKAN\b", r"\bTAWAU\b",
            r"\b8[8-9]\d{3}\b", r"\b9[0-1]\d{3}\b"
        ],
        "Sarawak": [
            r"\bSARAWAK\b", r"\bKUCHING\b", r"\bMIRI\b", r"\bSIBU\b", r"\bBINTULU\b",
            r"\b9[3-8]\d{3}\b"
        ],
        "Kuala Lumpur": [
            r"\bKUALA\s*LUMPUR\b", r"\bSUNCAI\s*BESI\b", r"\bSUNGAI\s*BESI\b",
            r"\bKL\b", r"\bCHERAS\b", r"\bKEPONG\b", r"\bBANGSAR\b", r"\b5\d{4}\b",
            r"\b60\d{3}\b"
        ],
        "Putrajaya": [
            r"\bPUTRAJAYA\b", r"\b62\d{3}\b"
        ],
        "Labuan": [
            r"\bLABUAN\b", r"\b87\d{3}\b"
        ]
    }

    def _extract_state(self, text_lines: List[str]) -> Optional[str]:
        """
        Extract the Malaysian state of the petrol station location only.
        Matches against the 16 official states/federal territories of Malaysia.
        """
        header_text = " ".join(text_lines[:15]).upper()

        # Priority 1: Check explicit canonical state names (flexible whitespace & fused text)
        for state in self.MALAYSIA_STATES:
            tokens = [re.escape(p) for p in state.upper().split()]
            pat = r"\s*".join(tokens) + r"\b"
            if re.search(pat, header_text):
                return state

        # Priority 2: Check town/district/postcode patterns mapped to state
        for state, patterns in self.STATE_MAPPINGS.items():
            for pat in patterns:
                if re.search(pat, header_text):
                    return state

        return None

    def _estimate_expected_total(self, text_lines: List[str]) -> Optional[float]:
        """Internal helper: computes expected total from fuel volume * rate to assist accuracy."""
        full_text_upper = "\n".join(text_lines).upper()

        volume = None
        for pat in [
            r'(\d{1,3}\.\d{2,4})\s*(?:GAL|GALS|GALLON|GALLONS|GAL\b|G\b)',
            r'(?:GALLONS|VOLUME|QTY|QUANTITY|GALS)[:\s]+(\d{1,3}\.\d{2,4})',
            r'(\d{1,3}\.\d{2,4})\s*(?:LTR|LITRES|LITERS|\bL\b)',
            r'(?:LITRES|LITERS)[:\s]+(\d{1,3}\.\d{2,4})'
        ]:
            m = re.search(pat, full_text_upper)
            if m:
                try:
                    volume = float(m.group(1))
                    break
                except ValueError:
                    pass

        unit_price = None
        for pat in [
            r'(?:PRICE\/GAL|PRICE\/G|P\/G|PRICE\/L|RATE)[:\s]*\$?\s*(\d{1,2}\.\d{2,3})',
            r'@\s*\$?\s*(\d{1,2}\.\d{2,3})\s*(?:\/|\s*PER\s*)?(?:GAL|G|L|LTR)?',
            r'\$?\s*(\d{1,2}\.\d{2,3})\s*\/\s*(?:GAL|G|L|LTR)\b'
        ]:
            m = re.search(pat, full_text_upper)
            if m:
                try:
                    p = float(m.group(1))
                    if 0.50 <= p <= 15.00:
                        unit_price = p
                        break
                except ValueError:
                    pass

        if volume and unit_price:
            return round(volume * unit_price, 2)
        return None

    def _extract_total_amount(
        self,
        text_lines: List[str],
        lines: List[OCRLine],
        expected_total: Optional[float] = None
    ) -> Tuple[Optional[float], str, str, Optional[str]]:
        TOTAL_KEYWORDS = [
            r'GRAND\s*TOTAL',
            r'TOTAL\s*NET',
            r'NET\s*TOTAL',
            r'TOTAL\s*SALE',
            r'TOTAL\s*USD',
            r'TOTAL\s*RM',
            r'TOTAL\s*CAD',
            r'TOTAL\s*EUR',
            r'TOTAL\s*DUE',
            r'BALANCE\s*DUE',
            r'BAL\s*DUE',
            r'AMOUNT\s*PAID',
            r'FINAL\s*TOTAL',
            r'TOTAL\s*AMOUNT',
            r'SALE\s*TOTAL',
            r'TOTAL\s*:',
            r'TOTAL\s*\$',
            r'\bTOTAL\b'
        ]

        def clean_amount_str(raw_str: str) -> Optional[float]:
            cleaned = raw_str.strip().replace('$', '').replace('RM', '').replace('RH', '').replace(' ', '')
            # Replace OCR typo ':' with '.' e.g. 111:70 -> 111.70
            cleaned = cleaned.replace(':', '.')
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned and len(cleaned.split(',')[-1]) == 2:
                cleaned = cleaned.replace(',', '.')
            try:
                val = float(cleaned)
                if 0.50 <= val <= 3500.00:
                    return val
            except ValueError:
                pass
            return None

        candidates = []

        # Strategy 1: Same-line Total Keyword Match
        for idx, line in enumerate(text_lines):
            line_upper = line.upper()
            if any(re.search(ex, line_upper) for ex in [r'\bSUBTOTAL\b', r'\bSUB\s+TOTAL\b']):
                continue

            for pattern in TOTAL_KEYWORDS:
                match = re.search(pattern, line_upper)
                if match:
                    # Ignore lines that are volume measurements like "(30.150L)" or "30.150L"
                    if re.search(r'\b\d+\.\d+\s*(?:L|LTR|GAL|GALS)\b|\(\d+\.\d+\s*L\)', line_upper):
                        continue

                    amounts = re.findall(r'(?:RM|RH|\$|USD|CAD)?\s*([0-9]{1,4}(?:[,\.:][0-9]{2}))', line_upper)
                    for amt_str in amounts:
                        val = clean_amount_str(amt_str)
                        if val is not None:
                            weight = 100
                            if "GRAND" in line_upper:
                                weight += 60
                            if any(k in line_upper.replace(" ", "") for k in ["TOTALSALE", "TOTALDUE", "TOTALUSD", "TOTALRM", "BALANCE"]):
                                weight += 40
                            if any(c in line_upper for c in ["$", "RM", "RH", "USD"]):
                                weight += 15
                            if expected_total and abs(val - expected_total) <= 0.05:
                                weight += 50

                            candidates.append({
                                "value": val,
                                "weight": weight,
                                "line_idx": idx,
                                "line_text": line,
                                "reason": f"Matched keyword '{pattern}' on line: '{line}'"
                            })

        # Strategy 2: Two-line Total (e.g. "GRAND TOTAL" / "TOTAL" on line N, amount on line N+1 or N-1)
        for idx, line in enumerate(text_lines):
            line_upper = line.upper().strip()
            if re.fullmatch(r'(?:GRAND\s*TOTAL|TOTAL\s*NET|NET\s*TOTAL|TOTAL|TOTAL\s*DUE|TOTAL\s*SALE|TOTAL\s*USD|TOTAL\s*RM|BALANCE\s*DUE|AMOUNT\s*PAID|AMOUNT|TOTAL\s*AMOUNT)[:\s]*', line_upper):
                for offset in [1, 2, -1]:
                    target_idx = idx + offset
                    if 0 <= target_idx < len(text_lines):
                        next_line = text_lines[target_idx].strip()
                        next_upper = next_line.upper()
                        # Ignore volume lines or time lines
                        if re.search(r'\b\d+\.\d+\s*(?:L|LTR|GAL|GALS)\b|\(\d+\.\d+\s*L\)', next_upper):
                            continue
                        if re.search(r'\b(?:TIME|DATE|PUMP|INVOICE)\b', next_upper):
                            continue

                        amt_match = re.search(r'(?:RM|RH|\$|USD)?\s*([0-9]{1,4}(?:[,\.:][0-9]{2}))', next_upper)
                        if amt_match:
                            val = clean_amount_str(amt_match.group(1))
                            if val is not None:
                                weight = 110
                                if "GRAND" in line_upper or "TOTALNET" in line_upper.replace(" ", ""):
                                    weight += 60
                                if expected_total and abs(val - expected_total) <= 0.05:
                                    weight += 50
                                candidates.append({
                                    "value": val,
                                    "weight": weight,
                                    "line_idx": target_idx,
                                    "line_text": f"{line} -> {next_line}",
                                    "reason": f"Multi-line total ('{line}' and '{next_line}')"
                                })
                                break

        # Strategy 3: Math match among all numbers
        if expected_total:
            for idx, line in enumerate(text_lines):
                line_upper = line.upper()
                amounts = re.findall(r'([0-9]{1,4}(?:[,\.][0-9]{2}))', line)
                for amt_str in amounts:
                    val = clean_amount_str(amt_str)
                    if val is not None and abs(val - expected_total) <= 0.05:
                        is_subtotal = ("SUBTOTAL" in line_upper) or ("SUB TOTAL" in line_upper)
                        if is_subtotal:
                            weight = 60
                        elif "TOTAL" in line_upper:
                            weight = 180
                        else:
                            weight = 130
                        candidates.append({
                            "value": val,
                            "weight": weight,
                            "line_idx": idx,
                            "line_text": line,
                            "reason": f"Math verified (Volume x Rate = ${expected_total:.2f})"
                        })

        if candidates:
            candidates.sort(key=lambda c: c["weight"], reverse=True)
            best = candidates[0]
            confidence = "HIGH" if best["weight"] >= 100 else "MEDIUM"
            return best["value"], confidence, best["reason"], best["line_text"]

        # Strategy 4: Fallback largest dollar amount
        fallback_candidates = []
        for idx, line in enumerate(text_lines):
            line_upper = line.upper()
            if any(re.search(ex, line_upper) for ex in [r'\b\d{1,2}[\/\-]\d{1,2}\b', r'\*{4}', r'PUMP']):
                continue
            amounts = re.findall(r'(?:\$)?\s*([0-9]{1,4}\.[0-9]{2})\b', line)
            for amt_str in amounts:
                val = clean_amount_str(amt_str)
                if val is not None:
                    fallback_candidates.append((val, line))

        if fallback_candidates:
            fallback_candidates.sort(key=lambda x: x[0], reverse=True)
            val, line = fallback_candidates[0]
            return val, "LOW", f"Extracted as largest monetary amount (line: '{line}')", line

        return None, "NOT FOUND", "No total amount pattern could be identified.", None

    def scan_multiple(
        self,
        image_inputs: List[Tuple[str, Union[str, bytes]]]
    ) -> Tuple[List[ReceiptScanResult], float]:
        """
        Scan multiple receipts, extracting total from each and computing Grand Total.
        """
        results = []
        for name, img_input in image_inputs:
            res = self.scan_receipt(img_input, filename=name)
            results.append(res)

        grand_total = round(sum(r.total_amount for r in results if r.total_amount is not None), 2)
        return results, grand_total


def print_receipt_scan_report(result: ReceiptScanResult, image_path: str = ""):
    """Format and print a terminal report showing raw output text and captured total amount."""
    separator = "=" * 65
    sub_sep = "-" * 65

    print(separator)
    print("              FUEL RECEIPT OCR SCANNER REPORT")
    print(separator)
    filepath = image_path or result.filename
    if filepath:
        print(f"File         : {filepath}")
    if result.state:
        print(f"State        : {result.state}")
    print(f"OCR Engine   : {result.engine_used}")
    print(f"Scan Status  : {'SUCCESS' if result.success else 'FAILED'}")

    print("\n" + sub_sep)
    print("                     RAW OCR OUTPUT TEXT")
    print(sub_sep)
    if result.raw_text.strip():
        for i, line in enumerate(result.raw_text.splitlines(), start=1):
            print(f"[{i:02d}] {line}")
    else:
        print("(No text recognized)")

    print("\n" + sub_sep)
    print("                   CAPTURED TOTAL AMOUNT")
    print(sub_sep)
    print(f"TOTAL AMOUNT : {result.formatted_total or 'NOT DETECTED'}  [Confidence: {result.total_confidence}]")
    print(f"Detection    : {result.total_detection_reason}")
    if result.total_line_raw:
        print(f"Total Line   : \"{result.total_line_raw}\"")
    print(separator)


def print_batch_receipt_scan_report(results: List[ReceiptScanResult]):
    """Format and print multiple receipts and the aggregated Grand Total."""
    for res in results:
        print_receipt_scan_report(res)
        print()

    grand_total = sum(r.total_amount for r in results if r.total_amount is not None)
    count = len(results)
    found_count = sum(1 for r in results if r.total_amount is not None)

    summary_sep = "=" * 65
    print(summary_sep)
    print("                     BATCH SCAN SUMMARY")
    print(summary_sep)
    print(f"Total Receipts Processed : {count}")
    print(f"Totals Successfully Found: {found_count} of {count}")
    print(f"GRAND TOTAL AMOUNT       : ${grand_total:.2f}")
    print(summary_sep)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        scanner = FuelReceiptOCR()
        paths = sys.argv[1:]
        if len(paths) == 1:
            res = scanner.scan_receipt(paths[0])
            print_receipt_scan_report(res, paths[0])
        else:
            image_inputs = [(os.path.basename(p), p) for p in paths]
            results, grand_total = scanner.scan_multiple(image_inputs)
            print_batch_receipt_scan_report(results)
    else:
        print("Usage: python receipt_scanner.py <receipt_1> [receipt_2 ...]")



