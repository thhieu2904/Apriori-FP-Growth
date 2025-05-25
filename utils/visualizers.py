# utils/visualizers.py
import graphviz
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


def visualize_fp_tree_interactive(st_container, tree_root, header_table, title="FP-Tree"):
    """
    Trực quan hóa FP-Tree bằng Graphviz và hiển thị trong Streamlit.
    Args:
        st_container: Streamlit container.
        tree_root (TreeNode): Nút gốc của FP-Tree.
        header_table (dict): Bảng header của FP-Tree.
        title (str): Tiêu đề cho biểu đồ.
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
        if current_node not in node_id_map:
            # Điều này không nên xảy ra nếu logic đúng, nhưng để phòng ngừa
            current_dot_id = f"node_{current_node.item}_{id(current_node)}"
            node_id_map[current_node] = current_dot_id
        else:
            current_dot_id = node_id_map[current_node]

        if current_dot_id in processed_nodes: # Tránh xử lý lại nếu có cấu trúc phức tạp (dù FP-tree là cây)
            continue
        
        node_label = f"{{{current_node.item}|{current_node.count}}}"
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
                "Đầu chuỗi Node Link": f"-> {data['node'].item}:{data['node'].count}" if data['node'] else "Không có"
            })
        st_container.dataframe(ht_data_display)
    
    try:
        st_container.graphviz_chart(dot, use_container_width=True)
    except Exception as e:
        st_container.error(f"Lỗi khi vẽ FP-Tree: {e}. Có thể do Graphviz chưa được cài đặt đúng cách.")
        st_container.code(dot.source) # Hiển thị mã DOT để debug

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
    
    import pandas as pd
    rules_df = pd.DataFrame(formatted_rules)
    # Sắp xếp theo Lift và Confidence giảm dần
    rules_df_sorted = rules_df.sort_values(by=['Lift', 'Confidence'], ascending=[False, False])
    st_container.dataframe(rules_df_sorted)

