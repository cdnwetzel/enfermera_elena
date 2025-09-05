#!/usr/bin/env python3
"""
Layout-Preserving PDF Processor for Enfermera Elena
Maintains original document structure during translation
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import tempfile
import subprocess

import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import black, blue, red
import fitz  # PyMuPDF for better PDF manipulation

logger = logging.getLogger(__name__)


class BlockType(Enum):
    """Types of document blocks"""
    TITLE = "title"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FORM_FIELD = "form_field"
    HEADER = "header"
    FOOTER = "footer"
    CAPTION = "caption"
    LIST_ITEM = "list_item"
    SIGNATURE = "signature"
    STAMP = "stamp"


@dataclass
class TextBlock:
    """Represents a text block with position and content"""
    page_num: int
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    text: str
    block_type: BlockType
    confidence: float = 1.0
    font_size: Optional[float] = None
    font_name: Optional[str] = None
    is_bold: bool = False
    is_italic: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'page': self.page_num,
            'bbox': self.bbox,
            'text': self.text,
            'type': self.block_type.value,
            'confidence': self.confidence,
            'font_size': self.font_size,
            'font_name': self.font_name,
            'bold': self.is_bold,
            'italic': self.is_italic
        }


class LayoutAnalyzer:
    """Analyzes document layout and extracts structured text blocks"""
    
    def __init__(self, use_deep_learning: bool = False):
        """
        Initialize layout analyzer
        
        Args:
            use_deep_learning: Use LayoutParser with Detectron2 (requires GPU)
        """
        self.use_deep_learning = use_deep_learning
        
        if use_deep_learning:
            try:
                import layoutparser as lp
                self.layout_model = lp.Detectron2LayoutModel(
                    'lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config',
                    extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
                    label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
                )
                logger.info("LayoutParser initialized for deep learning analysis")
            except ImportError:
                logger.warning("LayoutParser not available, falling back to heuristics")
                self.use_deep_learning = False
                
    def analyze_digital_page(self, pdf_path: str, page_num: int) -> List[TextBlock]:
        """Extract layout from born-digital PDF page using pdfplumber"""
        blocks = []
        
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return blocks
                
            page = pdf.pages[page_num]
            
            # Extract words with positions
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False
            )
            
            # Extract tables separately
            tables = page.find_tables()
            
            # Group words into lines
            lines = self._group_words_into_lines(words)
            
            # Group lines into blocks
            text_blocks = self._group_lines_into_blocks(lines, page_num)
            
            # Handle tables
            for table in tables:
                if table.bbox:
                    table_text = self._extract_table_text(table)
                    blocks.append(TextBlock(
                        page_num=page_num,
                        bbox=table.bbox,
                        text=table_text,
                        block_type=BlockType.TABLE,
                        confidence=1.0
                    ))
                    
            blocks.extend(text_blocks)
            
        return blocks
        
    def analyze_scanned_page(self, image_path: str, page_num: int) -> List[TextBlock]:
        """Extract layout from scanned page using OCR with hOCR"""
        blocks = []
        
        # Get hOCR output from Tesseract
        hocr_data = pytesseract.image_to_pdf_or_hocr(
            image_path,
            lang='spa',
            config='--oem 1 --psm 6',
            extension='hocr'
        )
        
        # Parse hOCR to extract blocks with coordinates
        blocks = self._parse_hocr(hocr_data, page_num)
        
        # If deep learning is enabled, refine block types
        if self.use_deep_learning:
            blocks = self._refine_with_layout_model(image_path, blocks)
            
        return blocks
        
    def _group_words_into_lines(self, words: List[Dict]) -> List[List[Dict]]:
        """Group words into lines based on vertical position"""
        if not words:
            return []
            
        # Sort by vertical position, then horizontal
        words.sort(key=lambda w: (w['top'], w['x0']))
        
        lines = []
        current_line = [words[0]]
        current_top = words[0]['top']
        
        for word in words[1:]:
            # If word is on same line (within threshold)
            if abs(word['top'] - current_top) < 5:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
                current_top = word['top']
                
        if current_line:
            lines.append(current_line)
            
        return lines
        
    def _group_lines_into_blocks(self, lines: List[List[Dict]], page_num: int) -> List[TextBlock]:
        """Group lines into logical blocks (paragraphs, titles, etc.)"""
        blocks = []
        
        for line_group in self._identify_line_groups(lines):
            # Combine words in lines
            text = ' '.join(' '.join(word['text'] for word in line) for line in line_group)
            
            # Calculate bounding box
            all_words = [word for line in line_group for word in line]
            if not all_words:
                continue
                
            x0 = min(w['x0'] for w in all_words)
            y0 = min(w['top'] for w in all_words)
            x1 = max(w['x1'] for w in all_words)
            y1 = max(w['bottom'] for w in all_words)
            
            # Determine block type based on heuristics
            block_type = self._classify_block(text, (x1-x0), (y1-y0), all_words)
            
            # Get font info from first word
            font_size = all_words[0].get('height', 12)
            font_name = all_words[0].get('fontname', 'Unknown')
            
            blocks.append(TextBlock(
                page_num=page_num,
                bbox=(x0, y0, x1, y1),
                text=text,
                block_type=block_type,
                font_size=font_size,
                font_name=font_name
            ))
            
        return blocks
        
    def _identify_line_groups(self, lines: List[List[Dict]]) -> List[List[List[Dict]]]:
        """Identify groups of lines that form logical blocks"""
        if not lines:
            return []
            
        groups = []
        current_group = [lines[0]]
        
        for i in range(1, len(lines)):
            prev_line = lines[i-1]
            curr_line = lines[i]
            
            # Calculate vertical gap
            prev_bottom = max(w['bottom'] for w in prev_line)
            curr_top = min(w['top'] for w in curr_line)
            gap = curr_top - prev_bottom
            
            # If gap is small, same paragraph
            if gap < 15:  # Threshold for paragraph break
                current_group.append(curr_line)
            else:
                groups.append(current_group)
                current_group = [curr_line]
                
        if current_group:
            groups.append(current_group)
            
        return groups
        
    def _classify_block(self, text: str, width: float, height: float, words: List[Dict]) -> BlockType:
        """Classify block type based on heuristics"""
        text_lower = text.lower()
        word_count = len(text.split())
        
        # Title heuristics
        if word_count < 10 and height < 30:
            if any(word.get('height', 0) > 14 for word in words):  # Larger font
                return BlockType.TITLE
                
        # Form field heuristics
        if ':' in text and word_count < 20:
            return BlockType.FORM_FIELD
            
        # Header/footer heuristics (position-based would be better)
        if word_count < 15 and ('página' in text_lower or 'page' in text_lower):
            return BlockType.FOOTER
            
        # Table heuristics (if has multiple aligned columns)
        if '\t' in text or '|' in text:
            return BlockType.TABLE
            
        # Default to paragraph
        return BlockType.PARAGRAPH
        
    def _extract_table_text(self, table) -> str:
        """Extract text from pdfplumber table object"""
        if not table.rows:
            return ""
            
        rows_text = []
        for row in table.rows:
            row_text = ' | '.join(str(cell) if cell else '' for cell in row)
            rows_text.append(row_text)
            
        return '\n'.join(rows_text)
        
    def _parse_hocr(self, hocr_data: bytes, page_num: int) -> List[TextBlock]:
        """Parse hOCR output to extract text blocks with coordinates"""
        from bs4 import BeautifulSoup
        
        blocks = []
        soup = BeautifulSoup(hocr_data, 'html.parser')
        
        # Find all paragraph blocks
        for para in soup.find_all('p', class_='ocr_par'):
            # Extract bounding box
            title = para.get('title', '')
            bbox = self._extract_bbox_from_title(title)
            if not bbox:
                continue
                
            # Extract text
            text = para.get_text(strip=True)
            if not text:
                continue
                
            # Get confidence if available
            confidence = self._extract_confidence_from_title(title)
            
            blocks.append(TextBlock(
                page_num=page_num,
                bbox=bbox,
                text=text,
                block_type=BlockType.PARAGRAPH,
                confidence=confidence
            ))
            
        # Also extract line-level blocks for finer control
        for line in soup.find_all('span', class_='ocr_line'):
            title = line.get('title', '')
            bbox = self._extract_bbox_from_title(title)
            if not bbox:
                continue
                
            text = line.get_text(strip=True)
            if not text:
                continue
                
            # Check if this line is already part of a paragraph
            if not any(self._bbox_contains(b.bbox, bbox) for b in blocks):
                blocks.append(TextBlock(
                    page_num=page_num,
                    bbox=bbox,
                    text=text,
                    block_type=BlockType.PARAGRAPH,
                    confidence=0.9
                ))
                
        return blocks
        
    def _extract_bbox_from_title(self, title: str) -> Optional[Tuple[float, float, float, float]]:
        """Extract bounding box from hOCR title attribute"""
        import re
        match = re.search(r'bbox (\d+) (\d+) (\d+) (\d+)', title)
        if match:
            return tuple(map(float, match.groups()))
        return None
        
    def _extract_confidence_from_title(self, title: str) -> float:
        """Extract confidence from hOCR title attribute"""
        import re
        match = re.search(r'x_wconf (\d+)', title)
        if match:
            return float(match.group(1)) / 100.0
        return 0.9
        
    def _bbox_contains(self, outer: Tuple, inner: Tuple) -> bool:
        """Check if outer bbox contains inner bbox"""
        return (outer[0] <= inner[0] and outer[1] <= inner[1] and
                outer[2] >= inner[2] and outer[3] >= inner[3])
        
    def _refine_with_layout_model(self, image_path: str, blocks: List[TextBlock]) -> List[TextBlock]:
        """Refine block types using deep learning model"""
        # This would use LayoutParser to improve classification
        # Implementation depends on model availability
        return blocks


class LayoutPreservingTranslator:
    """Translates text while preserving document layout"""
    
    def __init__(self, translator, glossary_path: Optional[str] = None):
        """
        Initialize layout-preserving translator
        
        Args:
            translator: Translation backend (LibreTranslate, ALIA, etc.)
            glossary_path: Path to UMLS glossary
        """
        self.translator = translator
        self.glossary_path = glossary_path
        
    def translate_blocks(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """Translate text blocks while preserving structure"""
        translated_blocks = []
        
        for block in blocks:
            # Skip non-text blocks
            if block.block_type in [BlockType.SIGNATURE, BlockType.STAMP]:
                translated_blocks.append(block)
                continue
                
            # Translate text
            if block.text.strip():
                translated_text = self.translator.translate(block.text)
                
                # Adjust for text expansion/contraction
                translated_text = self._adjust_text_length(
                    translated_text,
                    block.bbox,
                    block.font_size
                )
                
                # Create new block with translated text
                translated_block = TextBlock(
                    page_num=block.page_num,
                    bbox=block.bbox,
                    text=translated_text,
                    block_type=block.block_type,
                    confidence=block.confidence,
                    font_size=block.font_size,
                    font_name=block.font_name,
                    is_bold=block.is_bold,
                    is_italic=block.is_italic
                )
                translated_blocks.append(translated_block)
            else:
                translated_blocks.append(block)
                
        return translated_blocks
        
    def _adjust_text_length(self, text: str, bbox: Tuple, font_size: Optional[float]) -> str:
        """Adjust text to fit within bounding box"""
        # Simple heuristic: truncate if too long
        # Better implementation would use font metrics
        
        if not font_size:
            font_size = 12
            
        # Estimate character width
        char_width = font_size * 0.5
        box_width = bbox[2] - bbox[0]
        max_chars = int(box_width / char_width)
        
        if len(text) > max_chars:
            # Try to break at word boundary
            if ' ' in text[:max_chars]:
                last_space = text[:max_chars].rfind(' ')
                return text[:last_space] + '...'
            else:
                return text[:max_chars-3] + '...'
                
        return text


class LayoutPreservingPDFWriter:
    """Recreates PDF with translated text preserving original layout"""
    
    def __init__(self, maintain_images: bool = True):
        """
        Initialize PDF writer
        
        Args:
            maintain_images: Keep original page as background image
        """
        self.maintain_images = maintain_images
        
    def create_translated_pdf(self,
                             original_pdf_path: str,
                             translated_blocks: List[TextBlock],
                             output_path: str,
                             overlay_mode: bool = True):
        """
        Create translated PDF preserving layout
        
        Args:
            original_pdf_path: Path to original PDF
            translated_blocks: List of translated text blocks
            output_path: Path for output PDF
            overlay_mode: If True, overlay text on original pages
        """
        if overlay_mode:
            self._create_overlay_pdf(original_pdf_path, translated_blocks, output_path)
        else:
            self._create_rebuilt_pdf(translated_blocks, output_path)
            
    def _create_overlay_pdf(self,
                           original_pdf_path: str,
                           translated_blocks: List[TextBlock],
                           output_path: str):
        """Create PDF by overlaying translated text on original pages"""
        
        # Open original PDF with PyMuPDF
        original_doc = fitz.open(original_pdf_path)
        
        # Group blocks by page
        blocks_by_page = {}
        for block in translated_blocks:
            if block.page_num not in blocks_by_page:
                blocks_by_page[block.page_num] = []
            blocks_by_page[block.page_num].append(block)
            
        # Process each page
        for page_num in range(len(original_doc)):
            page = original_doc[page_num]
            
            # Optional: Clear original text layer (keep images/graphics)
            # page.clean_contents()
            
            # Add translated text blocks
            if page_num in blocks_by_page:
                for block in blocks_by_page[page_num]:
                    self._add_text_to_page(page, block)
                    
        # Save translated PDF
        original_doc.save(output_path)
        original_doc.close()
        
        logger.info(f"Created overlay PDF: {output_path}")
        
    def _create_rebuilt_pdf(self,
                           translated_blocks: List[TextBlock],
                           output_path: str):
        """Create PDF from scratch with translated text"""
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        c = canvas.Canvas(output_path, pagesize=letter)
        page_width, page_height = letter
        
        # Group blocks by page
        blocks_by_page = {}
        for block in translated_blocks:
            if block.page_num not in blocks_by_page:
                blocks_by_page[block.page_num] = []
            blocks_by_page[block.page_num].append(block)
            
        # Create pages
        for page_num in sorted(blocks_by_page.keys()):
            if page_num > 0:
                c.showPage()
                
            # Add blocks to page
            for block in blocks_by_page[page_num]:
                # Convert coordinates (PDF origin is bottom-left)
                x = block.bbox[0]
                y = page_height - block.bbox[3]  # Flip Y coordinate
                
                # Set font
                font_size = block.font_size or 12
                c.setFont("Helvetica", font_size)
                
                # Draw text
                c.drawString(x, y, block.text)
                
        c.save()
        logger.info(f"Created rebuilt PDF: {output_path}")
        
    def _add_text_to_page(self, page: fitz.Page, block: TextBlock):
        """Add text block to PyMuPDF page"""
        
        # Create rectangle from bbox
        rect = fitz.Rect(block.bbox)
        
        # Insert text
        text_options = {
            "fontsize": block.font_size or 11,
            "fontname": "helv",  # Helvetica
            "color": (0, 0, 0),  # Black
        }
        
        # Handle different block types
        if block.block_type == BlockType.TITLE:
            text_options["fontsize"] = (block.font_size or 11) * 1.2
            text_options["fontname"] = "hebo"  # Helvetica Bold
            
        elif block.block_type == BlockType.TABLE:
            # Tables need special handling
            # Split into cells and position each
            lines = block.text.split('\n')
            y_offset = 0
            for line in lines:
                line_rect = fitz.Rect(rect.x0, rect.y0 + y_offset, rect.x1, rect.y0 + y_offset + 15)
                page.insert_textbox(line_rect, line, **text_options)
                y_offset += 15
            return
            
        # Insert text with wrapping
        overflow = page.insert_textbox(rect, block.text, **text_options)
        
        if overflow:
            logger.warning(f"Text overflow on page {block.page_num}: {len(overflow)} chars")


class LayoutPreservingPipeline:
    """Complete pipeline with layout preservation"""
    
    def __init__(self,
                 translator,
                 use_deep_learning: bool = False,
                 maintain_images: bool = True):
        """
        Initialize complete pipeline
        
        Args:
            translator: Translation backend
            use_deep_learning: Use LayoutParser for analysis
            maintain_images: Keep original pages as background
        """
        self.analyzer = LayoutAnalyzer(use_deep_learning)
        self.translator = LayoutPreservingTranslator(translator)
        self.writer = LayoutPreservingPDFWriter(maintain_images)
        
    def process_document(self,
                        input_pdf: str,
                        output_pdf: str,
                        page_limit: Optional[int] = None) -> Dict:
        """
        Process complete document preserving layout
        
        Args:
            input_pdf: Input PDF path
            output_pdf: Output PDF path
            page_limit: Maximum pages to process
            
        Returns:
            Processing statistics
        """
        stats = {
            'pages_processed': 0,
            'blocks_extracted': 0,
            'blocks_translated': 0,
            'layout_preserved': True
        }
        
        # Extract layout structure
        logger.info("Extracting document layout...")
        all_blocks = []
        
        with pdfplumber.open(input_pdf) as pdf:
            num_pages = min(len(pdf.pages), page_limit) if page_limit else len(pdf.pages)
            
            for page_num in range(num_pages):
                logger.info(f"Analyzing page {page_num + 1}/{num_pages}")
                
                # Check if page has text
                page = pdf.pages[page_num]
                if page.extract_text():
                    # Digital page
                    blocks = self.analyzer.analyze_digital_page(input_pdf, page_num)
                else:
                    # Scanned page - need OCR
                    # Convert to image first
                    images = convert_from_path(input_pdf, first_page=page_num+1, last_page=page_num+1)
                    if images:
                        with tempfile.NamedTemporaryFile(suffix='.png') as tmp:
                            images[0].save(tmp.name)
                            blocks = self.analyzer.analyze_scanned_page(tmp.name, page_num)
                            
                all_blocks.extend(blocks)
                
        stats['pages_processed'] = num_pages
        stats['blocks_extracted'] = len(all_blocks)
        
        # Translate blocks
        logger.info(f"Translating {len(all_blocks)} text blocks...")
        translated_blocks = self.translator.translate_blocks(all_blocks)
        stats['blocks_translated'] = len(translated_blocks)
        
        # Recreate PDF with layout
        logger.info("Creating translated PDF with preserved layout...")
        self.writer.create_translated_pdf(
            input_pdf,
            translated_blocks,
            output_pdf,
            overlay_mode=True
        )
        
        logger.info(f"✅ Layout-preserved translation complete: {output_pdf}")
        
        return stats


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python layout_preserving_processor.py input.pdf output.pdf")
        sys.exit(1)
        
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    
    # Create simple translator (replace with your actual translator)
    class SimpleTranslator:
        def translate(self, text):
            # Placeholder - replace with actual translation
            return f"[TRANSLATED] {text}"
            
    translator = SimpleTranslator()
    
    # Process with layout preservation
    pipeline = LayoutPreservingPipeline(
        translator=translator,
        use_deep_learning=False,
        maintain_images=True
    )
    
    stats = pipeline.process_document(input_pdf, output_pdf)
    
    print(f"Processing complete!")
    print(f"  Pages: {stats['pages_processed']}")
    print(f"  Blocks extracted: {stats['blocks_extracted']}")
    print(f"  Blocks translated: {stats['blocks_translated']}")
    print(f"  Output: {output_pdf}")