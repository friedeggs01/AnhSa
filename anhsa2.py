import re
import fitz  # PyMuPDF
import pandas as pd
import streamlit as st

def extract_text_from_pdf(pdf_file):
    """Trích xuất toàn bộ text từ file PDF (file object từ Streamlit)."""
    text = ""
    with fitz.open(stream=pdf_file.read(), filetype="pdf") as pdf:
        for page in pdf:
            text += page.get_text("text")
    return text

def find_text_after_keyword(text, keyword, num_chars=50):
    """
    Tìm đoạn văn bản sau một keyword. 
    Nếu cùng dòng không có nội dung, lấy nội dung ở dòng kế tiếp.
    """
    # 1️⃣ Tìm trên cùng dòng
    pattern_same_line = re.escape(keyword) + r"[ \t]*(.{1," + str(num_chars) + r"})"
    match = re.search(pattern_same_line, text)
    if match:
        result = match.group(1).strip()
        if result:
            return result

    # 2️⃣ Nếu không có, tìm ở dòng kế tiếp
    pattern_next_line = re.escape(keyword) + r"\s*\n\s*(.{1," + str(num_chars) + r"})"
    match = re.search(pattern_next_line, text)
    if match:
        return match.group(1).strip()

    return None

# --- Streamlit UI ---
st.title("📄 PDF to Excel Extractor")
st.write("Upload PDF và tự động trích xuất thông tin theo các keyword.")

uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])

if uploaded_file is not None:
    text = extract_text_from_pdf(uploaded_file)

    # Danh sách các keyword cần trích xuất
    keywords = [
        "Invoice#:",
        "PO-Item:",
        "Material:",
        "NO MARKS",
        "Reference Invoice #:",
        "Material#:",
        "Invoice Number:",
        "Total Gross Weight:",
    ]

    results = []
    for keyword in keywords:
        result = find_text_after_keyword(text, keyword, num_chars=100)
        results.append({
            "Keyword": keyword,
            "Extracted Text": result if result else "⚠️ Not Found"
        })

    # Xuất ra Excel
    df = pd.DataFrame(results)
    import io

    # Tạo Excel in-memory
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)  # quay lại đầu buffer để đọc

    # Nút tải file trên Streamlit
    st.download_button(
        label="⬇️ Tải kết quả Excel",
        data=output,
        file_name="extracted_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


    st.dataframe(df)
