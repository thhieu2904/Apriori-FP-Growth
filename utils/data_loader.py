# utils/data_loader.py
import pandas as pd
import streamlit as st
import io
import csv # Đảm bảo import csv
import re # Thêm import re
from typing import Tuple, List, Optional, Union, Any # Đảm bảo import Tuple và List
import numpy as np

@st.cache_data
def load_transactions_from_file(
    uploaded_file: Optional[Any],
    invoice_col: str = 'InvoiceNo',
    item_col: str = 'Description',
    sheet_name: Union[int, str] = 0,
    perform_online_retail_cleaning: bool = False,
    quantity_col: str = 'Quantity',
    stock_code_col: str = 'StockCode',
    customer_id_col: str = 'CustomerID',
    country_col: str = 'Country',
    target_customer_id: Optional[Union[str, int]] = None,
    target_country: Optional[str] = None
) -> Tuple[List[List[str]], int, int, pd.DataFrame]:
    """
    Load and process transaction data from CSV or Excel files with advanced cleaning options.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        invoice_col: Column name for invoice/transaction IDs
        item_col: Column name for product descriptions
        sheet_name: Sheet name/index for Excel files
        perform_online_retail_cleaning: Whether to apply Online Retail specific cleaning
        quantity_col: Column name for quantities
        stock_code_col: Column name for stock codes
        customer_id_col: Column name for customer IDs
        country_col: Column name for countries
        target_customer_id: Filter transactions by specific customer ID
        target_country: Filter transactions by specific country
        
    Returns:
        Tuple containing:
        - List of transactions (each transaction is a list of items)
        - Number of unique invoice/transaction IDs found after processing
        - Number of unique item descriptions found after processing
        - Processed DataFrame
    """
    if uploaded_file is None:
        return [], 0, 0, pd.DataFrame()

    # Constants for Online Retail cleaning
    NON_PRODUCT_STOCK_CODES = {
        'POST', 'D', 'M', 'BANK CHARGES', 'AMAZONFEE', 'CRUK', 'DCGSSBOY',
        'DCGSSGIRL', 'PADS', 'DOT', 'S', 'ADJUST', 'ADJUST2', 'SPENSE'
    }
    
    NON_PRODUCT_KEYWORDS = {
        'POSTAGE', 'DOTCOM POSTAGE', 'MANUAL', 'CHARGES', 'AMAZON FEE',
        'BANK CHARGES', 'Discount', 'CRUK Commission', 'SAMPLES',
        'Gift Vouchers', 'Manual', 'Freight', 'Carriage', 'Shipping'
    }

    def load_dataframe() -> Optional[pd.DataFrame]:
        """Helper function to load DataFrame based on file type"""
        try:
            if uploaded_file.name.lower().endswith('.csv'):
                try:
                    # Thử đọc với utf-8 trước
                    return pd.read_csv(uploaded_file, encoding='utf-8')
                except UnicodeDecodeError:
                    # Nếu lỗi, thử với latin1
                    uploaded_file.seek(0) # Reset con trỏ file về đầu
                    return pd.read_csv(uploaded_file, encoding='latin1')
                except Exception as csv_e:
                    st.error(f"Error reading CSV file: {str(csv_e)}")
                    return None
            elif uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
                try:
                    return pd.read_excel(io.BytesIO(uploaded_file.getvalue()), sheet_name=sheet_name)
                except Exception as excel_e:
                    st.error(f"Error reading Excel file: {str(excel_e)}")
                    return None
            else:
                st.error("Unsupported file format. Please upload CSV or Excel (.xlsx, .xls) files.")
                return None
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            return None

    def validate_columns(df: pd.DataFrame, required_cols: List[str]) -> bool:
        """Validate required columns exist in DataFrame"""
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"Missing required columns: {', '.join(missing_cols)}")
            return False
        return True

    # Load initial DataFrame
    df = load_dataframe()
    if df is None or df.empty:
        return [], 0, 0, pd.DataFrame()

    # Determine required columns based on cleaning and filtering options
    required_cols = [invoice_col, item_col]
    if perform_online_retail_cleaning:
        # Chỉ thêm các cột này nếu chúng không trùng với invoice_col hoặc item_col
        if quantity_col not in required_cols: required_cols.append(quantity_col)
        if stock_code_col not in required_cols: required_cols.append(stock_code_col)
        if customer_id_col not in required_cols: required_cols.append(customer_id_col)
    if target_customer_id and customer_id_col not in required_cols:
        required_cols.append(customer_id_col)
    if target_country and country_col not in required_cols:
        required_cols.append(country_col)

    # Loại bỏ các cột trùng lặp trong required_cols nếu có
    required_cols = list(dict.fromkeys(required_cols))

    if not validate_columns(df, required_cols):
        return [], 0, 0, df

    # Apply filters
    if target_customer_id and customer_id_col in df.columns:
        # Chuyển cột CustomerID sang string để xử lý
        df[customer_id_col] = df[customer_id_col].astype(str).str.replace(r'\.0$', '', regex=True)
        
        # Chuẩn hóa target_customer_id thành chuỗi và loại bỏ '.0' nếu có
        target_id_str = str(target_customer_id)
        if target_id_str.endswith('.0'):
            target_id_str = target_id_str[:-2]
            
        df = df[df[customer_id_col] == target_id_str]
        if df.empty:
            st.warning(f"No transactions found for CustomerID: {target_customer_id}")
            return [], 0, 0, df

    if target_country and country_col in df.columns:
        df = df[df[country_col] == target_country]
        if df.empty:
            st.warning(f"No transactions found for Country: {target_country}")
            return [], 0, 0, df

    # Apply Online Retail specific cleaning
    if perform_online_retail_cleaning:
        with st.spinner("Applying Online Retail specific cleaning... This may take a moment for large datasets."):
            # Clean invoice numbers and remove cancellations
            if invoice_col in df.columns:
                 df[invoice_col] = df[invoice_col].astype(str)
                 df = df[~df[invoice_col].str.startswith('C', na=False)] # Thêm na=False để xử lý NaN
            else:
                 st.warning(f"Invoice column '{invoice_col}' not found. Skipping cancellation cleaning.")

            # Clean quantities
            if quantity_col in df.columns:
                df[quantity_col] = pd.to_numeric(df[quantity_col], errors='coerce')
                df = df[df[quantity_col].notna() & (df[quantity_col] > 0)] # Loại bỏ NaN và <= 0
            else:
                st.warning(f"Quantity column '{quantity_col}' not found. Skipping quantity-based cleaning.")
            
            # Clean stock codes
            if stock_code_col in df.columns:
                df[stock_code_col] = df[stock_code_col].astype(str).str.strip().str.upper()
                df = df[~df[stock_code_col].isin(NON_PRODUCT_STOCK_CODES)]
            else:
                 st.warning(f"StockCode column '{stock_code_col}' not found. Skipping StockCode cleaning.")

            # Clean descriptions
            if item_col in df.columns:
                df[item_col] = df[item_col].astype(str).str.strip()
                # Tạo regex pattern từ danh sách keywords
                pattern = '|'.join(re.escape(k) for k in NON_PRODUCT_KEYWORDS)
                if pattern: # Chỉ áp dụng nếu có keywords
                    df = df[~df[item_col].str.contains(pattern, case=False, na=False)]
            else:
                 st.warning(f"Item column '{item_col}' not found. Skipping description cleaning.")

        st.info("✅ Online Retail specific cleaning completed.")

    # Final cleaning steps: Remove rows with missing item descriptions or empty descriptions
    if item_col in df.columns:
        df = df.dropna(subset=[item_col])
        df[item_col] = df[item_col].astype(str).str.strip()
        df = df[df[item_col] != '']
    else:
        st.error(f"Item column '{item_col}' is missing after processing. Cannot create transactions.")
        return [], 0, 0, df


    if df.empty:
        st.info("No valid transactions after cleaning.")
        return [], 0, 0, df

    # Store initial counts before grouping for transactions
    initial_trans_count_before_grouping = df[invoice_col].nunique() if invoice_col in df.columns else 0
    initial_items_count_before_grouping = df[item_col].nunique() if item_col in df.columns else 0


    # Create transactions: Group by invoice and collect items
    if invoice_col in df.columns:
        transactions_series = df.groupby(invoice_col)[item_col].apply(
            lambda x: sorted(list(set(item.strip() for item in x if str(item).strip())))
        )
        # Filter out transactions that became empty after cleaning
        transactions = [trans for trans in transactions_series if trans]
    else:
        st.error(f"Invoice column '{invoice_col}' is missing after processing. Cannot group into transactions.")
        return [], 0, 0, df


    # Calculate counts based on the final processed DataFrame
    # These counts reflect the data *after* all filtering and cleaning,
    # but *before* grouping into transactions (which might remove empty transactions)
    processed_trans_count = df[invoice_col].nunique() if invoice_col in df.columns else 0
    processed_items_count = df[item_col].nunique() if item_col in df.columns else 0


    return (
        transactions, processed_trans_count, processed_items_count, df
    )

