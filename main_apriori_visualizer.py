# main_apriori_visualizer.py
import streamlit as st
import math
import pandas as pd
from algorithms.apriori_logic import AprioriAlgorithm
from utils.data_loader import load_transactions_from_file, get_unique_items_from_transactions, parse_text_area_transactions, parse_tx_format_transactions
from utils.metrics_collector import PerformanceMetrics
from utils.visualizers import display_itemsets_table, display_rules_table

st.set_page_config(layout="wide", page_title="Apriori Visualizer")
st.title("📊 Trình Trực Quan Hóa Thuật Toán Apriori")
st.markdown("""
    Ứng dụng này cho phép bạn tải lên dữ liệu giao dịch, chạy thuật toán Apriori,
    và trực quan hóa các bước trung gian cũng như kết quả cuối cùng.
""")

# --- Sidebar ---
st.sidebar.header("📁 Tải Dữ Liệu và Tham Số")
input_method = st.sidebar.radio(
    "Chọn phương thức nhập liệu:",
    ("Tải file lên", "Nhập trực tiếp (Groceries List)", "Nhập trực tiếp (Định dạng Tx: [])")
)

uploaded_file = None
manual_transactions_str = "" # For Groceries List format
manual_tx_format_str = ""    # For Tx: [] format
default_tx_format_data = """T1: [A, B, C]
T2: [B, C, D]
T3: [A, C, D, E]
T4: [A, D, E]
T5: [A, B, C, E]"""
default_groceries_data = "itemA,itemB,itemC\nitemA,itemD\nitemB,itemE,itemC"

manual_has_header = False # Default for Groceries List
manual_item_separator = ',' # Default for Groceries List
manual_skip_first_col = False # Default for Groceries List

# Các widget cho nhập liệu trực tiếp sẽ được hiển thị trước
if input_method == "Nhập trực tiếp (Groceries List)":
    manual_transactions_str = st.sidebar.text_area(
        "Nhập giao dịch (mỗi dòng một giao dịch, item cách nhau bằng ký tự phân tách):",
        height=200,
        value=default_groceries_data
    )
    manual_item_separator = st.sidebar.text_input("Ký tự phân tách item:", value=",")
    col_header, col_skip = st.sidebar.columns(2)
    manual_has_header = col_header.checkbox("Dòng đầu là header?", value=False)
    manual_skip_first_col = col_skip.checkbox("Bỏ qua cột đầu tiên mỗi dòng?", value=False, help="Hữu ích cho định dạng như groceries.csv có cột số lượng item ở đầu.")
elif input_method == "Nhập trực tiếp (Định dạng Tx: [])":
    manual_tx_format_str = st.sidebar.text_area(
        "Nhập giao dịch (định dạng 'Tx: [item1, item2,...]'):",
        height=200,
        value=default_tx_format_data
    )
elif input_method == "Tải file lên":
    uploaded_file = st.sidebar.file_uploader("Chọn file (đã tiền xử lý nếu cần)", type=['csv', 'xlsx', 'xls'])
    # Các widget cấu hình cột sẽ hiển thị bên dưới, sau dấu ngăn cách

st.sidebar.markdown("---") # Ngăn cách chung

# Các tùy chọn cho Tải file lên và Lọc dữ liệu (Nâng cao) sẽ nằm ở đây
# Các biến này cần được định nghĩa ở scope ngoài để không bị lỗi khi input_method khác "Tải file lên"
invoice_col_name = "InvoiceNo" # Giá trị mặc định
item_col_name = "Description"  # Giá trị mặc định
customer_id_col_name = "CustomerID"
country_col_name = "Country"
perform_cleaning = False
target_customer_id_input = ""
target_country_input = ""

if input_method == "Tải file lên":
    invoice_col_name = st.sidebar.text_input("Tên cột Mã Hóa Đơn/Giao Dịch (cho file)", invoice_col_name)
    item_col_name = st.sidebar.text_input("Tên cột Tên Sản Phẩm/Item (cho file)", item_col_name)
    st.sidebar.markdown("---") # Ngăn cách trước khi vào phần lọc

