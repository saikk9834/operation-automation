import cv2
import numpy as np
from PIL import Image

def create_die_cut_path(image_path, output_path, margin_pixels=20):
    """
    Create a die cut path around a sticker image with transparency.
    
    Parameters:
    image_path (str): Path to input image (PNG with transparency)
    output_path (str): Path to save the output image with die cut path
    margin_pixels (int): Number of pixels margin around the sticker
    """
    # Read the image with alpha channel
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    
    # Extract alpha channel
    alpha = img[:, :, 3]
    
    # Create binary mask from alpha channel
    _, binary = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Get the largest contour (main sticker shape)
    main_contour = max(contours, key=cv2.contourArea)
    
    # Create expanded contour for die cut
    epsilon = 0.002 * cv2.arcLength(main_contour, True)
    approx_contour = cv2.approxPolyDP(main_contour, epsilon, True)
    
    # Create slightly larger contour for die cut line
    kernel = np.ones((margin_pixels, margin_pixels), np.uint8)
    mask = np.zeros_like(binary)
    cv2.drawContours(mask, [approx_contour], -1, (255, 255, 255), -1)
    dilated_mask = cv2.dilate(mask, kernel, iterations=1)
    die_cut_contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Create output image with original sticker and die cut line
    output = img.copy()
    # White die cut line (255,255,255) with 4px thickness
    cv2.drawContours(output, die_cut_contours, -1, (255, 255, 255, 255), 20)
    
    # Save the result
    cv2.imwrite(output_path, output)
    
    # Return the die cut contour points for further use if needed
    return die_cut_contours[0]

def create_vector_die_cut(image_path, svg_output_path, margin_pixels=20):
    """
    Create an SVG die cut path around a sticker image.
    
    Parameters:
    image_path (str): Path to input image (PNG with transparency)
    svg_output_path (str): Path to save the output SVG
    margin_pixels (int): Number of pixels margin around the sticker
    """
    # Get the die cut contour
    contour = create_die_cut_path(image_path, "temp.png", margin_pixels)
    
    # Create SVG path
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    height, width = img.shape[:2]
    
    # Convert contour points to SVG path
    svg_path = "M "
    for point in contour:
        x, y = point[0]
        svg_path += f"{x},{y} L "
    svg_path = svg_path[:-2] + "Z"  # Close the path
    
    # Create SVG file with white stroke and 4px thickness
    svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <path d="{svg_path}" fill="none" stroke="white" stroke-width="4"/>
    </svg>"""
    
    with open(svg_output_path, 'w') as f:
        f.write(svg_content)    
def main():
    # For raster output with die cut line
    create_die_cut_path('/home/mayankch283/allin1/KPOPSTIC271.png', 'output_with_die_cut.png')

    # For vector SVG die cut path
    create_vector_die_cut('/home/mayankch283/allin1/KPOPSTIC271.png', 'die_cut_path.svg')

if __name__ == "__main__":
    main()