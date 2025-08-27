import streamlit as st
import os
import tempfile
import zipfile
from pathlib import Path
import shutil
from utils.image_processor import ImageProcessor
from utils.card_matcher import CardMatcher
from utils.pdf_generator import PDFGenerator

def main():
    st.set_page_config(
        page_title="مولد ملفات PDF للبطاقات",
        page_icon="🃏",
        layout="wide"
    )
    
    st.title("🃏 مولد ملفات PDF للبطاقات")
    st.markdown("""
    <div style='background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); padding: 1rem; border-radius: 10px; margin-bottom: 2rem;'>
        <h4 style='color: white; margin: 0;'>🎆 مرحباً بك في مولد ملفات البطاقات</h4>
        <p style='color: white; margin: 0.5rem 0 0 0;'>ارفع صور البطاقات لمطابقة الوش والضهر تلقائياً وإنشاء ملفات PDF بخلفية بيضاء</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'processed_cards' not in st.session_state:
        st.session_state.processed_cards = []
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = None
    
    # File upload section
    with st.container():
        st.markdown("### 📁 رفع صور البطاقات")
        st.markdown("<div style='background-color: #f0f2f6; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>", unsafe_allow_html=True)
        uploaded_files = st.file_uploader(
            "اختر ملفات صور البطاقات",
            type=['jpg', 'jpeg', 'png', 'tiff', 'tif'],
            accept_multiple_files=True,
            help="ارفع صور الوش والضهر للبطاقات. تأكد أن أسماء الملفات تحتوي على أرقام للمطابقة."
        )
        st.markdown("</div>", unsafe_allow_html=True)
    
    if uploaded_files:
        st.success(f"تم رفع {len(uploaded_files)} ملف")
        
        # Processing options
        st.markdown("### ⚙️ خيارات المعالجة")
        
        with st.container():
            st.markdown("<div style='background-color: #f8f9fa; padding: 1.5rem; border-radius: 10px; border-left: 4px solid #667eea;'>", unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
        
            with col1:
                st.markdown("**🔍 استخراج البيانات**")
                use_ocr = st.checkbox(
                    "استخراج من الصور", 
                    value=True,
                    help="استخرج الأسماء والأرقام من داخل البطاقات"
                )
                
            with col2:
                st.markdown("**🎨 لون الخلفية**")
                background_color = st.color_picker(
                    "اختر اللون", 
                    "#FFFFFF", 
                    help="لون خلفية البطاقات في ملف PDF"
                )
                
            with col3:
                st.markdown("**📝 تسمية الملفات**")
                naming_option = st.radio(
                    "اختر نوع التسمية",
                    ["🆔 بالاسم", "🔢 بالرقم القومي"],
                    index=0,
                    help="اختر طريقة تسمية ملفات PDF"
                )
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Process button
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 بدء معالجة البطاقات", type="primary", use_container_width=True):
                use_names = naming_option == "🆔 بالاسم"
                process_cards(uploaded_files, use_ocr, background_color, use_names)
    
    # Display results
    if st.session_state.processed_cards:
        display_results()

def process_cards(uploaded_files, use_ocr, background_color, use_names=True):
    """Process uploaded card images"""
    
    # Create temporary directory for processing
    if st.session_state.temp_dir:
        shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
    
    st.session_state.temp_dir = tempfile.mkdtemp()
    temp_dir = Path(st.session_state.temp_dir)
    
    # Save uploaded files
    input_dir = temp_dir / "input"
    input_dir.mkdir()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Save files
        status_text.text("يتم حفظ الملفات المرفوعة...")
        for i, file in enumerate(uploaded_files):
            file_path = input_dir / file.name
            with open(file_path, 'wb') as f:
                f.write(file.getbuffer())
            progress_bar.progress((i + 1) / len(uploaded_files) * 0.2)
        
        # Initialize processors
        image_processor = ImageProcessor(background_color)
        card_matcher = CardMatcher(use_ocr)
        pdf_generator = PDFGenerator()
        
        # Match cards
        status_text.text("جاري مطابقة أزواج البطاقات...")
        progress_bar.progress(0.3)
        
        card_pairs = card_matcher.match_cards(input_dir)
        
        if not card_pairs:
            st.error("لم يتم العثور على أزواج بطاقات متطابقة.")
            
            # Show diagnostic information
            st.info("نصائح لحل المشكلة:")
            st.markdown("""
            - تأكد من أن أسماء الملفات تحتوي على أرقام واضحة
            - استخدم كلمات مثل 'وش' أو 'ضهر' أو 'front' أو 'back' في أسماء الملفات
            - **فعل خيار OCR لاستخراج الأسماء من البطاقات وتسمية ملفات PDF بأسماء أصحابها**
            - مثال على أسماء الملفات: '29912345678901_وش.jpg' و '29912345678901_ضهر.jpg'
            """)
            return
        
        # Process each card pair
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        processed_cards = []
        
        for i, card_pair in enumerate(card_pairs):
            # Handle both old format (3 items) and new format (4 items with name)
            if len(card_pair) == 4:
                card_id, front_path, back_path, card_name = card_pair
            else:
                card_id, front_path, back_path = card_pair
                card_name = None
            status_text.text(f"جاري معالجة البطاقة {card_id}...")
            
            try:
                # Process images
                processed_front = image_processor.process_image(front_path)
                processed_back = image_processor.process_image(back_path) if back_path else None
                
                # Generate PDF with appropriate filename based on user choice
                if use_names and card_name:
                    filename = card_name
                else:
                    filename = card_id
                # Clean filename for safe file system usage
                safe_filename = _clean_filename(filename)
                pdf_path = output_dir / f"{safe_filename}.pdf"
                pdf_generator.create_pdf(processed_front, processed_back, pdf_path)
                
                processed_cards.append({
                    'id': card_id,
                    'name': card_name or 'غير متاح',
                    'front_image': front_path.name,
                    'back_image': back_path.name if back_path else 'غير موجود',
                    'pdf_path': pdf_path,
                    'status': 'تم بنجاح'
                })
                
            except Exception as e:
                processed_cards.append({
                    'id': card_id,
                    'name': card_name or 'غير متاح',
                    'front_image': front_path.name if front_path else 'غير موجود',
                    'back_image': back_path.name if back_path else 'غير موجود',
                    'pdf_path': None,
                    'status': f'خطأ: {str(e)}'
                })
            
            progress_bar.progress(0.3 + (i + 1) / len(card_pairs) * 0.7)
        
        st.session_state.processed_cards = processed_cards
        progress_bar.progress(1.0)
        status_text.text("تمت المعالجة بنجاح!")
        st.success(f"تمت معالجة {len(card_pairs)} زوج بطاقة")
        
    except Exception as e:
        st.error(f"فشلت المعالجة: {str(e)}")

def display_results():
    """Display processing results and download options"""
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1rem; border-radius: 10px; margin: 2rem 0 1rem 0;'>
        <h3 style='color: white; margin: 0; text-align: center;'>📊 نتائج المعالجة</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Summary
    total_cards = len(st.session_state.processed_cards)
    successful_cards = len([card for card in st.session_state.processed_cards if card['status'] == 'تم بنجاح'])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 إجمالي البطاقات", total_cards)
    with col2:
        st.metric("✅ نجحت", successful_cards)
    with col3:
        st.metric("❌ فشلت", total_cards - successful_cards)
    
    # Results table
    st.markdown("""
    <div style='margin: 2rem 0 1rem 0;'>
        <h4 style='color: #333; border-bottom: 2px solid #667eea; padding-bottom: 0.5rem;'>📋 تفاصيل معالجة البطاقات</h4>
    </div>
    """, unsafe_allow_html=True)
    
    results_data = []
    for card in st.session_state.processed_cards:
        results_data.append({
            'رقم البطاقة': card['id'],
            'اسم صاحب البطاقة': card.get('name', 'غير متاح'),
            'صورة الوش': card['front_image'],
            'صورة الضهر': card['back_image'],
            'الحالة': card['status']
        })
    
    st.dataframe(results_data, width='stretch')
    
    # Download options
    if successful_cards > 0:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 1rem; border-radius: 10px; margin: 1rem 0;'>
            <h4 style='color: white; margin: 0; text-align: center;'>📥 خيارات التحميل</h4>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Individual downloads
            st.markdown("""
            <div style='background-color: #e3f2fd; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                <h5 style='margin: 0; color: #1976d2;'>📄 ملفات PDF منفردة</h5>
            </div>
            """, unsafe_allow_html=True)
            for card in st.session_state.processed_cards:
                if card['status'] == 'تم بنجاح' and card['pdf_path']:
                    with open(card['pdf_path'], 'rb') as f:
                        st.download_button(
                            label=f"📄 تحميل {card.get('name', card['id'])}.pdf",
                            data=f.read(),
                            file_name=f"{_clean_filename(card.get('name', card['id']))}.pdf",
                            mime="application/pdf",
                            key=f"download_{card['id']}"
                        )
        
        with col2:
            # Batch download
            st.markdown("""
            <div style='background-color: #f3e5f5; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
                <h5 style='margin: 0; color: #7b1fa2;'>📦 تحميل جماعي</h5>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📦 إنشاء ملف مضغوط", use_container_width=True, type="secondary"):
                create_zip_download()

def create_zip_download():
    """Create ZIP archive of all successful PDFs"""
    
    if not st.session_state.temp_dir:
        st.error("لا توجد ملفات معالجة")
        return
    
    zip_path = Path(st.session_state.temp_dir) / "card_pdfs.zip"
    
    try:
        with zipfile.ZipFile(zip_path, 'w') as zip_file:
            for card in st.session_state.processed_cards:
                if card['status'] == 'تم بنجاح' and card['pdf_path']:
                    safe_name = _clean_filename(card.get('name', card['id']))
                    zip_file.write(card['pdf_path'], f"{safe_name}.pdf")
        
        with open(zip_path, 'rb') as f:
            st.download_button(
                label="📦 تحميل جميع ملفات PDF",
                data=f.read(),
                file_name="card_pdfs.zip",
                mime="application/zip"
            )
        
        st.success("تم إنشاء الملف المضغوط بنجاح!")
        
    except Exception as e:
        st.error(f"فشل في إنشاء الملف المضغوط: {str(e)}")

# Cleanup on app restart
def _clean_filename(filename):
    """Clean filename for safe file system usage"""
    import re
    
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', str(filename))
    
    # Remove extra spaces and replace with underscores
    filename = re.sub(r'\s+', '_', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Ensure it's not empty
    if not filename or filename == '_':
        filename = 'unknown'
    
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename

def cleanup_temp_files():
    """Clean up temporary files"""
    if st.session_state.temp_dir and os.path.exists(st.session_state.temp_dir):
        shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
        st.session_state.temp_dir = None

if __name__ == "__main__":
    # Register cleanup
    import atexit
    atexit.register(cleanup_temp_files)
    
    main()