def get_unique_items_from_transactions(transactions: List[List[str]]) -> List[str]:
    """
    Get unique items from all transactions.
    
    Args:
        transactions: List of transactions, where each transaction is a list of items
        
    Returns:
        Sorted list of unique items
    """
    # Kiểm tra nếu transactions là None hoặc rỗng
    if not transactions:
        return []
        
    unique_items = set()
    for transaction in transactions:
        # Đảm bảo transaction là một list và chứa các chuỗi
        if isinstance(transaction, list):
            for item in transaction:
                 if isinstance(item, str):
                    unique_items.add(item)
    return sorted(list(unique_items))

def parse_text_area_transactions(data_string: str,
                                 has_header: bool,
                                 item_separator: str,
                                 skip_first_column: bool) -> Tuple[List[List[str]], List[str], int, int]:
    """
    Phân tích chuỗi dữ liệu giao dịch từ ô nhập liệu (định dạng groceries list).
    Mỗi dòng là một giao dịch. Các item được phân tách bởi item_separator.
    Trả về: (danh_sách_giao_dịch, danh_sách_lỗi, số_dòng_có_nội_dung, số_item_duy_nhất_từ_input)
    """
    transactions = []
    errors = []

    if not data_string.strip():
        return [], ["Dữ liệu đầu vào rỗng."], 0, 0

    raw_lines = data_string.strip().split('\n')
    line_iterator = iter(raw_lines)
    initial_content_lines = 0 # Đếm số dòng có nội dung (sau khi bỏ qua header)

    if has_header:
        try:
            header_line = next(line_iterator)
            # errors.append(f"Thông tin: Đã bỏ qua dòng header: '{header_line[:100]}...'") # Ghi chú nếu cần
        except StopIteration:
            errors.append("Lỗi: Dữ liệu chỉ có header hoặc rỗng sau khi chọn bỏ qua header.")
            return [], errors, 0, 0 # Không có dòng nội dung nào

    all_items_in_input = set()
    
    for i, row_str in enumerate(line_iterator):
        line_num_in_input = i + (2 if has_header else 1) # Số dòng trong input gốc
        
        cleaned_row_str = row_str.strip()
        if not cleaned_row_str:
            continue # Bỏ qua dòng trống
        initial_content_lines +=1

        line_io = io.StringIO(cleaned_row_str) # Sử dụng cleaned_row_str
        reader = csv.reader(line_io, delimiter=item_separator)
        parsed_row_list = []
        try:
            parsed_row_list = next(reader)
        except csv.Error as e:
            errors.append(f"Lỗi CSV ở dòng {line_num_in_input}: Không thể phân tích dòng với ký tự phân tách '{item_separator}'. Dòng: '{cleaned_row_str[:100]}...'. Lỗi: {e}")
            continue
        except StopIteration:
             # Trường hợp dòng chỉ chứa khoảng trắng hoặc rỗng sau khi strip() và csv.reader không tìm thấy gì
             continue

        start_index = 1 if skip_first_column and len(parsed_row_list) > 0 else 0
        # Lọc bỏ các item rỗng hoặc chỉ chứa khoảng trắng sau khi strip
        items_in_transaction = [item.strip() for item in parsed_row_list[start_index:] if item and item.strip()]

        if items_in_transaction:
            transactions.append(items_in_transaction)
            for item in items_in_transaction:
                all_items_in_input.add(item)

    if not transactions and not errors and data_string.strip() and initial_content_lines > 0:
        errors.append("Không có giao dịch hợp lệ nào được tạo từ dữ liệu nhập (Groceries List). Kiểm tra định dạng, header, separator và tùy chọn bỏ qua cột đầu.")

    initial_unique_item_count = len(all_items_in_input)
    return transactions, errors, initial_content_lines, initial_unique_item_count

