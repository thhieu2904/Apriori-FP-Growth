# utils/visualizers.py
import graphviz
import pandas as pd
import streamlit as st

def display_itemsets_table(st_container, title, itemsets_data, k=None, support_type="Count"):
    """
    Hiển thị bảng các itemset (ứng viên hoặc phổ biến) trong Streamlit.
    
    Args:
        st_container: Streamlit container (e.g., st.expander, st)
        title (str): Tiêu đề cho bảng.
        itemsets_data (dict or list): 
            - Nếu dict: {frozenset: count}
            - Nếu list: [frozenset] (cho ứng viên chưa đếm)
        k (int, optional): Kích thước của itemset (để hiển thị trong tiêu đề).
        support_type (str): "Count" hoặc "Percentage"
    """
    if k:
        st_container.subheader(f"{title} (k={k}, {len(itemsets_data)} mục)")
    else:
        st_container.subheader(f"{title} ({len(itemsets_data)} mục)")

    if not itemsets_data:
        st_container.info("Không có itemset nào để hiển thị.")
        return

    display_data = []
    if isinstance(itemsets_data, dict):
        for itemset, count in itemsets_data.items():
            display_data.append({
                "Itemset": ", ".join(sorted(list(itemset))), 
                support_type: count
            })
    elif isinstance(itemsets_data, list) or isinstance(itemsets_data, set): # Dành cho danh sách ứng viên chưa có count
         for itemset in itemsets_data:
            display_data.append({"Itemset": ", ".join(sorted(list(itemset)))})
    
    if display_data:
        # Sắp xếp theo Itemset để dễ theo dõi
        sorted_display_data = sorted(display_data, key=lambda x: x["Itemset"])
        st_container.dataframe(sorted_display_data)
    else:
        st_container.info("Không có dữ liệu hợp lệ để hiển thị.")