st.sidebar.subheader("Tùy Chọn Lọc Dữ Liệu (Nâng Cao - chỉ áp dụng khi tải file)")
customer_id_col_name = st.sidebar.text_input("Tên cột Mã Khách Hàng (nếu lọc)", customer_id_col_name, disabled=(input_method != "Tải file lên"))
country_col_name = st.sidebar.text_input("Tên cột Quốc Gia (nếu lọc)", country_col_name, disabled=(input_method != "Tải file lên"))
perform_cleaning = st.sidebar.checkbox(
    "Áp dụng làm sạch chuyên biệt cho Online Retail (cho file)?", 
    value=perform_cleaning, 
    help="Nếu chọn, sẽ áp dụng các quy tắc làm sạch như loại bỏ mã 'POST', 'MANUAL', giao dịch hủy 'C', Quantity <=0, v.v.",
    disabled=(input_method != "Tải file lên")
)
target_customer_id_input = st.sidebar.text_input("Lọc theo Mã Khách Hàng (để trống nếu không lọc)", target_customer_id_input, help="Nhập chính xác ID khách hàng. Ví dụ: 12345", disabled=(input_method != "Tải file lên"))
target_country_input = st.sidebar.text_input("Lọc theo Quốc Gia (để trống nếu không lọc)", target_country_input, help="Nhập chính xác tên quốc gia. Ví dụ: United Kingdom", disabled=(input_method != "Tải file lên"))

st.sidebar.markdown("---")
st.sidebar.subheader("Tham Số Thuật Toán")
min_support_percentage = st.sidebar.slider("Ngưỡng Support Tối Thiểu (%)", 0.1, 50.0, 5.0, 0.1,
                                           help="Tỷ lệ phần trăm giao dịch tối thiểu mà một itemset phải xuất hiện.")
min_confidence_percentage = st.sidebar.slider("Ngưỡng Confidence Tối Thiểu (%)", 1.0, 100.0, 50.0, 1.0,
                                     help="Độ tin cậy tối thiểu của một luật kết hợp.")

# --- Main Area ---
transactions = None
initial_trans_count = 0
initial_items_count = 0
parse_errors_main = []

if input_method == "Tải file lên":
    if uploaded_file:
        target_customer_id_to_pass = target_customer_id_input.strip() if target_customer_id_input.strip() else None
        target_country_to_pass = target_country_input.strip() if target_country_input.strip() else None
        transactions, initial_trans_count, initial_items_count, processed_df = load_transactions_from_file(
            uploaded_file,
            invoice_col=invoice_col_name,
            item_col=item_col_name,
            perform_online_retail_cleaning=perform_cleaning,
            customer_id_col=customer_id_col_name,
            country_col=country_col_name,
            target_customer_id=target_customer_id_to_pass,
            target_country=target_country_to_pass
        )
elif input_method == "Nhập trực tiếp (Groceries List)":
    if manual_transactions_str.strip():
        transactions, parse_errors_main, initial_trans_count, initial_items_count = parse_text_area_transactions(
            manual_transactions_str, manual_has_header, manual_item_separator, manual_skip_first_col
        )
        if parse_errors_main:
            for error_msg in parse_errors_main:
                st.sidebar.error(f"Lỗi nhập liệu (Groceries): {error_msg}")
elif input_method == "Nhập trực tiếp (Định dạng Tx: [])":
    if manual_tx_format_str.strip():
        transactions, parse_errors_main, initial_trans_count, initial_items_count = parse_tx_format_transactions(
            manual_tx_format_str
        )
        if parse_errors_main:
            for error_msg in parse_errors_main:
                st.sidebar.error(f"Lỗi nhập liệu (Tx:[]): {error_msg}")