def parse_tx_format_transactions(data_string: str) -> Tuple[List[List[str]], List[str], int, int]:
    """
    Phân tích chuỗi dữ liệu giao dịch theo định dạng 'Tx: [item1, item2,...]'.
    Trả về: (danh_sách_giao_dịch, danh_sách_lỗi, số_dòng_hợp_lệ_ban_đầu, số_item_duy_nhất_ban_đầu)
    """
    transactions = []
    errors = []
    if not data_string.strip():
        return [], ["Dữ liệu đầu vào rỗng."], 0, 0

    lines = data_string.strip().split('\n')
    initial_valid_line_count = 0 # Đếm số dòng có vẻ hợp lệ (không trống, không comment)
    all_items_in_input = set()
    processed_tids = set() # Để kiểm tra TID trùng lặp

    for i, line_content in enumerate(lines):
        line_num_display = i + 1 # Số dòng để hiển thị lỗi
        line_content = line_content.strip()
        if not line_content or line_content.startswith('#'): # Bỏ qua dòng trống hoặc comment
            continue
        initial_valid_line_count += 1

        match_tid = re.match(r'^\s*([^:]+?)\s*:\s*', line_content)
        if not match_tid:
            errors.append(f"Dòng {line_num_display}: Thiếu định dạng 'TID:' ở đầu dòng.")
            continue
        tid = match_tid.group(1).strip()
        if not tid:
            errors.append(f"Dòng {line_num_display}: TID không được rỗng.")
            continue
        if tid in processed_tids:
             errors.append(f"Dòng {line_num_display}: TID '{tid}' bị trùng lặp (vẫn xử lý).")
        processed_tids.add(tid)

        match_items = re.search(r':\s*\[(.*?)\]', line_content)
        if not match_items:
            errors.append(f"Dòng {line_num_display} (TID: {tid}): Không tìm thấy danh sách item dạng '[item1, item2,...]'.")
            continue

        items_str = match_items.group(1)
        # Tách các item, loại bỏ khoảng trắng thừa và item rỗng
        current_transaction_items = [item.strip() for item in items_str.split(',') if item.strip()]

        transactions.append(current_transaction_items) # Thêm cả giao dịch rỗng nếu items_str rỗng
        for item in current_transaction_items:
            all_items_in_input.add(item)

    if not transactions and not errors and data_string.strip() and initial_valid_line_count > 0:
        errors.append("Không có giao dịch nào được tạo từ dữ liệu nhập (Định dạng Tx:[]).")

    initial_unique_item_count = len(all_items_in_input)
    return transactions, errors, initial_valid_line_count, initial_unique_item_count