def visualize_fp_tree_interactive(st_container, tree_root, header_table, title="FP-Tree", graph_size=None):
    """
    Trực quan hóa FP-Tree bằng Graphviz và hiển thị trong Streamlit.
    Args:
        st_container: Streamlit container.
        tree_root (TreeNode): Nút gốc của FP-Tree.
        header_table (dict): Bảng header của FP-Tree.
        title (str): Tiêu đề cho biểu đồ.
        graph_size (str, optional): Kích thước của biểu đồ Graphviz, ví dụ "8,6".
                                     Nếu None, biểu đồ sẽ sử dụng use_container_width=True.
    """
    st_container.subheader(title)
    if not tree_root or not tree_root.children: # Nếu cây rỗng (chỉ có root)
        st_container.info("FP-Tree rỗng hoặc chỉ chứa nút root.")
        # Hiển thị Header Table nếu có
        if header_table:
            st_container.write("Header Table:")
            ht_data = [{"Item": item, "Count": data['count'], "Node Link": "->" if data['node'] else "None"} 
                       for item, data in sorted(header_table.items(), key=lambda x: x[1]['count'], reverse=True)]
            st_container.dataframe(ht_data)
        return

    dot = graphviz.Digraph(comment=title, graph_attr={'rankdir': 'TB', 'splines':'true', 'overlap':'false'})
    if graph_size:
        dot.graph_attr['size'] = graph_size
    dot.attr('node', shape='record', style='filled', fillcolor='lightblue', fontname='Arial')
    dot.attr('edge', fontname='Arial', fontsize='10')

    # Nút gốc
    dot.node('root', '{Root}')
    
    # Hàng đợi cho duyệt cây BFS: (node object, parent_dot_id)
    queue = []
    node_id_map = {tree_root: 'root'} # Ánh xạ object node sang ID trong DOT
    
    # Thêm các con trực tiếp của root vào hàng đợi
    for item_name, child_node in tree_root.children.items():
        child_dot_id = f"node_{item_name}_{id(child_node)}" # ID duy nhất
        node_id_map[child_node] = child_dot_id
        queue.append((child_node, 'root'))

    processed_nodes = set(['root'])

    while queue:
        current_node, parent_dot_id = queue.pop(0)
        
        # Tạo ID duy nhất cho nút hiện tại nếu chưa có
        # current_dot_id nên được lấy từ node_id_map vì nó đã được thêm vào khi node được đưa vào queue.
        # Khối if này có thể là một fallback không cần thiết nếu logic thêm vào queue là đúng.
        # Tuy nhiên, nếu nó được kích hoạt, chúng ta cũng cần sửa lỗi truy cập thuộc tính.
        if current_node not in node_id_map: 
            # Điều này không nên xảy ra nếu logic đúng, nhưng để phòng ngừa
            current_node_name_for_id = getattr(current_node, 'name', f'item_obj_{id(current_node)}')
            current_dot_id = f"node_{current_node_name_for_id}_{id(current_node)}"
            node_id_map[current_node] = current_dot_id
        else:
            current_dot_id = node_id_map[current_node]

        if current_dot_id in processed_nodes: # Tránh xử lý lại nếu có cấu trúc phức tạp (dù FP-tree là cây)
            continue
        node_item_name_val = getattr(current_node, 'item_name', 'Unknown') # Sử dụng item_name
        node_label = f"{{{node_item_name_val}|{current_node.count}}}"
        dot.node(current_dot_id, label=node_label)
        dot.edge(parent_dot_id, current_dot_id)
        processed_nodes.add(current_dot_id)

        for child_item, child_node_obj in current_node.children.items():
            child_dot_id_new = f"node_{child_item}_{id(child_node_obj)}"
            node_id_map[child_node_obj] = child_dot_id_new
            queue.append((child_node_obj, current_dot_id))

    # Vẽ các đường liên kết từ Header Table (node links)
    dot.attr('edge', style='dashed', color='gray', constraint='false')
    for item_name, data in header_table.items():
        current_ht_node = data['node']
        prev_dot_id = None
        path_nodes = []
        while current_ht_node:
            # Tìm ID của node này trong map đã tạo khi duyệt cây
            node_dot_id = node_id_map.get(current_ht_node)
            if node_dot_id: # Chỉ vẽ nếu node thực sự có trong cây đã vẽ
                if prev_dot_id: # Vẽ cạnh từ node trước đó trong chuỗi liên kết
                    dot.edge(prev_dot_id, node_dot_id, f"{item_name}-link")
                path_nodes.append(node_dot_id)
                prev_dot_id = node_dot_id
            current_ht_node = current_ht_node.next_node_link # Sử dụng tên thuộc tính đúng

    # Hiển thị Header Table
    if header_table:
        st_container.write("Header Table (Sắp xếp theo tần suất giảm dần):")
        ht_data_display = []
        # Sắp xếp header table theo count giảm dần để hiển thị
        sorted_ht_items = sorted(header_table.items(), key=lambda item: item[1]['count'], reverse=True)
        for item, data in sorted_ht_items:
            ht_data_display.append({
                "Item": item, 
                "Count": data['count'], 
                "Đầu chuỗi Node Link": f"-> {getattr(data['node'], 'item_name', 'Unknown')}:{data['node'].count}" if data['node'] else "Không có"
            })
        st_container.dataframe(ht_data_display)
    
    try:
        if graph_size:
            st_container.graphviz_chart(dot, use_container_width=False)
        else:
            st_container.graphviz_chart(dot, use_container_width=True) # Hành vi mặc định cũ
    except Exception as e:
        st_container.error(f"Lỗi khi vẽ FP-Tree: {e}. Có thể do Graphviz chưa được cài đặt đúng cách.")
        st_container.code(dot.source) # Hiển thị mã DOT để debug

