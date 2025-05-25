# main_fp_growth_visualizer.py
import streamlit as st
import pandas as pd
from algorithms.fp_growth_logic import FPGrowthAlgorithm, TreeNode # Cần TreeNode để check type
from utils.data_loader import load_transactions_from_csv, get_unique_items_from_transactions
from utils.metrics_collector import PerformanceMetrics
from utils.visualizers import display_itemsets_table, display_rules_table, visualize_fp_tree_interactive

st.set_page_config(layout="wide", page_title="FP-Growth Visualizer")
st.title("🌳 Trình Trực Quan Hóa Thuật Toán FP-Growth")
st.markdown("""
    Ứng dụng này cho phép bạn tải lên dữ liệu giao dịch, chạy thuật toán FP-Growth,
    trực quan hóa FP-Tree, các bước trung gian và kết quả cuối cùng.
""")

# --- Sidebar ---
st.sidebar.header("📁 Tải Dữ Liệu và Tham Số")
uploaded_file = st.sidebar.file_uploader("Chọn file CSV (đã tiền xử lý nếu cần)", type="csv")

invoice_col_name = st.sidebar.text_input("Tên cột Mã Hóa Đơn/Giao Dịch", "InvoiceNo")
item_col_name = st.sidebar.text_input("Tên cột Tên Sản Phẩm/Item", "Description")

min_support_percentage = st.sidebar.slider("Ngưỡng Support Tối Thiểu (%)", 0.1, 10.0, 1.0, 0.1,
                                           help="Tỷ lệ phần trăm giao dịch tối thiểu mà một itemset phải xuất hiện.")
min_confidence_percentage = st.sidebar.slider("Ngưỡng Confidence Tối Thiểu (%)", 1.0, 100.0, 50.0, 1.0,
                                     help="Độ tin cậy tối thiểu của một luật kết hợp.")

