from pathlib import Path
from paddleocr import PaddleOCR

BASE_DIR = Path(__file__).resolve().parents[2]   # -> Capturing_backend/
IMAGE = BASE_DIR / "images" / "sample.jpg"

ocr = PaddleOCR(lang="en")

result = ocr.predict(str(IMAGE))

for res in result:
    res.print()