
from PIL import Image, ImageEnhance, ImageDraw, ImageFilter
import numpy as np
from pathlib import Path
import tempfile
import cv2
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageProcessor:
    """Handles image processing operations including background removal and enhancement"""
    
    def __init__(self, background_color="#FFFFFF", enhance_pixelated=False):
        self.background_color = background_color
        self.enhance_pixelated = enhance_pixelated
        
        # Validate background color
        try:
            # Test if background color is valid hex
            int(self.background_color[1:], 16)
            if len(self.background_color) != 7 or not self.background_color.startswith('#'):
                raise ValueError
        except (ValueError, IndexError):
            logger.warning(f"Invalid background color: {background_color}, using white")
            self.background_color = "#FFFFFF"
    
    def process_image(self, image_path):
        """Process a single image: apply white background and enhance quality"""
        
        if not image_path or not Path(image_path).exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        try:
            # Open and validate image
            with Image.open(image_path) as image:
                # Check if image is valid
                image.verify()
            
            # Reopen for processing (verify closes the file)
            image = Image.open(image_path)
            
            # Check image dimensions
            if image.size[0] == 0 or image.size[1] == 0:
                raise ValueError("Image has zero dimensions")
            
            # Check image size (limit to reasonable size)
            max_pixels = 50 * 1024 * 1024  # 50MP limit
            if image.size[0] * image.size[1] > max_pixels:
                # Resize to fit within limit
                ratio = (max_pixels / (image.size[0] * image.size[1])) ** 0.5
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized large image from {image_path}")
            
            # Convert to RGBA for transparency handling
            if image.mode not in ['RGB', 'RGBA']:
                if image.mode == 'P':
                    image = image.convert('RGBA')
                elif image.mode in ['L', 'LA']:
                    image = image.convert('RGBA')
                else:
                    image = image.convert('RGBA')
            
            original_mode = image.mode
            
            # Enhance pixelated images if enabled
            if self.enhance_pixelated:
                try:
                    image = self.enhance_pixelated_image(image)
                except Exception as e:
                    logger.warning(f"Failed to enhance pixelated image: {e}")
                    # Continue with original image
            
            # Apply background
            try:
                processed_image = self.apply_white_background(image)
            except Exception as e:
                logger.error(f"Failed to apply background: {e}")
                # Fallback: convert to RGB
                processed_image = image.convert('RGB') if image.mode != 'RGB' else image
            
            # Enhance image quality
            try:
                processed_image = self.enhance_image(processed_image)
            except Exception as e:
                logger.warning(f"Failed to enhance image quality: {e}")
                # Continue with current image
            
            # Save processed image to temporary file
            try:
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.png', 
                    delete=False,
                    prefix='processed_'
                )
                
                # Ensure image is in RGB mode for saving
                if processed_image.mode == 'RGBA':
                    # Create white background for final save
                    final_image = Image.new('RGB', processed_image.size, 'white')
                    final_image.paste(processed_image, mask=processed_image.split()[-1] if len(processed_image.split()) > 3 else None)
                    processed_image = final_image
                
                processed_image.save(temp_file.name, 'PNG', quality=95, optimize=True)
                temp_file.close()
                
                # Verify saved file
                if not Path(temp_file.name).exists() or Path(temp_file.name).stat().st_size == 0:
                    raise ValueError("Failed to save processed image")
                
                return temp_file.name
                
            except Exception as e:
                logger.error(f"Failed to save processed image: {e}")
                # Cleanup temp file if it exists
                if 'temp_file' in locals() and hasattr(temp_file, 'name'):
                    try:
                        Path(temp_file.name).unlink(missing_ok=True)
                    except:
                        pass
                raise Exception(f"Failed to save processed image: {str(e)}")
            
        except Exception as e:
            logger.error(f"Image processing failed for {image_path}: {e}")
            raise Exception(f"Failed to process image {Path(image_path).name}: {str(e)}")
    
    def apply_white_background(self, image):
        """Apply white background to image, removing transparency"""
        
        try:
            # Convert hex color to RGB
            bg_color = tuple(int(self.background_color[i:i+2], 16) for i in (1, 3, 5))
            
            # Create background image
            background = Image.new('RGB', image.size, bg_color)
            
            # Paste the image onto the background
            if image.mode == 'RGBA':
                # Use alpha channel as mask if available
                alpha = image.split()[-1]
                background.paste(image, mask=alpha)
            else:
                background.paste(image)
            
            return background
            
        except Exception as e:
            logger.error(f"Failed to apply background: {e}")
            # Fallback: convert to RGB
            return image.convert('RGB') if image.mode != 'RGB' else image
    
    def enhance_image(self, image):
        """Enhance image quality: contrast, sharpness, and brightness"""
        
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance contrast (more conservative)
            contrast = ImageEnhance.Contrast(image)
            image = contrast.enhance(1.05)
            
            # Enhance sharpness (more conservative)
            sharpness = ImageEnhance.Sharpness(image)
            image = sharpness.enhance(1.05)
            
            # Slight brightness adjustment
            brightness = ImageEnhance.Brightness(image)
            image = brightness.enhance(1.02)
            
            return image
            
        except Exception as e:
            logger.warning(f"Enhancement failed: {e}")
            # Return original image if enhancement fails
            return image
    
    def resize_for_pdf(self, image_path, max_width=1200, max_height=1600):
        """Resize image for optimal PDF display while maintaining aspect ratio"""
        
        try:
            if not Path(image_path).exists():
                return image_path
            
            with Image.open(image_path) as image:
                # Calculate new size maintaining aspect ratio
                width, height = image.size
                
                if width <= max_width and height <= max_height:
                    return image_path  # No resizing needed
                
                ratio = min(max_width/width, max_height/height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                
                if new_width <= 0 or new_height <= 0:
                    logger.warning(f"Invalid resize dimensions for {image_path}")
                    return image_path
                
                resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save resized image
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.png', 
                    delete=False,
                    prefix='resized_'
                )
                resized_image.save(temp_file.name, 'PNG', quality=95)
                temp_file.close()
                
                return temp_file.name
            
        except Exception as e:
            logger.warning(f"Resize failed for {image_path}: {e}")
            # Return original path if resize fails
            return image_path
    
    def enhance_pixelated_image(self, image):
        """Enhance pixelated/low quality images using various techniques"""
        
        try:
            # Convert PIL to OpenCV format
            img_array = np.array(image)
            
            # Validate array
            if img_array.size == 0:
                return image
            
            # Convert RGBA to RGB if needed
            if len(img_array.shape) == 3 and img_array.shape[2] == 4:
                rgb_array = img_array[:, :, :3]
            elif len(img_array.shape) == 3:
                rgb_array = img_array
            else:
                # Handle grayscale
                rgb_array = np.stack([img_array] * 3, axis=-1)
            
            # Ensure correct data type
            if rgb_array.dtype != np.uint8:
                rgb_array = (rgb_array * 255).astype(np.uint8)
            
            # Convert RGB to BGR for OpenCV
            bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
            
            # Apply bilateral filter for noise reduction while preserving edges
            denoised = cv2.bilateralFilter(bgr_array, 9, 75, 75)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            lab[:,:,0] = clahe.apply(lab[:,:,0])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Apply unsharp masking for better sharpness
            gaussian = cv2.GaussianBlur(enhanced, (0, 0), 1.0)
            unsharp_mask = cv2.addWeighted(enhanced, 1.3, gaussian, -0.3, 0)
            
            # Convert back to RGB
            rgb_enhanced = cv2.cvtColor(unsharp_mask, cv2.COLOR_BGR2RGB)
            
            # Convert back to PIL Image
            enhanced_pil = Image.fromarray(rgb_enhanced.astype(np.uint8))
            
            # If original had alpha channel, preserve it
            if len(img_array.shape) == 3 and img_array.shape[2] == 4:
                alpha = Image.fromarray(img_array[:, :, 3], 'L')
                enhanced_pil.putalpha(alpha)
            
            return enhanced_pil
            
        except Exception as e:
            logger.warning(f"Pixelated enhancement failed: {e}")
            # Return original image if enhancement fails
            return image
    
    def upscale_image(self, image, scale_factor=2):
        """Upscale image using LANCZOS resampling"""
        
        try:
            if scale_factor <= 0 or scale_factor > 4:
                return image
            
            width, height = image.size
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # Check for reasonable dimensions
            if new_width <= 0 or new_height <= 0 or new_width * new_height > 50 * 1024 * 1024:
                return image
            
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
        except Exception as e:
            logger.warning(f"Upscaling failed: {e}")
            return image
    
    def reduce_noise(self, image):
        """Reduce noise in the image using PIL filters"""
        
        try:
            if image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            
            # Apply median filter to reduce noise
            filtered = image.filter(ImageFilter.MedianFilter(size=3))
            
            # Apply slight Gaussian blur
            blurred = filtered.filter(ImageFilter.GaussianBlur(radius=0.3))
            
            return blurred
            
        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return image

    def detect_card_edges(self, image_path):
        """Detect and crop card edges for better presentation"""
        
        try:
            if not Path(image_path).exists():
                return image_path
            
            with Image.open(image_path) as image:
                # Convert to numpy array for processing
                img_array = np.array(image)
                
                if img_array.size == 0:
                    return image_path
                
                # Find non-background pixels (assuming background is light)
                if len(img_array.shape) == 3:
                    gray = np.mean(img_array, axis=2)
                else:
                    gray = img_array
                
                # Find bounding box of content
                coords = np.column_stack(np.where(gray < 240))
                
                if len(coords) == 0:
                    return image_path
                
                y_min, x_min = coords.min(axis=0)
                y_max, x_max = coords.max(axis=0)
                
                # Add small padding
                padding = 20
                y_min = max(0, y_min - padding)
                x_min = max(0, x_min - padding)
                y_max = min(image.height, y_max + padding)
                x_max = min(image.width, x_max + padding)
                
                # Validate crop dimensions
                if x_max <= x_min or y_max <= y_min:
                    return image_path
                
                # Crop image
                cropped_image = image.crop((x_min, y_min, x_max, y_max))
                
                # Save cropped image
                temp_file = tempfile.NamedTemporaryFile(
                    suffix='.png', 
                    delete=False,
                    prefix='cropped_'
                )
                cropped_image.save(temp_file.name, 'PNG', quality=95)
                temp_file.close()
                
                return temp_file.name
            
        except Exception as e:
            logger.warning(f"Edge detection failed for {image_path}: {e}")
            # Return original path if cropping fails
            return image_path
