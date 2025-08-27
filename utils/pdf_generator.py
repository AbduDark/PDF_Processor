from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import inch
from PIL import Image
import tempfile
import os

class PDFGenerator:
    """Handles PDF generation with card images"""
    
    def __init__(self, page_size=A4):
        self.page_size = page_size
        self.page_width, self.page_height = page_size
        
        # Margins and layout settings
        self.margin = 0.5 * inch
        self.max_image_width = self.page_width - (2 * self.margin)
        self.max_image_height = self.page_height - (2 * self.margin)
    
    def create_pdf(self, front_image_path, back_image_path, output_path):
        """Create PDF with front and back card images"""
        
        try:
            # Create PDF canvas
            c = canvas.Canvas(str(output_path), pagesize=self.page_size)
            
            # Add front image
            if front_image_path and os.path.exists(front_image_path):
                self._add_image_to_pdf(c, front_image_path, "Front")
            
            # Add back image on new page
            if back_image_path and os.path.exists(back_image_path):
                c.showPage()  # New page
                self._add_image_to_pdf(c, back_image_path, "Back")
            
            # Save PDF
            c.save()
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to create PDF: {str(e)}")
    
    def _add_image_to_pdf(self, canvas_obj, image_path, label=""):
        """Add single image to PDF page with proper scaling"""
        
        try:
            # Open image to get dimensions
            pil_image = Image.open(image_path)
            img_width, img_height = pil_image.size
            
            # Calculate scaling to fit page while maintaining aspect ratio
            width_scale = self.max_image_width / img_width
            height_scale = self.max_image_height / img_height
            scale = min(width_scale, height_scale)
            
            # Calculate final dimensions
            final_width = img_width * scale
            final_height = img_height * scale
            
            # Calculate position to center image
            x_pos = (self.page_width - final_width) / 2
            y_pos = (self.page_height - final_height) / 2
            
            # Draw image
            canvas_obj.drawImage(
                image_path,
                x_pos,
                y_pos,
                width=final_width,
                height=final_height,
                preserveAspectRatio=True,
                mask='auto'
            )
            
            # Add label if provided
            if label:
                canvas_obj.setFont("Helvetica", 10)
                canvas_obj.drawString(
                    self.margin,
                    self.page_height - self.margin + 0.2 * inch,
                    label
                )
            
        except Exception as e:
            # Draw error message instead of image
            canvas_obj.setFont("Helvetica", 12)
            canvas_obj.drawString(
                self.page_width / 2 - 100,
                self.page_height / 2,
                f"Error loading image: {str(e)}"
            )
    
    def create_batch_pdf(self, card_data_list, output_path):
        """Create single PDF with multiple cards"""
        
        try:
            c = canvas.Canvas(str(output_path), pagesize=self.page_size)
            
            for i, (card_id, front_path, back_path) in enumerate(card_data_list):
                if i > 0:
                    c.showPage()  # New page for each card after first
                
                # Add card ID as header
                c.setFont("Helvetica-Bold", 14)
                c.drawString(
                    self.page_width / 2 - 50,
                    self.page_height - 0.3 * inch,
                    f"Card ID: {card_id}"
                )
                
                # Add front image
                if front_path:
                    # Calculate position for two images on page
                    front_y = self.page_height * 0.55
                    self._add_image_to_pdf_positioned(
                        c, front_path, 
                        self.page_width / 2, front_y,
                        "Front"
                    )
                
                # Add back image
                if back_path:
                    back_y = self.page_height * 0.25
                    self._add_image_to_pdf_positioned(
                        c, back_path,
                        self.page_width / 2, back_y,
                        "Back"
                    )
            
            c.save()
            return True
            
        except Exception as e:
            raise Exception(f"Failed to create batch PDF: {str(e)}")
    
    def _add_image_to_pdf_positioned(self, canvas_obj, image_path, center_x, center_y, label=""):
        """Add image at specific position"""
        
        try:
            pil_image = Image.open(image_path)
            img_width, img_height = pil_image.size
            
            # Scale image to fit in half page
            max_width = self.max_image_width * 0.8
            max_height = self.max_image_height * 0.35
            
            width_scale = max_width / img_width
            height_scale = max_height / img_height
            scale = min(width_scale, height_scale)
            
            final_width = img_width * scale
            final_height = img_height * scale
            
            # Calculate position
            x_pos = center_x - (final_width / 2)
            y_pos = center_y - (final_height / 2)
            
            # Draw image
            canvas_obj.drawImage(
                image_path,
                x_pos,
                y_pos,
                width=final_width,
                height=final_height,
                preserveAspectRatio=True,
                mask='auto'
            )
            
            # Add label
            if label:
                canvas_obj.setFont("Helvetica", 10)
                canvas_obj.drawString(
                    center_x - 20,
                    y_pos - 0.2 * inch,
                    label
                )
                
        except Exception as e:
            canvas_obj.setFont("Helvetica", 10)
            canvas_obj.drawString(
                center_x - 30,
                center_y,
                f"Error: {str(e)}"
            )
    
    def optimize_pdf_size(self, pdf_path):
        """Optimize PDF file size (placeholder for future enhancement)"""
        # This could be implemented using PyPDF2 or similar library
        # for compression and optimization
        pass