def display_conditional_step_details(st_container, item_suffix, cpb_data, cond_tree_root, cond_header_table, step_number=None):
    """
    Hiển thị chi tiết một bước trong quá trình FP-Growth: CPB và Conditional FP-Tree.
    
    Args:
        st_container: Streamlit container.
        item_suffix (str): Item mà CPB và Conditional FP-Tree được xây dựng cho.
        cpb_data (list): Dữ liệu Conditional Pattern Base. 
                         Ví dụ: [(['A', 'B'], 2), (['A'], 1)]
        cond_tree_root (TreeNode): Nút gốc của Conditional FP-Tree.
        cond_header_table (dict): Bảng header của Conditional FP-Tree.
        step_number (int, optional): Số thứ tự của bước (nếu có).
    """
    title_prefix = f"Bước {step_number}: " if step_number else ""
    st_container.subheader(f"{title_prefix}Xây dựng Cây FP Điều kiện cho Item: '{item_suffix}'")

    # 1. Hiển thị và giải thích Conditional Pattern Base (CPB)
    st_container.markdown(f"**1. Conditional Pattern Base (CPB) cho '{item_suffix}':**")
    st_container.markdown(
        f"""
        Conditional Pattern Base (CPB) bao gồm tất cả các *tiền tố đường dẫn* (prefix paths) trong FP-Tree trước đó 
        mà cùng kết thúc bằng item đang xét (ở đây là '{item_suffix}'). 
        Mỗi đường dẫn trong CPB được gắn với tần suất của item '{item_suffix}' trong đường dẫn gốc đó.
        CPB này sẽ được sử dụng để xây dựng một *Cây FP Điều kiện* (Conditional FP-Tree) mới, 
        là một FP-Tree thu nhỏ chỉ chứa thông tin liên quan đến việc tìm các itemset phổ biến chứa '{item_suffix}'.
        """
    )

    if not cpb_data:
        st_container.info(f"Không có Conditional Pattern Base cho '{item_suffix}' (có thể do item này không đủ min_support trong các nhánh liên quan hoặc là item đơn lẻ).")
    else:
        cpb_display_data = []
        for path, count in cpb_data:
            cpb_display_data.append({
                "Đường dẫn tiền tố (Prefix Path)": ", ".join(path) if path else "∅ (rỗng)", # Hiển thị {} cho đường dẫn rỗng
                "Tần suất (Count)": count
            })
        
        cpb_df = pd.DataFrame(cpb_display_data)
        # Sắp xếp theo Tần suất giảm dần, sau đó theo Đường dẫn
        cpb_df_sorted = cpb_df.sort_values(by=["Tần suất (Count)", "Đường dẫn tiền tố (Prefix Path)"], ascending=[False, True])
        st_container.dataframe(cpb_df_sorted)

    # 2. Trực quan hóa Conditional FP-Tree
    st_container.markdown(f"**2. Cây FP Điều kiện (Conditional FP-Tree) cho '{item_suffix}':**")
    if cond_tree_root and (cond_tree_root.children or getattr(cond_tree_root, 'item_name', None) is not None) : # Vẽ nếu có con hoặc là cây chỉ có 1 nút (item_name của root khác None)
        visualize_fp_tree_interactive(st_container, cond_tree_root, cond_header_table,
                                      title=f"Conditional FP-Tree cho '{item_suffix}'",
                                      graph_size="6,4") # Đặt kích thước nhỏ hơn cho cây điều kiện
                                      # Bạn có thể điều chỉnh "6,4" thành kích thước mong muốn
    else:
         st_container.info(f"Không có Cây FP Điều kiện nào được xây dựng hoặc cây rỗng cho '{item_suffix}'. "
                           "Điều này có thể xảy ra nếu CPB rỗng, không có item nào trong CPB đạt min_support tương đối, "
                           "hoặc item đang xét là một phần của itemset 1-phần tử đã được tìm thấy.")
         # Vẫn có thể hiển thị header table của cây điều kiện nếu nó được tạo ra (dù cây có thể rỗng)
         if cond_header_table:
            st_container.caption("Header Table của Cây Điều kiện (nếu có):")
            ht_data_display = [{"Item": item, "Count": data['count'], "Đầu chuỗi Node Link": f"-> {getattr(data['node'], 'item_name', 'Unknown')}:{data['node'].count}" if data['node'] else "Không có"} for item, data in sorted(cond_header_table.items(), key=lambda x: x[1]['count'], reverse=True)]
            st_container.dataframe(ht_data_display)

def display_rules_table(st_container, title, rules_data, num_transactions):
    """
    Hiển thị bảng các luật kết hợp.
    
    Args:
        st_container: Streamlit container.
        title (str): Tiêu đề cho bảng.
        rules_data (list of dicts): Dữ liệu luật, mỗi dict chứa 'antecedent', 'consequent', 
                                     'support', 'confidence', 'lift'.
        num_transactions (int): Tổng số giao dịch để tính support count nếu cần.
    """
    st_container.subheader(f"{title} ({len(rules_data)} luật)")
    if not rules_data:
        st_container.info("Không có luật nào được tạo ra với các ngưỡng đã cho.")
        return

    formatted_rules = []
    for rule in rules_data:
        formatted_rules.append({
            "Tiền đề (Antecedent)": ", ".join(rule['antecedent']),
            "Hậu quả (Consequent)": ", ".join(rule['consequent']),
            "Support": f"{rule['support']:.4f}",
            "Confidence": f"{rule['confidence']:.4f}",
            "Lift": f"{rule['lift']:.2f}",
            # "Support Count": int(rule['support'] * num_transactions) # Tính support count
        })
    
    rules_df = pd.DataFrame(formatted_rules)
    # Sắp xếp theo Lift và Confidence giảm dần
    rules_df_sorted = rules_df.sort_values(by=['Lift', 'Confidence'], ascending=[False, False])
    st_container.dataframe(rules_df_sorted)
