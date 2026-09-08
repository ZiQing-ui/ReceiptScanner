"""
Generate sample realistic fuel receipts for testing the OCR scanner.
"""

import os
from PIL import Image, ImageDraw, ImageFont


def create_receipt_image(lines, output_path, width=480, line_height=26, bg_color="#FDFEFE", text_color="#1A1A1A"):
    height = (len(lines) + 4) * line_height + 40
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Use default font or truetype if available
    try:
        font = ImageFont.truetype("arial.ttf", 18)
        font_bold = ImageFont.truetype("arialbd.ttf", 20)
        font_title = ImageFont.truetype("arialbd.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font
        font_title = font

    y = 30
    for line in lines:
        text = line.get("text", "")
        align = line.get("align", "left")
        is_bold = line.get("bold", False)
        is_title = line.get("title", False)
        active_font = font_title if is_title else (font_bold if is_bold else font)

        bbox = draw.textbbox((0, 0), text, font=active_font)
        text_w = bbox[2] - bbox[0]

        if align == "center":
            x = (width - text_w) // 2
        elif align == "right":
            x = width - text_w - 30
        else:
            x = 35

        draw.text((x, y), text, fill=text_color, font=active_font)
        y += line_height

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, dpi=(300, 300))
    print(f"Generated sample receipt at: {output_path}")


def main():
    samples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")

    # Sample 1: Shell
    shell_lines = [
        {"text": "SHELL OIL #14892", "align": "center", "title": True},
        {"text": "1040 S HIGHWAY 101", "align": "center"},
        {"text": "SAN DIEGO, CA 92101", "align": "center"},
        {"text": "TEL: (619) 555-0199", "align": "center"},
        {"text": "------------------------------------------", "align": "center"},
        {"text": "DATE: 10/12/2024      TIME: 14:35:10", "align": "left"},
        {"text": "TRANSACTION # 839218", "align": "left"},
        {"text": "PUMP # 04", "align": "left", "bold": True},
        {"text": "PRODUCT: REGULAR UNLEADED (87)", "align": "left"},
        {"text": "VOLUME: 13.842 GAL", "align": "left"},
        {"text": "PRICE/GAL: $3.499", "align": "left"},
        {"text": "------------------------------------------", "align": "center"},
        {"text": "TOTAL SALE: $48.43", "align": "left", "bold": True, "title": True},
        {"text": "------------------------------------------", "align": "center"},
        {"text": "PAYMENT METHOD: VISA", "align": "left"},
        {"text": "CARD: ************7234", "align": "left"},
        {"text": "AUTH CODE: 049182", "align": "left"},
        {"text": "THANK YOU FOR SHOPPING AT SHELL!", "align": "center"},
    ]
    create_receipt_image(shell_lines, os.path.join(samples_dir, "receipt_shell.png"))

    # Sample 2: Chevron
    chevron_lines = [
        {"text": "CHEVRON STATION 0987", "align": "center", "title": True},
        {"text": "450 NORTH TEMPLE ST", "align": "center"},
        {"text": "SALT LAKE CITY, UT", "align": "center"},
        {"text": "==========================================", "align": "center"},
        {"text": "DATE: 11/04/2024  16:20", "align": "left"},
        {"text": "PUMP 08", "align": "left", "bold": True},
        {"text": "FUEL: PREMIUM UNLEADED 93", "align": "left"},
        {"text": "GALLONS: 15.250 GAL", "align": "left"},
        {"text": "RATE: $4.199 / GAL", "align": "left"},
        {"text": "SUBTOTAL: $64.03", "align": "left"},
        {"text": "TAX: $0.00", "align": "left"},
        {"text": "TOTAL USD: $64.03", "align": "left", "bold": True, "title": True},
        {"text": "==========================================", "align": "center"},
        {"text": "MASTERCARD ************1049", "align": "left"},
        {"text": "APPROVED - CHIP READ", "align": "left"},
        {"text": "HAVE A SAFE JOURNEY!", "align": "center"},
    ]
    create_receipt_image(chevron_lines, os.path.join(samples_dir, "receipt_chevron.png"))

    # Sample 3: BP (Multi-line Total layout)
    bp_lines = [
        {"text": "BP CONNECT", "align": "center", "title": True},
        {"text": "STORE # 4310", "align": "center"},
        {"text": "CHICAGO, IL 60614", "align": "center"},
        {"text": "------------------------------------------", "align": "center"},
        {"text": "DATE: 08/14/2024   TIME: 11:23 AM", "align": "left"},
        {"text": "DISPENSER # 02", "align": "left", "bold": True},
        {"text": "FUEL GRADE: DIESEL #2", "align": "left"},
        {"text": "20.000 GAL @ $3.750 / GAL", "align": "left"},
        {"text": "------------------------------------------", "align": "center"},
        {"text": "TOTAL DUE", "align": "left", "bold": True},
        {"text": "$75.00", "align": "left", "bold": True, "title": True},
        {"text": "------------------------------------------", "align": "center"},
        {"text": "CASH TENDERED: $80.00", "align": "left"},
        {"text": "CHANGE DUE: $5.00", "align": "left"},
        {"text": "THANK YOU - COME AGAIN", "align": "center"},
    ]
    create_receipt_image(bp_lines, os.path.join(samples_dir, "receipt_bp.png"))


if __name__ == "__main__":
    main()
