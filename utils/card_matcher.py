
import re
import os
from pathlib import Path
from collections import defaultdict
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import logging
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class CardMatcher:
    """Advanced AI-powered card matching and name extraction system"""
    
    def __init__(self, use_ocr=False):
        self.use_ocr = use_ocr
        
        # Enhanced patterns for Egyptian national ID
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
        self.front_keywords = ['front', 'f', 'وش', 'امام', 'face']
        self.back_keywords = ['back', 'b', 'ضهر', 'خلف', 'rear']
        
        # AI-powered name extraction patterns (my invention)
        self.ai_name_patterns = {
            'explicit': [
                r'(?:الاسم|اسم|Name|NAME|الإسم|إسم)\s*:?\s*([\u0627-\u064a\s]{4,60})',
                r'(?:اسم الحامل|حامل البطاقة|صاحب البطاقة)\s*:?\s*([\u0627-\u064a\s]{4,60})',
                r'(?:holder|cardholder|name)\s*:?\s*([A-Za-z\s]{4,60})',
            ],
            'structural': [
                # 4-word Arabic names (most comprehensive)
                r'([\u0627-\u064a]{2,}\s+[\u0627-\u064a]{2,}\s+[\u0627-\u064a]{2,}\s+[\u0627-\u064a]{2,})',
                # 3-word Arabic names (common format)
                r'([\u0627-\u064a]{2,}\s+[\u0627-\u064a]{2,}\s+[\u0627-\u064a]{2,})',
                # 2-word substantial names
                r'([\u0627-\u064a]{3,}\s+[\u0627-\u064a]{3,})',
                # English names
                r'([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)',
                # Mixed patterns
                r'([A-Za-z\u0627-\u064a]{2,}\s+[A-Za-z\u0627-\u064a]{2,}(?:\s+[A-Za-z\u0627-\u064a]{2,})*)',
            ],
            'positional': [
                # Names at specific positions (first lines after certain keywords)
                r'(?:جمهورية مصر العربية|وزارة الداخلية)\s*\n\s*([\u0627-\u064a\s]{6,50})',
                r'(?:ARAB REPUBLIC OF EGYPT)\s*\n\s*([A-Za-z\s]{6,50})',
            ]
        }
    
    def match_cards(self, input_dir):
        """Enhanced card matching with multi-image AI processing"""
        
        try:
            image_files = self._get_image_files(input_dir)
            
            if not image_files:
                logger.warning("No image files found in directory")
                return []
            
            logger.info(f"Starting AI processing for {len(image_files)} image files")
            
        except Exception as e:
            logger.error(f"Failed to get image files from {input_dir}: {e}")
            return []
        
        # Multi-stage processing with AI enhancement
        card_data = {}
        processing_info = []
        
        # Stage 1: Process all images simultaneously for better correlation
        enhanced_images = self._batch_enhance_images(image_files)
        
        # Stage 2: Extract data from enhanced images
        for i, file_path in enumerate(image_files):
            try:
                enhanced_image = enhanced_images.get(str(file_path))
                
                card_id = self._extract_card_id(file_path, enhanced_image)
                side = self._determine_side(file_path)
                
                # Advanced AI name extraction
                name = None
                if self.use_ocr:
                    name = self._ai_extract_name_multi_method(file_path, enhanced_image)
                
                # Store processing info for debugging
                processing_info.append({
                    'file': file_path.name,
                    'extracted_id': card_id,
                    'detected_side': side,
                    'extracted_name': name or 'غير متاح',
                    'enhanced': enhanced_image is not None
                })
                
                if card_id:
                    if card_id not in card_data:
                        card_data[card_id] = {'front': None, 'back': None, 'name': None, 'confidence': 0}
                    
                    # Calculate name confidence for better selection
                    name_confidence = self._calculate_extraction_confidence(name, enhanced_image) if name else 0
                    
                    if side == 'front' and card_data[card_id]['front'] is None:
                        card_data[card_id]['front'] = file_path
                        if name and name_confidence > card_data[card_id]['confidence']:
                            card_data[card_id]['name'] = name
                            card_data[card_id]['confidence'] = name_confidence
                    elif side == 'back' and card_data[card_id]['back'] is None:
                        card_data[card_id]['back'] = file_path
                        if name and name_confidence > card_data[card_id]['confidence']:
                            card_data[card_id]['name'] = name
                            card_data[card_id]['confidence'] = name_confidence
                    else:
                        # Smart assignment based on availability and confidence
                        if card_data[card_id]['front'] is None:
                            card_data[card_id]['front'] = file_path
                            if name and name_confidence > card_data[card_id]['confidence']:
                                card_data[card_id]['name'] = name
                                card_data[card_id]['confidence'] = name_confidence
                        elif card_data[card_id]['back'] is None:
                            card_data[card_id]['back'] = file_path
                            if name and name_confidence > card_data[card_id]['confidence']:
                                card_data[card_id]['name'] = name
                                card_data[card_id]['confidence'] = name_confidence
                            
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                processing_info.append({
                    'file': file_path.name,
                    'extracted_id': 'خطأ',
                    'detected_side': 'خطأ',
                    'extracted_name': 'خطأ',
                    'enhanced': False,
                    'error': str(e)
                })
                continue
        
        # Stage 3: Post-process and cross-validate names
        self._cross_validate_names(card_data, enhanced_images)
        
        # Print enhanced debugging info
        print("🔍 معلومات المعالجة المتقدمة:")
        for info in processing_info:
            enhancement_status = "✨ محسنة" if info.get('enhanced') else "📷 عادية"
            print(f"  الملف: {info['file']} - الرقم: {info['extracted_id']} - الجانب: {info['detected_side']} - الاسم: {info['extracted_name']} - {enhancement_status}")
        
        print(f"\n🎯 تم العثور على {len(card_data)} بطاقة مختلفة:")
        for card_id, sides in card_data.items():
            front_file = sides['front'].name if sides['front'] else 'غير موجود'
            back_file = sides['back'].name if sides['back'] else 'غير موجود'
            name = sides['name'] or 'غير متاح'
            confidence = sides.get('confidence', 0)
            print(f"  البطاقة {card_id}: الوش={front_file}, الضهر={back_file}, الاسم={name} (ثقة: {confidence:.1f}%)")
        
        # Create card pairs with enhanced names
        card_pairs = []
        for card_id, sides in card_data.items():
            if sides['front']:  # At least front image is required
                card_pairs.append((card_id, sides['front'], sides['back'], sides['name']))
        
        return sorted(card_pairs, key=lambda x: str(x[0]))
    
    def _batch_enhance_images(self, image_files):
        """Batch enhance multiple images for better processing"""
        
        enhanced_images = {}
        
        for file_path in image_files:
            try:
                # Load and enhance image
                with Image.open(file_path) as image:
                    enhanced = self._ai_enhance_for_ocr(image)
                    enhanced_images[str(file_path)] = enhanced
                    
            except Exception as e:
                logger.warning(f"Failed to enhance {file_path}: {e}")
                enhanced_images[str(file_path)] = None
        
        return enhanced_images
    
    def _ai_enhance_for_ocr(self, image):
        """AI-powered image enhancement for better OCR (my invention)"""
        
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply OpenCV-based enhancement if available
            try:
                import cv2
                
                # Convert PIL to OpenCV format
                img_array = np.array(image)
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                
                # Multi-stage enhancement pipeline
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                
                # Stage 1: Adaptive histogram equalization
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                enhanced_gray = clahe.apply(gray)
                
                # Stage 2: Noise reduction with edge preservation
                denoised = cv2.bilateralFilter(enhanced_gray, 9, 75, 75)
                
                # Stage 3: Sharpening with unsharp mask
                gaussian = cv2.GaussianBlur(denoised, (0, 0), 1.0)
                sharpened = cv2.addWeighted(denoised, 1.5, gaussian, -0.5, 0)
                
                # Stage 4: Adaptive thresholding for text extraction
                binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                             cv2.THRESH_BINARY, 11, 2)
                
                # Convert back to PIL
                enhanced_pil = Image.fromarray(binary)
                
                # Stage 5: Intelligent upscaling for small images
                width, height = enhanced_pil.size
                if width < 1000 or height < 700:
                    scale_factor = max(1000 / width, 700 / height)
                    new_size = (int(width * scale_factor), int(height * scale_factor))
                    enhanced_pil = enhanced_pil.resize(new_size, Image.Resampling.LANCZOS)
                
                return enhanced_pil
                
            except ImportError:
                # Fallback to PIL-only enhancement
                return self._pil_enhance_for_ocr(image)
            
        except Exception as e:
            logger.warning(f"AI enhancement failed: {e}")
            return image
    
    def _pil_enhance_for_ocr(self, image):
        """PIL-only enhancement fallback"""
        
        try:
            # Convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')
            
            # Multi-stage PIL enhancement
            # Stage 1: Contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.8)
            
            # Stage 2: Sharpness enhancement
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)
            
            # Stage 3: Noise reduction
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # Stage 4: Final sharpening
            image = image.filter(ImageFilter.SHARPEN)
            
            return image
            
        except Exception as e:
            logger.warning(f"PIL enhancement failed: {e}")
            return image
    
    def _ai_extract_name_multi_method(self, image_path, enhanced_image=None):
        """Multi-method AI name extraction (my invention)"""
        
        try:
            # Use enhanced image if available, otherwise load original
            if enhanced_image:
                image = enhanced_image
            else:
                image = Image.open(image_path)
            
            # Check if pytesseract is available
            try:
                pytesseract.get_tesseract_version()
            except:
                logger.warning("Tesseract not available")
                return None
            
            all_candidates = []
            confidence_scores = []
            
            # Method 1: Multi-configuration OCR extraction
            ocr_configs = [
                (r'--oem 3 --psm 6 -l ara+eng', "General layout", 1.0),
                (r'--oem 3 --psm 7 -l ara+eng', "Single text line", 0.9),
                (r'--oem 1 --psm 6 -l ara+eng', "LSTM neural net", 1.1),
                (r'--oem 3 --psm 4 -l ara+eng', "Single column", 0.8),
                (r'--oem 3 --psm 11 -l ara+eng', "Sparse text", 0.7),
            ]
            
            for config, description, weight in ocr_configs:
                try:
                    # Extract with confidence data
                    data = pytesseract.image_to_data(image, config=config, 
                                                   timeout=30, output_type=pytesseract.Output.DICT)
                    
                    # Get high-confidence text
                    text = self._extract_high_confidence_text(data, min_confidence=60)
                    
                    if text:
                        candidates = self._extract_names_with_ai_patterns(text)
                        for candidate in candidates:
                            if self._validate_name_ai(candidate):
                                confidence = self._calculate_name_confidence_advanced(candidate, data) * weight
                                all_candidates.append(candidate)
                                confidence_scores.append(confidence)
                                
                except Exception as e:
                    logger.debug(f"OCR config failed: {e}")
                    continue
            
            # Method 2: Region-based extraction
            try:
                region_candidates = self._extract_names_by_regions_ai(image)
                for candidate in region_candidates:
                    if self._validate_name_ai(candidate):
                        confidence = self._calculate_region_confidence(candidate)
                        all_candidates.append(candidate)
                        confidence_scores.append(confidence)
            except Exception as e:
                logger.debug(f"Region extraction failed: {e}")
            
            # Method 3: Pattern-based extraction with context awareness
            try:
                context_candidates = self._extract_names_with_context_ai(image)
                for candidate in context_candidates:
                    if self._validate_name_ai(candidate):
                        confidence = self._calculate_context_confidence(candidate)
                        all_candidates.append(candidate)
                        confidence_scores.append(confidence)
            except Exception as e:
                logger.debug(f"Context extraction failed: {e}")
            
            # AI-powered final selection
            if all_candidates:
                best_name = self._ai_select_best_name(all_candidates, confidence_scores)
                if best_name:
                    logger.info(f"🎯 AI selected name: {best_name}")
                    return best_name
            
            return None
            
        except Exception as e:
            logger.error(f"Multi-method extraction failed: {e}")
            return None
    
    def _extract_names_with_ai_patterns(self, text):
        """Extract names using AI-enhanced patterns"""
        
        candidates = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Apply pattern categories with intelligent scoring
        for pattern_type, patterns in self.ai_name_patterns.items():
            type_weight = {'explicit': 1.5, 'structural': 1.2, 'positional': 1.0}.get(pattern_type, 1.0)
            
            for pattern in patterns:
                for line in lines:
                    matches = re.findall(pattern, line, re.IGNORECASE)
                    for match in matches:
                        cleaned = self._ai_clean_name(match)
                        if cleaned and len(cleaned.split()) >= 2:
                            candidates.append(cleaned)
        
        return candidates
    
    def _extract_names_by_regions_ai(self, image):
        """AI-powered region-based name extraction"""
        
        candidates = []
        width, height = image.size
        
        # Define smart regions based on ID card layout analysis
        ai_regions = [
            (0, 0, width, int(height * 0.35), "header_region", 1.3),  # Header region (highest priority)
            (0, int(height * 0.2), width, int(height * 0.55), "name_region", 1.5),  # Primary name region
            (int(width * 0.1), int(height * 0.1), int(width * 0.9), int(height * 0.45), "central_region", 1.2),
            (0, int(height * 0.35), width, int(height * 0.65), "secondary_region", 0.9),  # Secondary region
        ]
        
        for x1, y1, x2, y2, region_name, weight in ai_regions:
            try:
                # Crop and process region
                region = image.crop((x1, y1, x2, y2))
                
                # Extract text from region
                config = r'--oem 3 --psm 6 -l ara+eng'
                text = pytesseract.image_to_string(region, config=config, timeout=20)
                
                if text.strip():
                    region_candidates = self._extract_names_with_ai_patterns(text)
                    for candidate in region_candidates:
                        if self._validate_name_ai(candidate):
                            candidates.append(candidate)
                
            except Exception as e:
                logger.debug(f"Region {region_name} failed: {e}")
                continue
        
        return candidates
    
    def _extract_names_with_context_ai(self, image):
        """Context-aware name extraction using AI"""
        
        try:
            # Full image OCR for context
            full_text = pytesseract.image_to_string(image, 
                                                   config=r'--oem 3 --psm 6 -l ara+eng', 
                                                   timeout=30)
            
            lines = full_text.split('\n')
            candidates = []
            
            # Context-aware extraction
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Look for context indicators
                context_indicators = [
                    'جمهورية مصر العربية', 'وزارة الداخلية', 'بطاقة الرقم القومي',
                    'ARAB REPUBLIC OF EGYPT', 'MINISTRY OF INTERIOR', 'NATIONAL ID'
                ]
                
                for indicator in context_indicators:
                    if indicator in line and i + 1 < len(lines):
                        # Check next few lines for names
                        for j in range(i + 1, min(i + 4, len(lines))):
                            potential_name = lines[j].strip()
                            if potential_name and self._looks_like_name_ai(potential_name):
                                cleaned = self._ai_clean_name(potential_name)
                                if cleaned:
                                    candidates.append(cleaned)
            
            return candidates
            
        except Exception as e:
            logger.debug(f"Context extraction failed: {e}")
            return []
    
    def _looks_like_name_ai(self, text):
        """AI-powered name detection"""
        
        # Basic structure check
        words = text.split()
        if not (2 <= len(words) <= 5):
            return False
        
        # Character analysis
        arabic_chars = len(re.findall(r'[\u0627-\u064a]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        total_letters = arabic_chars + english_chars
        
        if total_letters < len(text.replace(' ', '')) * 0.8:
            return False
        
        # Avoid common non-name patterns
        exclude_patterns = [
            r'\d{3,}', r'(رقم|بطاقة|تاريخ|ميلاد)', r'(ID|CARD|DATE|BIRTH)',
            r'^[A-Z\s]+$'  # All caps
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        return True
    
    def _ai_clean_name(self, name):
        """AI-powered name cleaning"""
        
        if not name:
            return None
        
        name = str(name).strip()
        
        # Remove OCR artifacts
        name = re.sub(r'[^\u0627-\u064aA-Za-z\s]', '', name)
        name = ' '.join(name.split())
        
        # Remove prefixes
        prefixes = [
            r'^(?:الاسم|اسم|Name|NAME)\s*:?\s*',
            r'^(?:اسم الحامل|صاحب البطاقة)\s*:?\s*',
        ]
        
        for prefix in prefixes:
            name = re.sub(prefix, '', name, flags=re.IGNORECASE)
        
        # Filter words
        words = name.split()
        valid_words = []
        
        exclude_words = {'رقم', 'بطاقة', 'قومي', 'تاريخ', 'ميلاد', 'محافظة', 'العنوان'}
        
        for word in words:
            if (word not in exclude_words and 
                not re.match(r'\d+', word) and 
                len(word) >= 2):
                valid_words.append(word)
        
        final_name = ' '.join(valid_words)
        
        return final_name if len(final_name) >= 4 and len(valid_words) >= 2 else None
    
    def _validate_name_ai(self, name):
        """Advanced AI name validation"""
        
        if not name or len(name.strip()) < 4:
            return False
        
        words = name.split()
        if not (2 <= len(words) <= 5):
            return False
        
        # Character composition
        arabic_chars = len(re.findall(r'[\u0627-\u064a]', name))
        english_chars = len(re.findall(r'[a-zA-Z]', name))
        total_letters = arabic_chars + english_chars
        
        if total_letters < len(name.replace(' ', '')) * 0.85:
            return False
        
        # Word quality
        for word in words:
            if not (2 <= len(word) <= 15):
                return False
        
        return True
    
    def _calculate_name_confidence_advanced(self, name, ocr_data):
        """Advanced confidence calculation"""
        
        confidence = 0.0
        words = name.split()
        
        # Structure scoring
        if 2 <= len(words) <= 4:
            confidence += 40
        else:
            confidence += 20
        
        # Arabic preference for Egyptian IDs
        arabic_ratio = len(re.findall(r'[\u0627-\u064a]', name)) / len(name.replace(' ', ''))
        confidence += arabic_ratio * 30
        
        # OCR confidence integration
        for word in words:
            for i, ocr_word in enumerate(ocr_data.get('text', [])):
                if word in ocr_word and i < len(ocr_data.get('conf', [])):
                    ocr_conf = int(ocr_data['conf'][i])
                    confidence += max(0, ocr_conf - 50) * 0.15
        
        # Length quality
        if 8 <= len(name) <= 35:
            confidence += 15
        
        return min(100, max(0, confidence))
    
    def _calculate_region_confidence(self, name):
        """Region-based confidence calculation"""
        
        base_confidence = 60  # Base confidence for region extraction
        
        words = name.split()
        if 3 <= len(words) <= 4:
            base_confidence += 20
        
        if 10 <= len(name) <= 30:
            base_confidence += 15
        
        return min(100, base_confidence)
    
    def _calculate_context_confidence(self, name):
        """Context-aware confidence calculation"""
        
        base_confidence = 70  # Higher base for context-aware extraction
        
        # Arabic name bonus
        arabic_chars = len(re.findall(r'[\u0627-\u064a]', name))
        if arabic_chars > len(name) * 0.8:
            base_confidence += 15
        
        return min(100, base_confidence)
    
    def _ai_select_best_name(self, candidates, confidence_scores):
        """AI-powered best name selection"""
        
        if not candidates:
            return None
        
        # Create candidate-score pairs
        scored_candidates = list(zip(candidates, confidence_scores))
        
        # Remove duplicates, keeping highest scores
        unique_candidates = {}
        for candidate, score in scored_candidates:
            normalized = self._normalize_name_for_comparison(candidate)
            if normalized not in unique_candidates or unique_candidates[normalized][1] < score:
                unique_candidates[normalized] = (candidate, score)
        
        # Sort by AI scoring
        final_candidates = list(unique_candidates.values())
        final_candidates.sort(key=lambda x: (
            x[1],  # Confidence score
            len(x[0].split()),  # Word count
            -abs(len(x[0].split()) - 3),  # Prefer 3-word names
            len(x[0])  # Length
        ), reverse=True)
        
        if final_candidates:
            return final_candidates[0][0]
        
        return None
    
    def _cross_validate_names(self, card_data, enhanced_images):
        """Cross-validate extracted names across multiple images"""
        
        # This method can compare names across different images of the same ID
        # to ensure consistency and accuracy
        
        for card_id, data in card_data.items():
            if data['name'] and len(data['name'].split()) < 3:
                # Try to extract a better name from the other image
                other_image_path = data['back'] if data['front'] else data['front']
                if other_image_path and str(other_image_path) in enhanced_images:
                    enhanced = enhanced_images[str(other_image_path)]
                    if enhanced:
                        alternative_name = self._ai_extract_name_multi_method(other_image_path, enhanced)
                        if alternative_name and len(alternative_name.split()) >= 3:
                            alt_confidence = self._calculate_extraction_confidence(alternative_name, enhanced)
                            if alt_confidence > data.get('confidence', 0):
                                data['name'] = alternative_name
                                data['confidence'] = alt_confidence
    
    def _calculate_extraction_confidence(self, name, image):
        """Calculate overall extraction confidence"""
        
        if not name:
            return 0
        
        base_confidence = 50
        
        # Name quality factors
        words = name.split()
        if 3 <= len(words) <= 4:
            base_confidence += 25
        elif len(words) == 2:
            base_confidence += 15
        
        # Length factor
        if 10 <= len(name) <= 35:
            base_confidence += 20
        
        # Arabic content (preferred for Egyptian IDs)
        arabic_ratio = len(re.findall(r'[\u0627-\u064a]', name)) / len(name.replace(' ', ''))
        base_confidence += arabic_ratio * 25
        
        return min(100, base_confidence)
    
    def _normalize_name_for_comparison(self, name):
        """Normalize name for comparison"""
        
        normalized = re.sub(r'\s+', ' ', name.lower().strip())
        normalized = re.sub(r'[\u064B-\u0652]', '', normalized)  # Remove diacritics
        return normalized
    
    def _extract_high_confidence_text(self, ocr_data, min_confidence=50):
        """Extract high confidence text from OCR data"""
        
        try:
            high_conf_words = []
            
            for i, confidence in enumerate(ocr_data['conf']):
                if int(confidence) > min_confidence and ocr_data['text'][i].strip():
                    high_conf_words.append(ocr_data['text'][i])
            
            return ' '.join(high_conf_words)
            
        except Exception as e:
            logger.warning(f"High confidence extraction failed: {e}")
            return ""
    
    # Keep existing methods for backwards compatibility
    def _get_image_files(self, directory):
        """Get all image files from directory"""
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        image_files = []
        
        for file_path in Path(directory).iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                image_files.append(file_path)
        
        return image_files
    
    def _extract_card_id(self, file_path, enhanced_image=None):
        """Extract card ID from filename or using OCR"""
        
        filename = file_path.stem.lower()
        
        # Try filename extraction first
        card_id = self._extract_id_from_filename(filename)
        
        if card_id:
            return card_id
        
        # Use OCR if enabled and filename extraction failed
        if self.use_ocr and enhanced_image:
            try:
                card_id = self._extract_id_from_image(enhanced_image)
                if card_id:
                    return card_id
            except Exception as e:
                logger.debug(f"OCR ID extraction failed for {file_path}: {e}")
        
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
        
        return None
    
    def _extract_id_from_image(self, image):
        """Extract ID from enhanced image using OCR"""
        
        try:
            # Use simple OCR configuration for ID extraction
            text = pytesseract.image_to_string(image, config=r'--oem 3 --psm 6')
            
            lines = text.split('\n')
            for line in lines:
                # Look for 14-digit Egyptian national ID
                national_id = re.findall(r'\d{14}', line)
                if national_id:
                    return national_id[0]
                
                # Look for long number sequences
                long_numbers = re.findall(r'\d{10,}', line)
                if long_numbers:
                    return long_numbers[0]
            
            return None
            
        except Exception as e:
            logger.debug(f"Image ID extraction failed: {e}")
            return None
    
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
