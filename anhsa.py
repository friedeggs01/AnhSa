import re
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
import streamlit as st
import io

def extract_text_from_pdf(pdf_file):
    """Trích xuất toàn bộ text từ file PDF (file object từ Streamlit)."""
    text = ""
    # pdfplumber -> lấy bảng, text có cấu trúc
    pdf_file.seek(0)
    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    return text

def find_text_before_keyword(text, keyword):
    """
    Extract the number (or text) immediately before the given keyword.
    Example:
        '31 Cartons of Footwear Division of Goods' -> '31'
        '25 Cartons of Apparel Division goods'     -> '25'
    Supports:
        - Any single word between 'Cartons of' and 'Division'
        - Both 'Division of goods' and 'Division goods'
        - Any capitalization of 'Goods' or 'goods'
    """
    # Nếu keyword có chứa 'Cartons of', dùng regex linh hoạt
    if re.search(r"Cartons of", keyword, re.IGNORECASE):
        # Cho phép có hoặc không có 'of' trước 'Goods'
        pattern = r"(\d+)\s+(?=Cartons of \w+ Division(?: of)? [Gg]oods)"
    else:
        # Trường hợp bình thường
        pattern = rf"(\d+)\s+(?={re.escape(keyword)})"

    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1) if match else None

def find_text_before_keyword_2(text, keyword):
    """
    Extract the number (or text) immediately before the given keyword.
    Example: '31 Cartons of Footwear Division Goods' -> '31'
    """
    pattern = rf'(\d+)\s+(?={re.escape(keyword)})'
    match = re.search(pattern, text)
    return match.group(1) if match else None

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

def find_text_after_style(text, keyword, num_chars=50):
    """
    Tìm nội dung sau một keyword.
    Keyword phải có ít nhất 1 khoảng trắng sau từ chính, hoặc dấu ':' / '#:'.
    Hỗ trợ các biến thể: 'MATERIAL ', 'MATERIAL:', 'MATERIAL #:'.
    """
    # Bắt buộc có ít nhất 1 space sau từ, có thể có ':' hoặc '#:' theo sau
    keyword_pattern = re.escape(keyword.rstrip(".:")) + r"(?:[.:]+)?(?:\s+(?:#?:)?)"

    # 1️⃣ Tìm trên cùng dòng
    pattern_same_line = keyword_pattern + r"(.{1," + str(num_chars) + r"})"
    match = re.search(pattern_same_line, text, re.IGNORECASE)
    if match:
        result = match.group(1).strip()
        if result:
            return result

    # 2️⃣ Tìm ở dòng kế tiếp nếu không có gì trên cùng dòng
    pattern_next_line = keyword_pattern + r"\s*\n\s*(.{1," + str(num_chars) + r"})"
    match = re.search(pattern_next_line, text, re.IGNORECASE)
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
    positions = []
    for b in bill_names:
        # if b == "WAYBILL" or b == "INTERIM FOOTWEAR INVOICE (US)":
        if b == "WAYBILL":
            idx = text_lower.find(b.lower())
            positions.append((idx, b))
        else:
        # Regex: tìm tất cả vị trí 'Invoice 1' KHÔNG có '(continue)' ngay sau
            for match in re.finditer(rf'\b{re.escape(b)}\b(?!\s*\(continued\))', text_lower, re.IGNORECASE):
                positions.append((match.start(), b))

    
    positions.sort(key=lambda x: x[0])
    
    # Tách nội dung giữa các bill
    for i, (start_idx, bill) in enumerate(positions):
        end_idx = positions[i+1][0] if i + 1 < len(positions) else len(text)
        content = text[start_idx + len(bill): end_idx].strip()
        sections.append((bill, content))
    return sections

def split_waybill_blocks(text):
    pattern = r"(\d+\s*CTN\s*//.*?\*{34,})"
    blocks = re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return blocks

