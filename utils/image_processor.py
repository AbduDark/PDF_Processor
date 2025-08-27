from PIL import Image, ImageEnhance, ImageDraw
import numpy as np
from pathlib import Path
import tempfile

class ImageProcessor:
    """Handles image processing operations including background removal and enhancement"""
    
    def __init__(self, background_color="#FFFFFF"):
        self.background_color = background_color
    
    def process_image(self, image_path):
        """Process a single image: apply white background and enhance quality"""
        
        try:
            # Open and convert image
            image = Image.open(image_path)
            
            # Convert to RGBA for transparency handling
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Apply white background
            processed_image = self.apply_white_background(image)
            
            # Enhance image quality
            processed_image = self.enhance_image(processed_image)
            
            # Save processed image to temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png', 
                delete=False
            )
            processed_image.save(temp_file.name, 'PNG', quality=95)
            
            return temp_file.name
            
        except Exception as e:
            raise Exception(f"Failed to process image {image_path}: {str(e)}")
    
    def apply_white_background(self, image):
        """Apply white background to image, removing transparency"""
        
        # Convert hex color to RGB
        bg_color = tuple(int(self.background_color[i:i+2], 16) for i in (1, 3, 5))
        
        # Create background image
        background = Image.new('RGB', image.size, bg_color)
        
        # Paste the image onto the background
        if image.mode == 'RGBA':
            background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
        else:
            background.paste(image)
        
        return background
    
    def enhance_image(self, image):
        """Enhance image quality: contrast, sharpness, and brightness"""
        
        try:
            # Enhance contrast
            contrast = ImageEnhance.Contrast(image)
            image = contrast.enhance(1.1)
            
            # Enhance sharpness
            sharpness = ImageEnhance.Sharpness(image)
            image = sharpness.enhance(1.1)
            
            # Slight brightness adjustment
            brightness = ImageEnhance.Brightness(image)
            image = brightness.enhance(1.05)
            
            return image
            
        except Exception as e:
            # Return original image if enhancement fails
            return image
    
    def resize_for_pdf(self, image_path, max_width=1200, max_height=1600):
        """Resize image for optimal PDF display while maintaining aspect ratio"""
        
        try:
            image = Image.open(image_path)
            
            # Calculate new size maintaining aspect ratio
            width, height = image.size
            ratio = min(max_width/width, max_height/height)
            
            if ratio < 1:
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save resized image
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png', 
                delete=False
            )
            image.save(temp_file.name, 'PNG', quality=95)
            
            return temp_file.name
            
        except Exception as e:
            # Return original path if resize fails
            return image_path
    
    def detect_card_edges(self, image_path):
        """Detect and crop card edges for better presentation"""
        
        try:
            image = Image.open(image_path)
            
            # Convert to numpy array for processing
            img_array = np.array(image)
            
            # Simple edge detection based on color variance
            # This is a basic implementation - can be enhanced with OpenCV
            
            # Find non-background pixels (assuming background is light)
            if len(img_array.shape) == 3:
                gray = np.mean(img_array, axis=2)
            else:
                gray = img_array
            
            # Find bounding box of content
            coords = np.column_stack(np.where(gray < 240))  # Adjust threshold as needed
            
            if len(coords) > 0:
                y_min, x_min = coords.min(axis=0)
                y_max, x_max = coords.max(axis=0)
                
                # Add small padding
                padding = 20
                y_min = max(0, y_min - padding)
                x_min = max(0, x_min - padding)
                y_max = min(image.height, y_max + padding)
                x_max = min(image.width, x_max + padding)
                
                # Crop image
                cropped_image = image.crop((x_min, y_min, x_max, y_max))
                
                # Save cropped image
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.png', 
                    delete=False
                )
                cropped_image.save(temp_file.name, 'PNG', quality=95)
                
                return temp_file.name
            
            return image_path
            
        except Exception as e:
            # Return original path if cropping fails
            return image_path
