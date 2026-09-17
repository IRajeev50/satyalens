import io
from dataclasses import dataclass
from PIL import Image, UnidentifiedImageError

ALLOWED = {"image/png", "image/jpeg", "image/webp"}
@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: str
    engine: str
    width: int
    height: int

def extract_screenshot(data: bytes, mime_type: str) -> OCRResult:
    if mime_type not in ALLOWED: raise ValueError("Only PNG, JPEG and WebP screenshots are accepted")
    try:
        im = Image.open(io.BytesIO(data)); im.verify()
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc: raise ValueError("Invalid image") from exc
    if im.width * im.height > 40_000_000: raise ValueError("Image dimensions are too large")
    try:
        import pytesseract
        details = pytesseract.image_to_data(im, lang="eng+hin", output_type=pytesseract.Output.DICT)
    except Exception as exc:
        raise RuntimeError("OCR unavailable. Install Tesseract with Hindi data or configure an OCR provider.") from exc
    words=[]; conf=[]
    for word, score in zip(details.get("text",[]), details.get("conf",[])):
        if word.strip():
            words.append(word.strip())
            try:
                n=float(score)
                if n >= 0: conf.append(n)
            except (TypeError,ValueError): pass
    text=" ".join(words)
    if not text: raise ValueError("No text could be read from the screenshot")
    avg=sum(conf)/len(conf) if conf else 0
    band="High" if avg>=85 else "Moderate" if avg>=60 else "Low"
    return OCRResult(text, band, "tesseract-eng+hin", im.width, im.height)
