import os
from PIL import Image, ImageDraw
from typing import List, Tuple
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
import shopify
from dataclasses import dataclass
from pathlib import Path
import math

@dataclass
class StickerOrder:
    sku: str
    quantity: int
    design_url: str

class StickerProcessor:
    def __init__(self, 
                 sticker_size: Tuple[int, int] = (2, 2),  # inches
                 bleeding_pixels: int = 4,
                 canvas_sizes: List[Tuple[int, int]] = [(10, 8), (10, 10)]):  # inches
        self.dpi = 300  # 300 pixels per inch
        self.mm_to_pixels = self.dpi / 25.4  # Convert mm to pixels
        
        # Convert measurements to pixels
        self.registration_mark_size = round(5 * self.mm_to_pixels)  # 5mm
        self.border_margin = round(10 * self.mm_to_pixels)  # 10mm
        self.sticker_spacing = round(5 * self.mm_to_pixels)  # 7mm
        
        # Basic setup
        self.sticker_size = sticker_size
        self.bleeding_pixels = bleeding_pixels
        self.canvas_sizes = canvas_sizes
        
        # Convert inches to pixels
        self.sticker_pixels = (round(sticker_size[0] * self.dpi), 
                             round(sticker_size[1] * self.dpi))
        self.canvas_pixels = [(round(w * self.dpi), round(h * self.dpi)) 
                            for w, h in canvas_sizes]
        
        # Grid sizes for each canvas
        self.grid_sizes = {
            (10, 8): (4, 5),  # 4 rows, 5 columns
            (10, 10): (5, 5)  # 5 rows, 5 columns
        }

    def calculate_positions(self, canvas_size: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Calculate exact positions for each sticker ensuring no cutoff."""
        canvas_inches = (canvas_size[0] / self.dpi, canvas_size[1] / self.dpi)
        rows, cols = self.grid_sizes[canvas_inches]
        
        # Calculate total width and height needed for stickers and spacing
        total_sticker_width = cols * self.sticker_pixels[0]
        total_sticker_height = rows * self.sticker_pixels[1]
        
        total_spacing_width = (cols - 1) * self.sticker_spacing
        total_spacing_height = (rows - 1) * self.sticker_spacing
        
        # Calculate remaining space after accounting for borders
        remaining_width = canvas_size[0] - (2 * self.border_margin) - total_sticker_width - total_spacing_width
        remaining_height = canvas_size[1] - (2 * self.border_margin) - total_sticker_height - total_spacing_height
        
        # Distribute remaining space evenly
        h_extra = remaining_width / (cols + 1)
        v_extra = remaining_height / (rows + 1)
        
        positions = []
        for row in range(rows):
            for col in range(cols):
                x = (self.border_margin + 
                     col * (self.sticker_pixels[0] + self.sticker_spacing + h_extra) + 
                     h_extra)
                y = (self.border_margin + 
                     row * (self.sticker_pixels[1] + self.sticker_spacing + v_extra) + 
                     v_extra)
                positions.append((round(x), round(y)))
        
        return positions

    def create_sticker_sheet(self, 
                           sticker_with_bleeding: Image.Image,
                           quantity: int,
                           canvas_size: Tuple[int, int]) -> List[Image.Image]:
        """Create sheets with stickers arranged in a grid with precise spacing."""
        canvas_inches = (canvas_size[0] / self.dpi, canvas_size[1] / self.dpi)
        rows, cols = self.grid_sizes[canvas_inches]
        stickers_per_sheet = rows * cols
        
        # Calculate all sticker positions
        positions = self.calculate_positions(canvas_size)
        
        sheets = []
        sheets_needed = max(1, math.ceil(quantity / stickers_per_sheet))
        
        for _ in range(sheets_needed):
            current_sheet = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
            
            # Place stickers at calculated positions
            for pos in positions:
                current_sheet.paste(
                    sticker_with_bleeding,
                    pos,
                    sticker_with_bleeding
                )
            
            # Add registration marks
            self.add_registration_marks(current_sheet)
            sheets.append(current_sheet)
        
        return sheets
    
    def add_bleeding(self, sticker_image: Image.Image) -> Image.Image:
        # Resize if not matching the required dimensions
        if sticker_image.size != self.sticker_pixels:
            sticker_image = sticker_image.convert("RGBA").resize(self.sticker_pixels)
        
        new_size = tuple(dim + 2 * self.bleeding_pixels for dim in sticker_image.size)
        new_image = Image.new('RGBA', new_size, (255, 255, 255, 0))
        # Create white border
        white_border = Image.new('RGBA', new_size, (255, 255, 255, 255))
        position = (self.bleeding_pixels, self.bleeding_pixels)
        white_border.paste(sticker_image, position, sticker_image)
        return white_border

    def add_registration_marks(self, canvas: Image.Image) -> None:
        """Add 5mm × 5mm black square registration marks to all four corners."""
        draw = ImageDraw.Draw(canvas)
        mark_size = self.registration_mark_size
        
        # Top-left
        draw.rectangle([0, 0, mark_size, mark_size], fill='black')
        
        # Top-right
        draw.rectangle([canvas.width - mark_size, 0, 
                       canvas.width, mark_size], fill='black')
        
        # Bottom-left
        draw.rectangle([0, canvas.height - mark_size, 
                       mark_size, canvas.height], fill='black')
        
        # Bottom-right
        draw.rectangle([canvas.width - mark_size, canvas.height - mark_size,
                       canvas.width, canvas.height], fill='black')

    def process_multi_sticker_order(self, sticker_files: List[Path], output_dir: Path) -> List[Path]:
        """Fill each canvas with the given stickers in a repeating sequence."""
        sticker_images = [self.add_bleeding(Image.open(f)) for f in sticker_files]
        generated_files = []
        
        for canvas_size in self.canvas_pixels:
            # Calculate positions and grid
            positions = self.calculate_positions(canvas_size)
            canvas_inches = (canvas_size[0]/self.dpi, canvas_size[1]/self.dpi)
            rows, cols = self.grid_sizes[canvas_inches]
            
            # Create a single sheet (or more if needed); here just one for example
            sheet = Image.new('RGBA', canvas_size, (255, 255, 255, 0))
            for i, pos in enumerate(positions):
                sticker = sticker_images[i % len(sticker_images)]
                sheet.paste(sticker, pos, sticker)
            
            self.add_registration_marks(sheet)
            
            output_path = output_dir / f"multi_stickers_{int(canvas_inches[0])}x{int(canvas_inches[1])}.png"
            sheet.save(output_path)
            generated_files.append(output_path)
        
        return generated_files

