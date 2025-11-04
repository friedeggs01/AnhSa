import re
import fitz  # PyMuPDF
import pandas as pd
import streamlit as st
import io

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


def split_by_bill_names(text, bill_names):
    """
    Tách text thành các phần tương ứng với bill_names (theo thứ tự trong danh sách).
    Mỗi bill_name chỉ xuất hiện 1 lần, lấy nội dung từ bill_i đến bill_(i+1).
    """
    sections = []
    text_lower = text.lower()
    
    # Dò vị trí xuất hiện của từng bill_name trong text
    positions = []
    for b in bill_names:
        idx = text_lower.find(b.lower())
        if idx != -1:
            positions.append((idx, b))
    
    # Sắp xếp theo vị trí xuất hiện
    # positions.sort()
    
    # Tách nội dung giữa các bill
    for i, (start_idx, bill) in enumerate(positions):
        end_idx = positions[i+1][0] if i + 1 < len(positions) else len(text)
        content = text[start_idx + len(bill): end_idx].strip()
        sections.append((bill, content))
        
        text = text[end_idx:].strip()
    return sections
def split_by_bill_names(text, bill_names):
    """
    Cắt text thành các phần tương ứng với bill_names.
    - Sau khi lấy một section, loại bỏ phần đó khỏi text.
    - Không cho phép 2 bill liên tiếp giống nhau.
    """
    sections = []
    text_lower = text.lower()
    pattern = "|".join([re.escape(b.lower()) for b in bill_names])

    prev_bill = None
    while True:
        match = re.search(pattern, text_lower)
        if not match:
            break  # không còn bill nào

        bill = next(b for b in bill_names if b.lower() == match.group(0))

        # Bỏ qua nếu trùng với bill trước
        if bill == prev_bill:
            # Cắt bỏ phần trùng rồi tiếp tục tìm tiếp
            text = text[match.end():].strip()
            text_lower = text.lower()
            continue

        # Tìm bill tiếp theo (để biết điểm kết thúc)
        next_match = re.search(pattern, text_lower[match.end():])
        end_idx = match.end() + next_match.start() if next_match else len(text)
        content = text[match.end():end_idx].strip()

        # Lưu lại section
        sections.append((bill, content))

        # Cắt bỏ phần đã xử lý khỏi text
        text = text[end_idx:].strip()
        text_lower = text.lower()
        prev_bill = bill

    return sections
def extract_bill_sections(text, bill_names, keyword_dict, verbose=False):
    """
    Extract info for each bill section based on grouped keywords.
    Each main key in keyword_dict will become a column name.
    """
    sections = split_by_bill_names(text, bill_names)
    results = []

    for bill_name, content in sections:
        if verbose:
            print(f"Processing section: {bill_name}")
            print(f"Snippet: {content}...")
            print("-" * 40)

        entry = {"Bill Name": bill_name}
        for key, kw_list in keyword_dict.items():
            if not kw_list:
                entry[key] = "⚠️ Not Found"
                continue
            vals = None
            for kw in kw_list:
                cont = find_text_after_keyword(content, kw)
                if cont is not None:
                    vals = cont
            if vals:
                entry[key] = vals
            else:
                entry[key] = "⚠️ Not Found"

        results.append(entry)

    return pd.DataFrame(results)

# --- Streamlit UI ---
st.title("📄 PDF to Excel Extractor")
st.write("Upload PDF và tự động trích xuất thông tin theo các keyword.")

uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])

if uploaded_file is not None:
    text = extract_text_from_pdf(uploaded_file)
    # st.subheader("🔎 Preview nội dung PDF")
    # st.text(text[:100000])
    # Danh sách các keyword cần trích xuất
    bill_names = [
        "WAYBILL",
        "Trading Company  Commercial Invoice",
        "Factory Commercial Invoice",
        "Factory Packing List ",
        "MULTIPLE COUNTRY OF ORIGIN DECLARATION",
        "Japan Customs Form",
            "WAYBILL",
        "Trading Company  Commercial Invoice",
        "Factory Commercial Invoice",
        "Factory Packing List ",
        "MULTIPLE COUNTRY OF ORIGIN DECLARATION",
        "Japan Customs Form",
            "WAYBILL",
        "Trading Company  Commercial Invoice",
        "Factory Commercial Invoice",
        "Factory Packing List ",
        "MULTIPLE COUNTRY OF ORIGIN DECLARATION",
        "Japan Customs Form",
                "WAYBILL",
        "Trading Company  Commercial Invoice",
        "Factory Commercial Invoice",
        "Factory Packing List ",
        "MULTIPLE COUNTRY OF ORIGIN DECLARATION",
        "Japan Customs Form",
    ]


    keywords = {
        "INV": ["Invoice#:", "Invoice Number:", "Invoice Number.:", "INVOICE NO."],
        "Total weight": ["Total Gross Kgs:", "Total Gross Weight:"],
        "total volume": [],
        "PO": ["PO-Item:", "P.O.#:", "PO#:", "PO Number:", "Reference PO#:"],
        "PO line": ["ITEM:", "PO Line Item Seq.#:", "PO Line#:", "Item Seq.:", "Sizes:"],
        "Style": ["Material:", "Material No:", "Material#:", "MATERIAL", "Material #:"],
        "total carton": ["Amount", "Cartons:"],
        "total quantity": ["Total Quantity:", "Total Qty:", "Qty:", "Quantity:"]
    }
        
    df = extract_bill_sections(text, bill_names, keywords)
    for i in range(len(df)):
        if "-" in str(df.loc[i, "PO"]):
            parts = df.loc[i, "PO"].split("-")
            df.loc[i, "PO"] = parts[0]
            df.loc[i, "PO line"] = parts[1] if len(parts) > 1 else None
        df["PO"] = df["PO"].astype(str).str.split(",").str[0]
        df["PO line"] = df["PO line"].astype(str).str.split(",").str[0]
        df["total quantity"] = df["total quantity"].astype(str).str.split(" ").str[0]

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
