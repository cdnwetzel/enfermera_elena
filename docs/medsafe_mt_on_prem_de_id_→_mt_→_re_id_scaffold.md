# MedsafeMT – On‑Prem De‑ID → MT → Re‑ID Scaffold (Updated for Mixed Medical PDFs)

Pipeline adapted for **87‑page mixed medical PDFs**: original born‑digital PDFs, scanned printouts, scanned forms, written forms, stamps, and signatures. We will:
- Extract text from **born‑digital PDFs** directly.
- Apply **OCR only on printed/printed‑and‑scanned text**.
- **Skip handwriting and stamps** (treated as noise).

---

## Updated Repository layout
```
medsafe-mt/
├─ pyproject.toml
├─ README.md
├─ cli.py
├─ examples/
│  ├─ config.sample.yaml
│  ├─ glossary_med_en.csv
│  └─ sample_mixed_medical.pdf
├─ src/medsafe_mt/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ pipeline.py
│  ├─ utils/
│  │  ├─ logging.py
│  │  ├─ io.py
│  │  └─ normalize.py
│  ├─ pdf/
│  │  ├─ extractor.py      # Born-digital text extraction
│  │  ├─ classifier.py     # Classify page type (digital vs scanned)
│  │  └─ writer.py
│  ├─ ocr/
│  │  ├─ base.py
│  │  ├─ tesseract.py
│  │  └─ filters.py        # Skip handwriting/stamps regions
│  ├─ deid/
│  │  ├─ base.py
│  │  ├─ rules_es.py
│  │  └─ placeholder.py
│  ├─ mt/
│  │  ├─ base.py
│  │  ├─ glossary.py
│  │  └─ transformers_stub.py
│  ├─ reid/
│  │  ├─ reinserter.py
│  │  └─ localization.py
│  └─ qa/
│     ├─ validator.py
│     └─ termcheck.py
└─ tests/
   ├─ test_placeholder_roundtrip.py
   ├─ test_deid_rules.py
   └─ test_qa_validators.py
```

---

## New/Updated Components

### src/medsafe_mt/pdf/classifier.py
Detect whether a page is born‑digital or scanned.
```python
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox
from typing import List

def classify_pages(path: str, max_pages: int = 1000) -> List[str]:
    """
    Return list of page types: "digital" or "scanned".
    Heuristic: if PDFMiner can extract >50 chars of text, it's digital.
    """
    types = []
    with open(path, 'rb') as f:
        for i, page in enumerate(PDFPage.get_pages(f)):
            if i >= max_pages:
                break
            rsrc = PDFResourceManager()
            laparams = LAParams()
            device = PDFPageAggregator(rsrc, laparams=laparams)
            interp = PDFPageInterpreter(rsrc, device)
            interp.process_page(page)
            layout = device.get_result()
            text = "".join([obj.get_text() for obj in layout if isinstance(obj, LTTextBox)])
            if len(text.strip()) > 50:
                types.append("digital")
            else:
                types.append("scanned")
    return types
```

### src/medsafe_mt/ocr/filters.py
Skip handwriting and stamps (approximate: ignore non‑text blocks, color blobs).
```python
import cv2
import numpy as np
from PIL import Image


def mask_non_print_regions(img: Image.Image) -> Image.Image:
    """
    Approx heuristic: keep black/grey printed text, drop colorful or thick pen strokes.
    - Convert to grayscale.
    - Threshold: keep dark thin strokes (likely printed text).
    - Dilated blobs (stamps/signatures) filtered out.
    """
    arr = np.array(img.convert("L"))
    _, binary = cv2.threshold(arr, 180, 255, cv2.THRESH_BINARY_INV)
    # Remove big blobs (likely handwriting/stamps)
    nb_components, output, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    mask = np.zeros(binary.shape, dtype=np.uint8)
    for i in range(1, nb_components):
        area = stats[i, cv2.CC_STAT_AREA]
        if 10 < area < 2000:  # heuristics: printed text size
            mask[output == i] = 255
    result = Image.fromarray(mask)
    return result
```

### Updated OCR (tesseract.py)
Use filters to skip handwriting/stamps.
```python
from .base import OCREngine
import pytesseract
from pdf2image import convert_from_path
from .filters import mask_non_print_regions
from typing import Optional

class TesseractOCREngine(OCREngine):
    def ocr_pdf(self, path: str, language: str, dpi: int, max_pages: Optional[int] = None) -> str:
        pages = convert_from_path(path, dpi=dpi)
        if max_pages:
            pages = pages[:max_pages]
        out = []
        for img in pages:
            filtered = mask_non_print_regions(img)
            txt = pytesseract.image_to_string(filtered, lang=language)
            out.append(txt)
        return "\n".join(out)
```

