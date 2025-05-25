# utils/data_loader.py
import pandas as pd
import streamlit as st
import io # Cần thiết để xử lý uploaded_file như một buffer

@st.cache_data # Cache để tăng tốc độ tải lại khi file không đổi
def load_transactions_from_file(uploaded_file, invoice_col='InvoiceNo', item_col='Description', sheet_name=0):
    """
    Tải dữ liệu giao dịch từ file CSV hoặc Excel được tải lên.
    Mỗi giao dịch là một list các item.
    Loại bỏ các item NaN hoặc rỗng và các giao dịch rỗng.

    Args:
        uploaded_file: Đối tượng file được tải lên từ Streamlit.
        invoice_col (str): Tên cột chứa mã hóa đơn/giao dịch.
        item_col (str): Tên cột chứa tên sản phẩm/item.
        sheet_name (int or str): Tên hoặc chỉ số của trang tính cần đọc (chỉ dùng cho file Excel).
                                 Mặc định là 0 (trang tính đầu tiên).

    Returns:
        list: Danh sách các giao dịch (list of lists of items).
        int: Tổng số giao dịch ban đầu.
        int: Tổng số item duy nhất ban đầu.
    """
    if uploaded_file is None:
        return [], 0, 0

    df = None
    file_name = uploaded_file.name.lower()

    try:
        # Đọc file dựa trên phần mở rộng
        if file_name.endswith('.csv'):
            # Giữ lại encoding detection cho CSV
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                #uploaded_file.seek(0) # Reset con trỏ file nếu đã đọc
                df = pd.read_csv(io.BytesIO(uploaded_file.getvalue()), encoding='latin1') # Đọc lại từ buffer
        elif file_name.endswith(('.xlsx', '.xls')):
            # Sử dụng BytesIO để pandas có thể đọc trực tiếp từ UploadedFile object
            excel_file_buffer = io.BytesIO(uploaded_file.getvalue())
            df = pd.read_excel(excel_file_buffer, sheet_name=sheet_name)
        else:
            st.error("Định dạng file không được hỗ trợ. Vui lòng tải lên file CSV hoặc Excel (.xlsx, .xls).")
            return [], 0, 0
    except Exception as e:
        st.error(f"Lỗi khi đọc file: {e}")
        return [], 0, 0

    if df is None: # Nếu không đọc được df vì lý do nào đó
        return [], 0, 0

    if invoice_col not in df.columns or item_col not in df.columns:
        st.error(f"File phải chứa cột '{invoice_col}' và '{item_col}'. Vui lòng kiểm tra lại tên cột hoặc nội dung file.")
        return [], 0, 0

    # Thống kê ban đầu
    initial_transaction_count = df[invoice_col].nunique()
    initial_unique_items = df[item_col].nunique()

    # Loại bỏ các dòng có item rỗng hoặc NaN
    df.dropna(subset=[item_col], inplace=True)
    df[item_col] = df[item_col].astype(str).str.strip() # Đảm bảo item là string và loại bỏ khoảng trắng thừa
    df = df[df[item_col] != ''] # Loại bỏ các item là chuỗi rỗng

    # Nhóm theo hóa đơn và tạo danh sách item cho mỗi giao dịch
    # Đảm bảo không có item trùng lặp trong một giao dịch
    transactions_series = df.groupby(invoice_col)[item_col].apply(lambda x: sorted(list(set(item.strip() for item in x if str(item.strip())))))
    
    # Loại bỏ các giao dịch rỗng sau khi xử lý
    transactions = [trans for trans in transactions_series if trans]
    
    return transactions, initial_transaction_count, initial_unique_items

def get_unique_items_from_transactions(transactions):
    """
    Lấy danh sách các item duy nhất từ tất cả các giao dịch đã xử lý.
    (Hàm này không thay đổi)
    """
    all_items = set()
    for transaction in transactions:
        for item in transaction:
            all_items.add(item)
    return sorted(list(all_items))