def extract_bill_sections(text, bill_names, keyword_dict, verbose=False):
    """
    Extract info for each bill section based on grouped keywords.
    Each main key in keyword_dict will become a column name.
    """
    sections = split_by_bill_names(text, bill_names)
    results = []

    for bill_name, content in sections:            
        if bill_name == "WAYBILL":
            blocks = split_waybill_blocks(content)
            for i, block in enumerate(blocks):
                entry = {"Bill Name": f"WAYBILL_{i+1}"}
                for key, kw_list in keyword_dict.items():
                    if not kw_list:
                        entry[key] = "⚠️ Not Found"
                        continue
                    idx = bill_names.index(bill_name)
                    kw = kw_list[idx]
                    if kw == "":
                        entry[key] = None
                        continue
                    if kw == "Cartons of Footwear Division Goods" or kw == "Cartons of Footwear Division of goods":
                        cont = find_text_before_keyword(block, kw) 
                        if cont is None:
                            cont = find_text_before_keyword_2(block, "CNTS OF NIKE FOOTWEAR GOODS")  
                        if cont is None:
                            cont = find_text_before_keyword_2(block, "CARTONS")
                        if cont is None:
                            cont = find_text_before_keyword_2(block, "CTN")
                    elif kw == "PO-Item:":
                        cont = find_text_after_keyword(block, kw)
                        if cont is None:
                            kw = "PO: "
                            cont = find_text_after_keyword(block, kw)
                        if cont is None:
                            kw = "PO:"
                            cont = find_text_after_keyword(block, kw)
                    elif kw == "Invoice#:":
                        cont = find_text_after_keyword(block, kw)
                        if cont is None:
                            kw = "Invoice number:"
                            cont = find_text_after_keyword(block, kw)
                        if cont is None:
                            kw = "INVOICE NUMBER:"
                            cont = find_text_after_keyword(block, kw)
                    elif kw == "Material:":
                        cont = find_text_after_keyword(block, kw)
                        if cont is None:
                            kw = "MATERIAL:"
                            cont = find_text_after_keyword(block, kw)
                    elif kw == "Qty:":
                        cont = find_text_after_keyword(block, kw)
                        if cont is None:
                            kw = "Quantity:"
                            cont = find_text_after_keyword(block, kw)
                        if cont is None:
                            kw = "QUANTITY:"
                            cont = find_text_after_keyword(block, kw)
                    else:
                        cont = find_text_after_keyword(block, kw)

                    if cont:
                        entry[key] = cont
                    else:
                        entry[key] = None
            
                results.append(entry)
            continue 
         
        entry = {"Bill Name": bill_name}
        for key, kw_list in keyword_dict.items():
            if not kw_list:
                entry[key] = "⚠️ Not Found"
                continue
            if bill_name == "INTERIM FOOTWEAR INVOICE (US)":
                print(f"Processing {bill_name} - Keyword: {key}")
            idx = bill_names.index(bill_name)
            kw = kw_list[idx]
            if kw == "":
                entry[key] = None
                continue
            if kw == "Cartons of Footwear Division Goods" or kw == "Cartons of Footwear Division of goods":
                cont = find_text_before_keyword(content, kw) 
                if cont is None:
                    cont = find_text_before_keyword_2(content, "CNTS OF NIKE FOOTWEAR GOODS")  
                if cont is None:
                    cont = find_text_before_keyword_2(content, "CARTONS")
                if cont is None:
                    cont = find_text_after_keyword(content, "Total Cartons: ")
            elif kw == "MATERIAL:" or kw == "INVOICE NO":      
                cont = find_text_after_style(content, kw)
            elif kw == "P.O. #:":
                cont = find_text_after_keyword(content, kw)
                if cont is None:
                    kw = "PO#:"
                    cont = find_text_after_keyword(content, kw)
            elif kw == "PO-Item:":
                cont = find_text_after_keyword(content, kw)
                if cont is None:
                    kw = "PO: "
                    cont = find_text_after_keyword(content, kw)
            elif kw == "ITEM :":
                cont = find_text_after_keyword(content, kw)
                if cont is None:
                    kw = "PO LINE ITEM SEQ. #:"
                    cont = find_text_after_keyword(content, kw)
                if cont is None:
                    kw = "PO Line Item Seq. #:"
                    cont = find_text_after_keyword(content, kw)
            elif kw == "Invoice#:":
                cont = find_text_after_keyword(content, kw)
                if cont is None:
                    kw = "Invoice number:"
                    cont = find_text_after_keyword(content, kw)
            else:
                cont = find_text_after_keyword(content, kw)

            if cont:
                entry[key] = cont
            else:
                entry[key] = None

        results.append(entry)

    return pd.DataFrame(results)