### Updated pipeline.py
Now routes per page: extract text directly if digital, OCR only if scanned.
```python
from .pdf.classifier import classify_pages

...

def run_pipeline(pdf_in: str, pdf_out: str, cfg: AppConfig):
    log = setup_logger(cfg.logging.level)

    # Classify each page
    page_types = classify_pages(pdf_in, cfg.pdf.max_pages)

    text_blocks = []
    ocr = TesseractOCREngine()
    for idx, typ in enumerate(page_types):
        if typ == "digital":
            txt = extract_pdf_text(pdf_in, maxpages=idx+1)[-1]  # per-page slice
        else:
            txt = ocr.ocr_pdf(pdf_in, cfg.ocr.language, cfg.ocr.dpi, 1)
        text_blocks.append(txt)

    text = "\n".join(text_blocks)
    ...  # Continue de-id, MT, re-id, write out
```

---

## README.md (updated guidance)
```md
# MedsafeMT Scaffold (Mixed Medical PDFs)

**Adapted for 87‑page mixed PDFs with forms, scans, handwriting, stamps:**
- Detects each page type (digital vs scanned).
- Extracts digital text directly.
- Runs OCR only on scanned pages, filtered to **skip handwriting and stamps** (mask based on blob size/color).
- Outputs cleaned text for de‑id → MT → re‑id.

## Benefits
- Avoids OCR noise from handwriting and stamps.
- Reduces false PHI captures (since handwritten names/signatures are out of scope).
- Keeps pipeline fast and deterministic.

## Next Steps
- Improve page classifier with ML (text density, histogram features).
- Train/finetune OCR filter for printed vs handwritten Spanish clinical docs.
- Add table/column structure retention.
```


---

# Update: Print-only OCR for mixed 87‑page medical PDFs

This update tunes the scaffold to **focus on printed text only** and **skip handwriting/stamps** while efficiently handling large, mixed PDFs (born‑digital pages + scanned pages).

## What changed (additions)
- New modules: `imageops/preprocess.py` and `imageops/masks.py` for print‑focused preprocessing and masking.
- OCR engine updated to set Tesseract `--oem`/`--psm` and apply masks before OCR.
- Per‑page text‑layer detection: OCR only pages with insufficient embedded text.
- Config gains `workers`, `psm`, `oem`, `skip_handwriting`, `skip_stamp_colors`, `text_layer_min_chars`.
- Pipeline reworked to process per page and join results, keeping memory predictable on long PDFs.

## pyproject.toml (deps)
```toml
[project]
version = "0.1.1"
dependencies = [
  "pydantic>=2.6", "click>=8.1", "python-dotenv>=1.0",
  "pdfminer.six>=20231228", "pdfplumber>=0.11", "reportlab>=4.0",
  "pytesseract>=0.3", "Pillow>=10.0", "spacy>=3.7",
  "regex>=2024.5.15", "python-dateutil>=2.9", "pdf2image>=1.17",
  "numpy>=1.26", "opencv-python-headless>=4.10"
]
```

## examples/config.sample.yaml (new fields)
```yaml
run:
  workers: 4

ocr:
  language: spa+eng
  dpi: 300
  psm: 6
  oem: 1
  skip_handwriting: true
  skip_stamp_colors: [red, blue]

pdf:
  text_layer_min_chars: 25
  max_pages: 1000
```

## src/medsafe_mt/imageops/preprocess.py
```python
import numpy as np, cv2
from PIL import Image

def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def cv_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))

def deskew(gray: np.ndarray) -> np.ndarray:
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi/180, 200)
    angle = 0.0
    if lines is not None:
        angles = [theta - np.pi/2 for rho, theta in lines[:,0]]
        angle = float(np.median(angles))
    (h, w) = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), angle*180/np.pi, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

def preprocess_for_print(img: Image.Image) -> Image.Image:
    cv = pil_to_cv(img)
    gray = cv2.cvtColor(cv, cv2.COLOR_BGR2GRAY)
    gray = deskew(gray)
    norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    blur = cv2.medianBlur(norm, 3)
    binar = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 31, 10)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
    morph = cv2.morphologyEx(binar, cv2.MORPH_CLOSE, kernel, iterations=1)
    return cv_to_pil(cv2.cvtColor(morph, cv2.COLOR_GRAY2BGR))
```