if transactions is not None:

    if transactions:
        num_total_transactions = len(transactions)
        unique_items_processed = get_unique_items_from_transactions(transactions)
        
        st.info(f"""
        **Thông tin dữ liệu đã xử lý:**
        - Số dòng/giao dịch đầu vào (trước khi lọc giao dịch rỗng): {initial_trans_count}
        - Số sản phẩm duy nhất đầu vào: {initial_items_count}
        - Số giao dịch đã xử lý (sau khi loại bỏ giao dịch rỗng): {num_total_transactions}
        - Số sản phẩm duy nhất đã xử lý: {len(unique_items_processed)}
        """)

        min_support_count = 0
        if num_total_transactions > 0:
            min_support_count = math.ceil((min_support_percentage / 100.0) * num_total_transactions)
        
        actual_min_support_percentage = (min_support_count / num_total_transactions) * 100 if num_total_transactions > 0 else 0
        
        st.sidebar.markdown("---")
        st.sidebar.write(f"**Ngưỡng Support Tuyệt Đối:** `{min_support_count}` giao dịch")
        st.sidebar.write(f"(Tương đương khoảng `{actual_min_support_percentage:.2f}%`)")
        
        min_confidence_threshold = min_confidence_percentage / 100.0
        st.sidebar.write(f"**Ngưỡng Confidence:** `{min_confidence_threshold:.2f}`")

        # Hiển thị nút Chạy Thuật Toán Apriori
        run_apriori_button = st.sidebar.button("🚀 Chạy Thuật Toán Apriori", type="primary", use_container_width=True)
        
        # Thêm một khoảng trống nhỏ phía trên nút Reset
        st.sidebar.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

        # Hiển thị nút Đặt lại Tất cả
        reset_button_apriori = st.sidebar.button("🔄 Đặt lại Tất cả", type="primary", use_container_width=True, key="reset_all_apriori_main")
        
        if reset_button_apriori: # Xử lý logic khi nút Reset được nhấn
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        if run_apriori_button:
            if num_total_transactions == 0 and not transactions:
                st.error("Không có giao dịch nào để xử lý. Vui lòng kiểm tra lại file dữ liệu.")
            elif min_support_count == 0 and num_total_transactions > 0 : 
                 st.error("Ngưỡng support tuyệt đối là 0. Vui lòng tăng ngưỡng support tối thiểu (%) để có kết quả ý nghĩa.")
            else:
                st.session_state.apriori_run_completed = False
                st.session_state.apriori_frequent_itemsets = {}
                st.session_state.apriori_intermediate_steps = []
                st.session_state.apriori_rules = []
                st.session_state.apriori_metrics = None

                metrics_collector = PerformanceMetrics()
                apriori_algo = AprioriAlgorithm(transactions, min_support_count, metrics_collector)
                
                with st.spinner("⏳ Đang chạy thuật toán Apriori... Vui lòng chờ."):
                    frequent_itemsets, intermediate_steps = apriori_algo.run()
                    
                    st.session_state.apriori_frequent_itemsets = frequent_itemsets
                    st.session_state.apriori_intermediate_steps = intermediate_steps
                    st.session_state.apriori_metrics = metrics_collector 

                    if frequent_itemsets:
                        rules = apriori_algo.generate_association_rules(frequent_itemsets, min_confidence_threshold)
                        st.session_state.apriori_rules = rules
                    else:
                        st.session_state.apriori_rules = []
                
                st.session_state.apriori_run_completed = True
                st.success("✅ Thuật toán Apriori đã chạy xong!")

        # --- Hiển thị kết quả ---
        if st.session_state.get("apriori_run_completed", False):
            metrics: PerformanceMetrics = st.session_state.get("apriori_metrics")
            
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Tổng Quan & Số Liệu", 
                "🔄 Bước Trung Gian", 
                "💎 Tập Mục Phổ Biến", 
                "📜 Luật Kết Hợp"
            ])

            with tab1:
                st.header("Tổng Quan Thực Thi và Số Liệu Hiệu Năng")
                if metrics:
                    overall_summary = metrics.get_overall_metrics_summary()
                    st.metric(label="Tổng Thời Gian Chạy", value=f"{overall_summary['total_duration_seconds']} giây")
                    col_mem1, col_mem2, col_mem3 = st.columns(3)
                    col_mem1.metric(label="Bộ Nhớ Ban Đầu", value=f"{overall_summary['initial_memory_MB']} MB")
                    col_mem2.metric(label="Bộ Nhớ Cuối Cùng", value=f"{overall_summary['final_memory_MB']} MB")
                    col_mem3.metric(label="Bộ Nhớ Đỉnh (ước tính)", value=f"{overall_summary['peak_memory_usage_MB']} MB")

                    st.subheader("Số liệu chi tiết của Apriori:")
                    apriori_specific_metrics = metrics.get_apriori_metrics_summary()
                    st.write(f"- Tổng số ứng viên đã tạo: `{apriori_specific_metrics['total_candidates_generated']}`")
                    st.write(f"- Tổng số tập mục phổ biến đã tìm thấy: `{apriori_specific_metrics['total_frequent_itemsets_found']}`")
                    
                    if apriori_specific_metrics['candidates_per_k']:
                         st.write("Chi tiết ứng viên theo k:")
                         st.json(apriori_specific_metrics['candidates_per_k'])
                    if apriori_specific_metrics['frequent_itemsets_per_k']:
                         st.write("Chi tiết tập mục phổ biến theo k:")
                         st.json(apriori_specific_metrics['frequent_itemsets_per_k'])


                    st.subheader("Thời Gian và Bộ Nhớ Từng Bước Chính:")
                    step_metrics_df = pd.DataFrame(metrics.get_step_metrics_table())
                    if not step_metrics_df.empty:
                        step_metrics_df['duration_seconds'] = step_metrics_df['duration_seconds'].apply(lambda x: f"{x:.4f}")
                        step_metrics_df['memory_before_MB'] = step_metrics_df['memory_before_MB'].apply(lambda x: f"{x:.2f}")
                        step_metrics_df['memory_after_MB'] = step_metrics_df['memory_after_MB'].apply(lambda x: f"{x:.2f}")
                        step_metrics_df['memory_change_MB'] = step_metrics_df['memory_change_MB'].apply(lambda x: f"{x:+.2f}")
                        st.dataframe(step_metrics_df[[
                            "step_name", "duration_seconds", 
                            "memory_before_MB", "memory_after_MB", "memory_change_MB",
                            "candidate_count", "frequent_count" 
                        ]], hide_index=True)
                    else:
                        st.info("Không có dữ liệu chi tiết từng bước.")
                else:
                    st.warning("Không có số liệu hiệu năng để hiển thị.")

            with tab2:
                st.header("Các Bước Trung Gian của Thuật Toán Apriori")
                intermediate_steps = st.session_state.get("apriori_intermediate_steps", [])
                if not intermediate_steps:
                    st.info("Không có bước trung gian nào được ghi lại hoặc thuật toán chưa chạy.")
                else:
                    for i, step_log in enumerate(intermediate_steps):
                        step_title = f"Bước {i+1}: {step_log['step_name']}"
                        if 'k' in step_log: step_title += f" (k={step_log['k']})"
                        
                        with st.expander(step_title, expanded=False):
                            if 'notes' in step_log:
                                st.caption(f"Ghi chú: {step_log['notes']}")
                            
                            data_content = step_log['data']
                            if isinstance(data_content, dict): 
                                display_itemsets_table(st, "Dữ liệu bước:", data_content, k=step_log.get('k'))
                            elif isinstance(data_content, list) and data_content and isinstance(data_content[0], frozenset): 
                                display_itemsets_table(st, "Dữ liệu bước (ứng viên):", data_content, k=step_log.get('k'))
                            elif isinstance(data_content, list) and data_content and isinstance(data_content[0], dict) and 'antecedent' in data_content[0]: 
                                display_rules_table(st, "Luật được tạo ở bước này:", data_content, num_total_transactions)
                            else: 
                                st.json(data_content, expanded=False)
            
            with tab3:
                st.header("💎 Các Tập Mục Phổ Biến (Frequent Itemsets)")
                frequent_itemsets = st.session_state.get("apriori_frequent_itemsets", {})
                if not frequent_itemsets:
                    st.info(f"Không tìm thấy tập mục phổ biến nào với ngưỡng support = {min_support_count} ({actual_min_support_percentage:.2f}%).")
                else:
                    st.success(f"Tìm thấy tổng cộng {sum(len(itemsets) for itemsets in frequent_itemsets.values() if isinstance(itemsets, dict)) if isinstance(frequent_itemsets,dict) and all(isinstance(val, dict) for val in frequent_itemsets.values()) else len(frequent_itemsets)} tập mục phổ biến.")
                    
                    if isinstance(frequent_itemsets, dict) and frequent_itemsets and isinstance(next(iter(frequent_itemsets.values())), dict):
                         for k_val, k_itemsets in sorted(frequent_itemsets.items()):
                             display_itemsets_table(st, f"Các tập {k_val}-itemset phổ biến", k_itemsets, k=k_val)
                    else: 
                        display_itemsets_table(st, "Tất cả các tập mục phổ biến", frequent_itemsets)


            with tab4:
                st.header("📜 Luật Kết Hợp")
                rules = st.session_state.get("apriori_rules", [])
                if not rules:
                    st.info(f"Không có luật kết hợp nào được tạo ra với min_confidence = {min_confidence_threshold:.2f} (hoặc không có tập mục phổ biến nào để sinh luật).")
                else:
                    st.success(f"Tìm thấy {len(rules)} luật kết hợp.")
                    display_rules_table(st, f"Các Luật Kết Hợp (min_confidence={min_confidence_threshold:.2f})", 
                                        rules, num_total_transactions)
    else: 
        if input_method == "Tải file lên" and uploaded_file: 
            st.warning("Không thể xử lý file dữ liệu đã tải lên. Vui lòng kiểm tra định dạng và nội dung file.")
        elif input_method.startswith("Nhập trực tiếp") and (manual_transactions_str.strip() or manual_tx_format_str.strip()) and not transactions and parse_errors_main:
            st.warning("Dữ liệu nhập trực tiếp có lỗi và không tạo ra được giao dịch nào. Vui lòng kiểm tra thông báo lỗi ở thanh bên.")
        elif not uploaded_file and not manual_transactions_str.strip() and not manual_tx_format_str.strip():
            st.info("Chào mừng! Vui lòng chọn phương thức nhập liệu và cung cấp dữ liệu ở thanh bên để bắt đầu.")
else: 
    st.info("Chào mừng! Vui lòng chọn phương thức nhập liệu và cung cấp dữ liệu ở thanh bên để bắt đầu.")

st.sidebar.markdown("---")
st.sidebar.markdown("Đồ án KPDL - So sánh Apriori và FP-Growth")
    