# --- Main Area ---
if uploaded_file:
    transactions, initial_trans_count, initial_items_count = load_transactions_from_csv(
        uploaded_file,
        invoice_col=invoice_col_name,
        item_col=item_col_name
    )

    if transactions:
        num_total_transactions = len(transactions)
        unique_items_processed = get_unique_items_from_transactions(transactions)
        
        st.info(f"""
        **Thông tin dữ liệu đã tải:**
        - Số giao dịch ban đầu (ước tính từ file): {initial_trans_count}
        - Số sản phẩm duy nhất ban đầu (ước tính từ file): {initial_items_count}
        - Số giao dịch đã xử lý (sau khi loại bỏ giao dịch rỗng): {num_total_transactions}
        - Số sản phẩm duy nhất đã xử lý: {len(unique_items_processed)}
        """)

        min_support_count = int((min_support_percentage / 100.0) * num_total_transactions)
        actual_min_support_percentage = (min_support_count / num_total_transactions) * 100 if num_total_transactions > 0 else 0
        
        st.sidebar.markdown("---")
        st.sidebar.write(f"**Ngưỡng Support Tuyệt Đối:** `{min_support_count}` giao dịch")
        st.sidebar.write(f"(Tương đương khoảng `{actual_min_support_percentage:.2f}%`)")
        
        min_confidence_threshold = min_confidence_percentage / 100.0
        st.sidebar.write(f"**Ngưỡng Confidence:** `{min_confidence_threshold:.2f}`")

        if st.sidebar.button("🚀 Chạy Thuật Toán FP-Growth", type="primary"):
            if num_total_transactions == 0:
                st.error("Không có giao dịch nào để xử lý. Vui lòng kiểm tra lại file dữ liệu.")
            else:
                st.session_state.fpgrowth_run_completed = False
                st.session_state.fpgrowth_frequent_itemsets = {}
                st.session_state.fpgrowth_intermediate_steps = []
                st.session_state.fpgrowth_rules = []
                st.session_state.fpgrowth_metrics = None

                metrics_collector = PerformanceMetrics()
                fpgrowth_algo = FPGrowthAlgorithm(transactions, min_support_count, metrics_collector)
                
                with st.spinner("⏳ Đang chạy thuật toán FP-Growth... Vui lòng chờ."):
                    frequent_itemsets, intermediate_steps = fpgrowth_algo.run()
                    
                    st.session_state.fpgrowth_frequent_itemsets = frequent_itemsets
                    st.session_state.fpgrowth_intermediate_steps = intermediate_steps
                    st.session_state.fpgrowth_metrics = metrics_collector

                    if frequent_itemsets:
                        rules = fpgrowth_algo.generate_association_rules(frequent_itemsets, min_confidence_threshold)
                        st.session_state.fpgrowth_rules = rules
                    else:
                        st.session_state.fpgrowth_rules = []
                
                st.session_state.fpgrowth_run_completed = True
                st.success("✅ Thuật toán FP-Growth đã chạy xong!")

        # --- Hiển thị kết quả ---
        if st.session_state.get("fpgrowth_run_completed", False):
            metrics: PerformanceMetrics = st.session_state.get("fpgrowth_metrics")
            
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Tổng Quan & Số Liệu", 
                "🔄 Bước Trung Gian & FP-Tree", 
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

                    st.subheader("Số liệu chi tiết của FP-Growth:")
                    fpgrowth_specific_metrics = metrics.get_fp_growth_metrics_summary()
                    st.write(f"- Số nút trong FP-Tree chính (ước tính): `{fpgrowth_specific_metrics['nodes_in_fp_tree']}`")
                    st.write(f"- Số Conditional FP-Tree đã xây dựng: `{fpgrowth_specific_metrics['conditional_fp_trees_built']}`")


                    st.subheader("Thời Gian và Bộ Nhớ Từng Bước Chính:")
                    step_metrics_df = pd.DataFrame(metrics.get_step_metrics_table())
                    if not step_metrics_df.empty:
                        step_metrics_df['duration_seconds'] = step_metrics_df['duration_seconds'].apply(lambda x: f"{x:.4f}")
                        step_metrics_df['memory_before_MB'] = step_metrics_df['memory_before_MB'].apply(lambda x: f"{x:.2f}")
                        step_metrics_df['memory_after_MB'] = step_metrics_df['memory_after_MB'].apply(lambda x: f"{x:.2f}")
                        step_metrics_df['memory_change_MB'] = step_metrics_df['memory_change_MB'].apply(lambda x: f"{x:+.2f}")
                        st.dataframe(step_metrics_df[[
                            "step_name", "duration_seconds", 
                            "memory_before_MB", "memory_after_MB", "memory_change_MB"
                            # Thêm các cột metrics cụ thể của FP-Growth nếu có trong additional_info
                        ]], hide_index=True)
                    else:
                        st.info("Không có dữ liệu chi tiết từng bước.")
                else:
                    st.warning("Không có số liệu hiệu năng để hiển thị.")

            with tab2:
                st.header("Các Bước Trung Gian và Trực Quan Hóa FP-Tree")
                intermediate_steps = st.session_state.get("fpgrowth_intermediate_steps", [])
                if not intermediate_steps:
                    st.info("Không có bước trung gian nào được ghi lại hoặc thuật toán chưa chạy.")
                else:
                    for i, step_log in enumerate(intermediate_steps):
                        step_title = f"Bước {i+1}: {step_log['step_name']}"
                        
                        with st.expander(step_title, expanded=False):
                            if 'notes' in step_log:
                                st.caption(f"Ghi chú: {step_log['notes']}")
                            
                            data_content = step_log.get('data', {})
                            
                            # Trực quan hóa cây nếu có
                            tree_to_visualize = step_log.get('tree_dot_object') # Đây là root_node
                            header_table_for_vis = step_log.get('header_table')

                            if isinstance(tree_to_visualize, TreeNode) and header_table_for_vis:
                                visualize_fp_tree_interactive(st, tree_to_visualize, header_table_for_vis, title=f"Trực quan hóa cho: {step_log['step_name']}")
                            elif header_table_for_vis and not tree_to_visualize: # Chỉ có header table (ví dụ cây rỗng)
                                visualize_fp_tree_interactive(st, None, header_table_for_vis, title=f"Header Table cho: {step_log['step_name']}")


                            # Hiển thị dữ liệu khác của bước
                            if data_content:
                                if isinstance(data_content, dict) and "counts" in data_content and "order" in data_content: # L1 và thứ tự
                                    st.write("Đếm 1-itemset phổ biến:", data_content["counts"])
                                    st.write("Thứ tự item phổ biến (L):", data_content["order"])
                                elif isinstance(data_content, dict) and "cpb" in data_content: # Conditional Pattern Base
                                    st.write(f"Conditional Pattern Base cho '{data_content.get('item','N/A')}' (tiền tố: {data_content.get('prefix','N/A')}):")
                                    if data_content["cpb"]:
                                        st.json(data_content["cpb"], expanded=False)
                                    else:
                                        st.info("Conditional Pattern Base rỗng.")
                                elif isinstance(data_content, dict) and "message" in data_content:
                                     st.write(data_content["message"])
                                elif isinstance(data_content, list) and data_content and isinstance(data_content[0], dict) and 'antecedent' in data_content[0]: # Rules
                                    display_rules_table(st, "Luật được tạo ở bước này:", data_content, num_total_transactions)
                                elif isinstance(data_content, dict) and not tree_to_visualize: # Các dict khác không phải cây
                                    st.json(data_content, expanded=False)
                                elif isinstance(data_content, list): # List các giao dịch đã sắp xếp
                                     st.write("Ví dụ dữ liệu (5 giao dịch đầu):")
                                     st.json(data_content[:5] if isinstance(data_content, list) else data_content, expanded=False)


            with tab3:
                st.header("💎 Các Tập Mục Phổ Biến (Frequent Itemsets)")
                frequent_itemsets = st.session_state.get("fpgrowth_frequent_itemsets", {})
                if not frequent_itemsets:
                    st.info(f"Không tìm thấy tập mục phổ biến nào với ngưỡng support = {min_support_count} ({actual_min_support_percentage:.2f}%).")
                else:
                    st.success(f"Tìm thấy tổng cộng {len(frequent_itemsets)} tập mục phổ biến.")
                    display_itemsets_table(st, "Tất cả các tập mục phổ biến", frequent_itemsets)
            
            with tab4:
                st.header("📜 Luật Kết Hợp")
                rules = st.session_state.get("fpgrowth_rules", [])
                if not rules:
                    st.info(f"Không có luật kết hợp nào được tạo ra với min_confidence = {min_confidence_threshold:.2f}.")
                else:
                    st.success(f"Tìm thấy {len(rules)} luật kết hợp.")
                    display_rules_table(st, f"Các Luật Kết Hợp (min_confidence={min_confidence_threshold:.2f})", 
                                        rules, num_total_transactions)
    else:
        if uploaded_file:
            st.warning("Không thể xử lý file dữ liệu. Vui lòng kiểm tra định dạng và nội dung file.")
else:
    st.info("Chào mừng! Vui lòng tải lên file CSV dữ liệu giao dịch ở thanh bên để bắt đầu.")

st.sidebar.markdown("---")
st.sidebar.markdown("Đồ án KHDL - So sánh Apriori và FP-Growth")