# --- Streamlit UI ---
st.title("📄 PDF to Excel Extractor")
st.write("Upload PDF và tự động trích xuất thông tin theo các keyword.")

uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])

if uploaded_file is not None:
    text = extract_text_from_pdf(uploaded_file)
    # st.subheader("🔎 Preview nội dung PDF")
    # st.text(text[:1000000])
    # Danh sách các keyword cần trích xuất
    bill_names = [
        "WAYBILL",
        "Trading Company Commercial Invoice",
        "Factory Commercial Invoice",
        "Factory Packing List",
        "MULTIPLE COUNTRY OF ORIGIN DECLARATION",
        "Japan Customs Form",
        "INTERIM FOOTWEAR INVOICE (US)"
    ]

    keywords = {
        "INV": ["Invoice#:", "Reference Invoice #:", "Invoice Number:", "Invoice Number.:", "INVOICE NO", "", ""],
        "Total weight": ["", "Total Gross Weight:", "Total Gross Weight:", "Total Gross Kgs:", "", "", ""],
        "PO": ["PO-Item:", "PO#:", "Reference PO#:", "Reference PO#:", "P.O. #:", "", ""],
        "PO line": ["", "PO Line Item Seq.#: ", "PO Line Item Seq. #:", "Item Seq.:", "ITEM :", "", ""],
        "Style": ["Material:", "Material#:", "Material #:", "Material:", "MATERIAL:", "STYLE/CLR:","STYLE/CLR:"],
        "total carton": ["Cartons of Footwear Division of goods", "Cartons of Footwear Division Goods",  "Cartons of Footwear Division Goods", "Cartons of Footwear Division Goods", "Cartons of Footwear Division Goods", "", ""],
        "total quantity": ["Qty:", "Total Invoice ", "Total Invoice Quantity:", "", "","", ""]
    }
        
    df = extract_bill_sections(text, bill_names, keywords)
    for i in range(len(df)):
        if "-" in str(df.loc[i, "PO"]):
            parts = df.loc[i, "PO"].split("-")
            df.loc[i, "PO"] = parts[0]
            df.loc[i, "PO line"] = parts[1] if len(parts) > 1 else None
        df["PO"] = df["PO"].astype(str).str.split(",").str[0]
        df["PO"] = df["PO"].astype(str).str.split(" ").str[0]
        df["PO line"] = df["PO line"].astype(str).str.split(",").str[0]
        df["Style"] = df["Style"].astype(str).str.split(",").str[0]
        if "-" in str(df["Style"].iloc[i]):
            df["Style"].iloc[i] = str(df["Style"].iloc[i]).split(" ")[0]
        else:
            print("No '-' in Style:", df["Style"].iloc[i])
            df["Style"].iloc[i] = " ".join(str(df["Style"].iloc[i]).split(" ")[:2])
        df["PO line"] = df["PO line"].astype(str).str.split(" ").str[0]
        df["INV"] = df["INV"].astype(str).str.split(" ").str[0]
        df["total quantity"] = df["total quantity"].astype(str).str.split(" ").str[0]
        df["total carton"] = df["total carton"].astype(str).str.split("  ").str[0]
        df["total carton"] = df["total carton"].astype(str).str.split(" ").str[0]
        df["total volume"] = None
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
