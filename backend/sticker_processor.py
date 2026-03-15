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
import cv2
import numpy as np


@dataclass
class StickerOrder:
    sku: str
    quantity: int
    design_url: str


sheet_number = 1


class StickerProcessor:
    def __init__(self,
                 sticker_size: Tuple[int, int] = (1.85, 1.85),  # inches
                 bleeding_pixels: int = 20,
                 canvas_sizes: List[Tuple[int, int]] = [(10, 8), (10, 10)]):
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
            # Create a transparent canvas instead of white
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
        # 1. Add heavy padding to ensure the border doesn't hit the image edge
        # We use a larger padding here to accommodate the thick bleed
        padding = self.bleeding_pixels * 3
        padded_sticker = Image.new('RGBA',
                                   (sticker_image.width + padding * 2, sticker_image.height + padding * 2),
                                   (0, 0, 0, 0))
        padded_sticker.paste(sticker_image, (padding, padding), sticker_image)

        # 2. Convert to CV2 to extract the shape (Alpha channel)
        cv2_image = cv2.cvtColor(np.array(padded_sticker), cv2.COLOR_RGBA2BGRA)
        alpha = cv2_image[:, :, 3]

        # Create a clean binary mask of the sticker's shape
        _, binary_mask = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)

        # 3. Use Dilation to expand the shape outward
        # This replaces 'drawContours'. It expands the solid white area perfectly.
        # A kernel of 45-60 creates a thick, smooth border.
        kernel_size = 45
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        dilated_mask = cv2.dilate(binary_mask, kernel, iterations=1)

        # 4. Create the "White Bleed" layer
        # We create a pure white image and apply the dilated mask as its transparency
        white_bleed_bg = np.full((cv2_image.shape[0], cv2_image.shape[1], 4), 255, dtype=np.uint8)
        white_bleed_bg[:, :, 3] = dilated_mask

        # Convert back to PIL
        white_bleed_pil = Image.fromarray(cv2.cvtColor(white_bleed_bg, cv2.COLOR_BGRA2RGBA))

        # 5. Composite: Put the original sticker ON TOP of the white bleed
        # This ensures the sticker stays sharp and the white is strictly behind it
        white_bleed_pil.paste(padded_sticker, (0, 0), padded_sticker)

        # 6. Final Crop and Resize
        # Remove empty space created by padding
        bbox = white_bleed_pil.getbbox()
        if bbox:
            white_bleed_pil = white_bleed_pil.crop(bbox)

        # Resize to fit the 2x2 inch box (self.sticker_pixels)
        w, h = white_bleed_pil.size
        aspect_ratio = w / h
        if w > h:
            new_w = self.sticker_pixels[0]
            new_h = int(new_w / aspect_ratio)
        else:
            new_h = self.sticker_pixels[1]
            new_w = int(new_h * aspect_ratio)

        return white_bleed_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)

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
        """
        Creates as many sheets as needed to process every sticker,
        doing so for EVERY canvas size defined in the class.
        """
        # 1. Pre-process all stickers once
        sticker_images = [self.add_bleeding(Image.open(f)) for f in sticker_files]
        generated_files = []

        # 2. Loop through each canvas size (10x8, 10x10, etc.)
        for canvas_size_px in self.canvas_pixels:
            canvas_inches = (canvas_size_px[0] / self.dpi, canvas_size_px[1] / self.dpi)
            size_label = f"{int(canvas_inches[0])}x{int(canvas_inches[1])}"

            # 3. Calculate grid positions for THIS specific canvas size
            positions = self.calculate_positions(canvas_size_px)
            stickers_per_sheet = len(positions)

            # 4. Calculate how many sheets are needed to fit all stickers on this canvas size
            total_stickers = len(sticker_images)
            total_sheets = math.ceil(total_stickers / stickers_per_sheet)

            # 5. Generate the sheets for this specific size
            for sheet_num in range(total_sheets):
                # Create the transparent canvas
                sheet = Image.new('RGBA', canvas_size_px, (0, 0, 0, 0))

                # Slice the sticker list to get only the stickers for this sheet
                start_idx = sheet_num * stickers_per_sheet
                end_idx = start_idx + stickers_per_sheet
                current_batch = sticker_images[start_idx:end_idx]

                # Place stickers in the calculated positions
                for i, sticker in enumerate(current_batch):
                    pos = positions[i]
                    sheet.paste(sticker, pos, sticker)

                # Add registration marks
                self.add_registration_marks(sheet)

                # 6. Save with a filename that includes Size AND Sheet Number
                # Example: order_10x8_sheet_1.png
                filename = f"order_{size_label}_sheet_{sheet_num + 1}.png"
                output_path = output_dir / filename
                sheet.save(output_path)
                generated_files.append(output_path)

        return generated_files