## src/medsafe_mt/imageops/masks.py
```python
import numpy as np, cv2
from PIL import Image

class MaskPipeline:
    def __init__(self, skip_handwriting: bool, skip_stamp_colors: list[str]):
        self.skip_handwriting = skip_handwriting
        self.skip_stamp_colors = skip_stamp_colors

    def apply(self, img: Image.Image) -> Image.Image:
        cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        out = cv.copy()
        hsv = cv2.cvtColor(cv, cv2.COLOR_BGR2HSV)
        masks = []
        if 'red' in self.skip_stamp_colors:
            lower1, upper1 = np.array([0,70,50]), np.array([10,255,255])
            lower2, upper2 = np.array([170,70,50]), np.array([180,255,255])
            masks.append(cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2))
        if 'blue' in self.skip_stamp_colors:
            lower, upper = np.array([90,70,50]), np.array([140,255,255])
            masks.append(cv2.inRange(hsv, lower, upper))
        if masks:
            mask = masks[0]
            for m in masks[1:]:
                mask |= m
            out[mask>0] = [255,255,255]
        if self.skip_handwriting:
            gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 80, 150)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
            thin = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel)
            out[thin>0] = 255
        return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))

def build_masks(skip_handwriting: bool, skip_stamp_colors: list[str]) -> MaskPipeline:
    return MaskPipeline(skip_handwriting, skip_stamp_colors)
```

## src/medsafe_mt/pdf/extractor.py (per‑page)
```python
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage
from typing import Optional, List

def extract_page_texts(path: str, maxpages: Optional[int] = None) -> List[str]:
    texts: List[str] = []
    with open(path, 'rb') as fh:
        for i, _ in enumerate(PDFPage.get_pages(fh)):
            if maxpages and i >= maxpages:
                break
            page_text = extract_text(path, page_numbers=[i])
            texts.append(page_text or "")
    return texts
```

## src/medsafe_mt/ocr/tesseract.py (apply masks + configs)
```python
from .base import OCREngine
import pytesseract
from pdf2image import convert_from_path
from typing import Optional
from ..imageops.preprocess import preprocess_for_print
from ..imageops.masks import build_masks

class TesseractOCREngine(OCREngine):
    def ocr_pdf(self, path: str, language: str, dpi: int, max_pages: Optional[int] = None,
                psm: int = 6, oem: int = 1, skip_handwriting: bool = True, skip_stamp_colors: list[str] | None = None) -> str:
        pages = convert_from_path(path, dpi=dpi)
        if max_pages:
            pages = pages[:max_pages]
        masks = build_masks(skip_handwriting=skip_handwriting, skip_stamp_colors=skip_stamp_colors or [])
        out = []
        for img in pages:
            proc = preprocess_for_print(img)
            masked = masks.apply(proc)
            cfg = f"--oem {oem} --psm {psm}"
            out.append(pytesseract.image_to_string(masked, lang=language, config=cfg))
        return "
".join(out)
```

## src/medsafe_mt/pipeline.py (OCR only what’s needed)
```python
from .pdf.extractor import extract_page_texts
from .ocr.tesseract import TesseractOCREngine
from .utils.normalize import clean_ocr_noise

# inside run_pipeline(...):
page_texts = extract_page_texts(pdf_in, maxpages=cfg.pdf.max_pages)
pages_to_ocr = [i for i, t in enumerate(page_texts) if len((t or '').strip()) < cfg.pdf.text_layer_min_chars]

if pages_to_ocr:
    eng = TesseractOCREngine()
    from pdf2image import convert_from_path
    images = convert_from_path(pdf_in, dpi=cfg.ocr.dpi)
    for i in pages_to_ocr:
        proc = preprocess_for_print(images[i])
        masked = build_masks(cfg.ocr.skip_handwriting, cfg.ocr.skip_stamp_colors).apply(proc)
        cfgs = f"--oem {cfg.ocr.oem} --psm {cfg.ocr.psm}"
        import pytesseract
        page_texts[i] = pytesseract.image_to_string(masked, lang=cfg.ocr.language, config=cfgs)

text = clean_ocr_noise("

".join(page_texts))
```

## Notes
- This deliberately **does not** attempt handwriting recognition; masks aim to remove it to prevent OCR confusion.
- Color‑based stamp masking covers common red/blue seals; extend HSV ranges as needed.
- For 87‑page docs, consider chunking pages to control RAM; `workers` is included for future parallelization.
- Keep the de‑id/MT/re‑id stages unchanged; they operate on the joined text.

