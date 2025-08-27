import re
import os
from pathlib import Path
from collections import defaultdict
import pytesseract
from PIL import Image

class CardMatcher:
    """Handles matching front and back card images based on ID numbers"""
    
    def __init__(self, use_ocr=False):
        self.use_ocr = use_ocr
        
        # Common patterns for Egyptian national ID in filenames
        self.id_patterns = [
            r'(\d{14})',  # Egyptian national ID (14 digits)
            r'ID_?(\d{14})',  # ID followed by 14 digits
            r'CARD_?(\d{14})',  # CARD followed by 14 digits
            r'(\d{14})_?(FRONT|BACK|وش|ضهر)',  # 14 digits with front/back indicators
            r'(FRONT|BACK|وش|ضهر)_?(\d{14})',  # Front/back followed by 14 digits
            r'(\d{10,})',  # Any long number sequence (10+ digits)
            r'(\d{8,})',   # Medium length numbers (8+ digits)
            r'(\d{5,})',   # Any sequence of 5+ digits
            r'(\d+)',      # Any number sequence (fallback)
        ]
        
        # Keywords to identify front/back
        self.front_keywords = ['front', 'f', 'وش', 'امام']
        self.back_keywords = ['back', 'b', 'ضهر', 'خلف']
    
    def match_cards(self, input_dir):
        """Match front and back cards from input directory"""
        
        image_files = self._get_image_files(input_dir)
        
        if not image_files:
            return []
        
        # Extract IDs and classify as front/back
        card_data = {}
        processing_info = []
        
        for file_path in image_files:
            try:
                card_id = self._extract_card_id(file_path)
                side = self._determine_side(file_path)
                
                # Extract name using OCR if enabled
                name = None
                if self.use_ocr:
                    name = self.extract_name_from_ocr(file_path)
                
                # Store processing info for debugging
                processing_info.append({
                    'file': file_path.name,
                    'extracted_id': card_id,
                    'detected_side': side,
                    'extracted_name': name or 'غير متاح'
                })
                
                if card_id:
                    if card_id not in card_data:
                        card_data[card_id] = {'front': None, 'back': None, 'name': None}
                    
                    if side == 'front' and card_data[card_id]['front'] is None:
                        card_data[card_id]['front'] = file_path
                        if name:
                            card_data[card_id]['name'] = name
                    elif side == 'back' and card_data[card_id]['back'] is None:
                        card_data[card_id]['back'] = file_path
                        if name and not card_data[card_id]['name']:
                            card_data[card_id]['name'] = name
                    else:
                        # If side is unclear or duplicate, assign to missing side
                        if card_data[card_id]['front'] is None:
                            card_data[card_id]['front'] = file_path
                            if name:
                                card_data[card_id]['name'] = name
                        elif card_data[card_id]['back'] is None:
                            card_data[card_id]['back'] = file_path
                            if name and not card_data[card_id]['name']:
                                card_data[card_id]['name'] = name
                            
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                processing_info.append({
                    'file': file_path.name,
                    'extracted_id': 'خطأ',
                    'detected_side': 'خطأ',
                    'extracted_name': 'خطأ',
                    'error': str(e)
                })
                continue
        
        # Print debugging info
        print("معلومات المعالجة:")
        for info in processing_info:
            print(f"  الملف: {info['file']} - الرقم: {info['extracted_id']} - الجانب: {info['detected_side']} - الاسم: {info['extracted_name']}")
        
        print(f"تم العثور على {len(card_data)} بطاقة مختلفة:")
        for card_id, sides in card_data.items():
            front_file = sides['front'].name if sides['front'] else 'غير موجود'
            back_file = sides['back'].name if sides['back'] else 'غير موجود'
            name = sides['name'] or 'غير متاح'
            print(f"  البطاقة {card_id}: الوش={front_file}, الضهر={back_file}, الاسم={name}")
        
        # Create card pairs with names
        card_pairs = []
        for card_id, sides in card_data.items():
            if sides['front']:  # At least front image is required
                card_pairs.append((card_id, sides['front'], sides['back'], sides['name']))
        
        return sorted(card_pairs, key=lambda x: str(x[0]))
    
    def _get_image_files(self, directory):
        """Get all image files from directory"""
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        image_files = []
        
        for file_path in Path(directory).iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                image_files.append(file_path)
        
        return image_files
    
    def _extract_card_id(self, file_path):
        """Extract card ID from filename or using OCR"""
        
        filename = file_path.stem.lower()
        
        # Try filename extraction first
        card_id = self._extract_id_from_filename(filename)
        
        if card_id:
            return card_id
        
        # Use OCR if enabled and filename extraction failed
        if self.use_ocr:
            try:
                card_id = self._extract_id_from_ocr(file_path)
                if card_id:
                    return card_id
            except Exception as e:
                print(f"OCR failed for {file_path}: {str(e)}")
        
        # Fallback: use filename without extension
        return self._clean_filename_for_id(filename)
    
    def _extract_id_from_filename(self, filename):
        """Extract ID from filename using patterns"""
        
        # Remove common prefixes/suffixes
        filename = re.sub(r'(card|id|front|back|f|b|وش|ضهر)', '', filename, flags=re.IGNORECASE)
        filename = re.sub(r'[_\-\s]+', '_', filename).strip('_')
        
        # Try each pattern
        for pattern in self.id_patterns:
            matches = re.findall(pattern, filename, re.IGNORECASE)
            if matches:
                # Extract numeric part
                for match in matches:
                    if isinstance(match, tuple):
                        for part in match:
                            if part.isdigit():
                                return part
                    elif match.isdigit():
                        return match
        
        # Look for Egyptian national ID (14 digits) first
        national_id = re.findall(r'\d{14}', filename)
        if national_id:
            return national_id[0]
        
        # Look for any long sequence of digits (10+)
        long_digits = re.findall(r'\d{10,}', filename)
        if long_digits:
            return long_digits[0]
        
        # Look for medium length digits (8+)
        medium_digits = re.findall(r'\d{8,}', filename)
        if medium_digits:
            return medium_digits[0]
        
        # Look for any meaningful sequence of digits (5+)
        meaningful_digits = re.findall(r'\d{5,}', filename)
        if meaningful_digits:
            return meaningful_digits[0]
        
        # Fallback: any sequence of digits
        digits = re.findall(r'\d+', filename)
        if digits:
            # Return the longest digit sequence
            return max(digits, key=len)
        
        return None
    
    def _extract_id_from_ocr(self, image_path):
        """Extract ID from image using OCR"""
        
        try:
            image = Image.open(image_path)
            
            # Configure OCR for Arabic and English
            custom_config = r'--oem 3 --psm 6 -l ara+eng'
            
            # Extract text
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Look for ID patterns in extracted text
            lines = text.split('\n')
            
            for line in lines:
                # Look for Egyptian national ID (14 digits)
                national_id = re.findall(r'\d{14}', line)
                if national_id:
                    return national_id[0]
                
                # Look for ID followed by numbers
                id_matches = re.findall(r'(?:ID|الرقم|رقم|رقم قومي|بطاقة رقم)\s*:?\s*(\d{10,})', line, re.IGNORECASE)
                if id_matches:
                    return id_matches[0]
                
                # Look for standalone long numbers
                numbers = re.findall(r'\d{10,}', line)
                if numbers:
                    return numbers[0]
            
            return None
            
        except Exception as e:
            raise Exception(f"OCR extraction failed: {str(e)}")
    
    def extract_name_from_ocr(self, image_path):
        """Extract person name from card image using OCR"""
        
        try:
            image = Image.open(image_path)
            
            # Configure OCR for Arabic and English
            custom_config = r'--oem 3 --psm 6 -l ara+eng'
            
            # Extract text
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Look for name patterns in extracted text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            for line in lines:
                # Look for Arabic name patterns
                arabic_name = re.findall(r'(?:الاسم|Name)\s*:?\s*([\u0627-\u064a\s]{3,})', line, re.IGNORECASE)
                if arabic_name:
                    name = arabic_name[0].strip()
                    if len(name) > 2:  # Valid name should be at least 3 characters
                        return self._clean_name(name)
                
                # Look for English name patterns
                english_name = re.findall(r'(?:Name|NAME)\s*:?\s*([A-Za-z\s]{3,})', line, re.IGNORECASE)
                if english_name:
                    name = english_name[0].strip()
                    if len(name) > 2:
                        return self._clean_name(name)
                
                # Look for standalone Arabic names (usually the longest Arabic text)
                if re.match(r'^[\u0627-\u064a\s]{5,}$', line.strip()):
                    # Check if it's likely a name (not too long, contains spaces)
                    if 5 <= len(line.strip()) <= 50 and ' ' in line.strip():
                        return self._clean_name(line.strip())
            
            # Fallback: try to find the most likely name from all Arabic text
            arabic_texts = []
            for line in lines:
                arabic_text = re.findall(r'[\u0627-\u064a\s]{5,}', line)
                for text in arabic_text:
                    text = text.strip()
                    if 5 <= len(text) <= 50 and ' ' in text:
                        arabic_texts.append(text)
            
            if arabic_texts:
                # Return the first reasonable Arabic text as name
                return self._clean_name(arabic_texts[0])
            
            return None
            
        except Exception as e:
            print(f"Name extraction failed for {image_path}: {str(e)}")
            return None
    
    def _clean_name(self, name):
        """Clean extracted name"""
        
        # Remove common OCR artifacts and unwanted characters
        name = re.sub(r'[^\u0627-\u064aA-Za-z\s]', '', name)
        
        # Remove extra spaces
        name = ' '.join(name.split())
        
        # Remove common unwanted words
        unwanted_words = ['الاسم', 'Name', 'NAME', 'الرقم', 'بطاقة']
        for word in unwanted_words:
            name = name.replace(word, '').strip()
        
        # Clean extra spaces again
        name = ' '.join(name.split())
        
        return name if len(name) > 2 else None
    
    def _determine_side(self, file_path):
        """Determine if image is front or back based on filename"""
        
        filename = file_path.name.lower()
        
        # Check for back keywords first (more specific)
        for keyword in self.back_keywords:
            if keyword in filename:
                return 'back'
        
        # Check for front keywords
        for keyword in self.front_keywords:
            if keyword in filename:
                return 'front'
        
        # If no clear indicator, try to infer from position in filename
        # Check if filename contains numbers followed by pattern
        if re.search(r'\d.*[2]', filename) or 'back' in filename or 'rear' in filename:
            return 'back'
        
        # Default assumption: if no clear indicator, assume front
        return 'front'
    
    def _clean_filename_for_id(self, filename):
        """Clean filename to use as ID when no pattern matches"""
        
        # Remove common extensions and separators
        cleaned = re.sub(r'[_\-\s]+', '_', filename)
        cleaned = cleaned.strip('_')
        
        # If still no clear ID, use first part before separator
        parts = cleaned.split('_')
        return parts[0] if parts else filename
