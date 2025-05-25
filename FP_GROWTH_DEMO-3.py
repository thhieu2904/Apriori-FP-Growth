# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from collections import defaultdict, Counter
import time
import copy
import graphviz
import os
import sys
import re
from itertools import combinations # Thêm itertools để tạo tổ hợp

# --- Cấu hình trang Streamlit ---
st.set_page_config(layout="wide", page_title="FP-Growth Visualizer")
st.title("FP-Growth Algorithm Visualizer")
st.markdown("### Trực quan hóa thuật toán FP-Growth từng bước")
st.markdown("Các bước được đánh dấu `[GM Line X]` (Giả Mã) tham chiếu đến các dòng trong mô tả thuật toán được cung cấp.")

# --- Cấu trúc Node và Lớp FP-Growth ---
class TreeNode:
    """Nút trong FP-Tree"""
    def __init__(self, item, count=1, parent=None):
        self.item = item; self.count = count; self.parent = parent
        self.children = {}; self.next = None # next: liên kết trong header table
    def increment(self, count=1): self.count += count
    def __repr__(self): return f"Node(item={self.item}, count={self.count}, id={id(self)})"

# --- Cấu hình Graphviz PATH (Tùy chọn) ---
# Nếu Graphviz không nằm trong PATH hệ thống, bạn có thể chỉ định đường dẫn ở đây
# Ví dụ:
# os.environ["PATH"] += os.pathsep + 'C:/Program Files/Graphviz/bin'
# try:
#     # Kiểm tra nhanh xem graphviz có chạy được không
#     graphviz.Digraph().render(engine='dot', format='png', cleanup=True, directory=os.path.dirname(__file__))
# except graphviz.backend.execute.ExecutableNotFound:
#     st.error("Lỗi: Không tìm thấy Graphviz 'dot'. Vui lòng cài đặt Graphviz và đảm bảo nó nằm trong PATH hệ thống, hoặc cấu hình đường dẫn trong code.")
# except Exception as e:
#      st.warning(f"Lỗi khi kiểm tra Graphviz: {e}")

class FPGrowth:
    """Lớp chính thực hiện thuật toán FP-Growth"""
    def __init__(self, min_support=2):
        if not isinstance(min_support, int) or min_support < 1:
            raise ValueError("Ngưỡng hỗ trợ tối thiểu (min_support) phải là số nguyên >= 1")
        self.min_support = min_support; self.frequent_items = None
        self.header_table = None; self.root = TreeNode(None, 0) # Luôn có root node
        self.transactions = None; self.transactions_input = None
        self.steps = []; self.patterns = [] # patterns sẽ lưu (pattern_tuple, support)

    # --- add_step (Giữ nguyên - dùng để ghi log các bước) ---
    def add_step(self, step_type, description, data=None, context=None):
        step_data_copy = {}
        if data:
            for key, value in data.items():
                # Chỉ copy tham chiếu cho các đối tượng cây để tránh deepcopy tốn kém
                if key in ["root", "generating_tree", "source_tree"] and isinstance(value, TreeNode):
                    step_data_copy[key] = value # Giữ tham chiếu
                # Copy header table một cách nông (shallow copy references to nodes)
                elif key in ["header_table", "generating_header", "active_header_table", "parent_header_table", "cond_header_table"] :
                    if isinstance(value, dict):
                        copied_header = {item: [freq, node_ref] for item, (freq, node_ref) in value.items()}
                        step_data_copy[key] = copied_header
                    else: # Có thể là None
                         step_data_copy[key] = value
                # Copy các thông tin highlight
                elif key in ["highlight_node_ids_to_path", "highlight_path_colors", "highlight_edge_id_colors"]:
                    step_data_copy[key] = value # Thường là dict nhỏ, deepcopy cũng được nhưng không cần thiết
                # Deepcopy các dữ liệu khác nếu có thể
                else:
                    try:
                        step_data_copy[key] = copy.deepcopy(value)
                    except Exception: # Nếu không deepcopy được, dùng bản gốc
                        step_data_copy[key] = value
        # Copy context một cách nông
        context_copy = copy.copy(context) if context else {}
        # Đảm bảo các tree/header trong context không bị deepcopy
        if "source_tree" in context_copy and isinstance(context_copy["source_tree"], TreeNode): pass
        if "generating_tree" in context_copy and isinstance(context_copy["generating_tree"], TreeNode): pass
        for header_key in ["generating_header", "active_header_table", "parent_header_table"]:
             if header_key in context_copy and isinstance(context_copy[header_key], dict):
                 context_copy[header_key] = {item: [freq, node_ref] for item, (freq, node_ref) in context_copy[header_key].items()}

        self.steps.append({
            "step_type": step_type,
            "description": description,
            "data": step_data_copy,
            "context": context_copy
        })

    # --- Các hàm helper mới cho kiểm tra Single Path ---
    def _is_single_path(self, node):
        """Kiểm tra xem cây/nhánh bắt đầu từ node có phải là single path không."""
        if not node: return True # Cây rỗng được coi là single path
        current = node
        while current and current.children:
            if len(current.children) > 1:
                return False # Nút có nhiều hơn 1 con -> không phải single path
            # Nếu có con, chỉ có 1 con, di chuyển xuống con đó
            current = list(current.children.values())[0]
        return True # Đã duyệt hết hoặc đến lá mà không gặp nút > 1 con

    def _extract_single_path_items(self, node):
        """Trích xuất danh sách (item, count) từ một single path, bắt đầu từ con của node đầu vào."""
        path_items_counts = []
        current = node
        # Bắt đầu từ con đầu tiên (nếu có) của node gốc được truyền vào
        if current and current.children:
            current = list(current.children.values())[0] # Lấy nút đầu tiên trên path (con của root/node)
            while current:
                path_items_counts.append((current.item, current.count))
                if not current.children: # Đã đến nút lá
                    break
                # Do là single path nên chỉ có tối đa 1 con
                current = list(current.children.values())[0]
        return path_items_counts # Trả về list các tuple (item, count)

    # --- load_data (Giữ nguyên) ---
    def load_data(self, parsed_transactions: list[list[str]]):
        """Nạp dữ liệu giao dịch đã được phân tích."""
        self.transactions_input = parsed_transactions
        # Kiểm tra nếu dữ liệu rỗng hoặc không hợp lệ ngay từ đầu
        if not self.transactions_input or not any(self.transactions_input):
             # Chỉ thêm bước nếu chưa có bước nào (tránh thêm nhiều lần khi reset)
             if not self.steps:
                 self.add_step("load_data_empty", "Dữ liệu giao dịch ban đầu rỗng hoặc không hợp lệ.", {"transactions": []})
             self.transactions_input = [] # Đảm bảo là list rỗng
             return self # Dừng sớm

        self.add_step("load_data", "Dữ liệu giao dịch ban đầu", {"transactions": self.transactions_input})
        return self

    # --- _scan1_find_frequent_items (Giữ nguyên) ---
    def _scan1_find_frequent_items(self):
        """Quét lần 1: Đếm tần suất và tìm các item phổ biến (>= min_support)."""
        # Kiểm tra nếu không có input
        if not self.transactions_input:
            self.frequent_items = {} # Khởi tạo rỗng
            self.add_step("frequency_empty", "Không có dữ liệu giao dịch để quét tần suất.", {"frequencies": {}, "frequent_items": {}, "min_support": self.min_support})
            return self # Dừng sớm

        item_counter = Counter(item for transaction in self.transactions_input for item in transaction)
        # Lọc các item đủ min_support
        self.frequent_items = {item: count for item, count in item_counter.items() if count >= self.min_support}
        # Sắp xếp FList: Giảm dần theo support, sau đó tăng dần theo tên item
        self.frequent_items = dict(sorted(self.frequent_items.items(), key=lambda x: (-x[1], x[0])))

        self.add_step("frequency",
                      f"Quét lần 1: Đếm tần suất các item (lọc với min_support={self.min_support})",
                      {"frequencies": dict(item_counter), "frequent_items": self.frequent_items, "min_support": self.min_support})

        if not self.frequent_items:
            st.warning(f"Không tìm thấy item nào đạt ngưỡng hỗ trợ tối thiểu ({self.min_support}). Thuật toán sẽ dừng.")
            # Thêm bước chỉ rõ không có item nào phổ biến
            self.add_step("no_frequent_items", "Không có item nào đủ ngưỡng hỗ trợ tối thiểu. Không thể xây dựng cây.", {"frequent_items": {}})

        return self

    # --- _scan2_build_tree (Cập nhật kiểm tra rỗng) ---
    def _scan2_build_tree(self):
        """Quét lần 2: Xây dựng FP-Tree."""
        # Kiểm tra nếu không có frequent items từ bước trước
        if not self.frequent_items:
             # Các bước thông báo rỗng đã được thêm ở các hàm trước nếu cần
             # Chỉ cần đảm bảo root tồn tại và thêm bước cây rỗng nếu chưa có
             if not any(s['step_type'] == 'build_fptree_empty' for s in self.steps):
                  self.root = TreeNode(None, 0) # Đảm bảo root tồn tại
                  self.add_step("build_fptree_empty", "Xây dựng FP-Tree: Không có frequent items -> Cây rỗng.", {"root": self.root, "header_table": {}})
             return self # Dừng sớm

        # Tạo Header Table ban đầu từ FList
        self.header_table = {item: [freq, None] for item, freq in self.frequent_items.items()}
        self.add_step("header_table_init", "Khởi tạo Header Table từ các item phổ biến (FList)", {"header_table": self.header_table})

        # Lọc và sắp xếp lại các giao dịch
        self.transactions = []
        display_transactions_dict = {} # Để hiển thị các giao dịch đã lọc
        f_list_order = list(self.frequent_items.keys()) # Thứ tự sắp xếp

        for i, transaction_input in enumerate(self.transactions_input):
            # Lọc bỏ các item không phổ biến
            filtered = [item for item in transaction_input if item in self.frequent_items]
            if filtered:
                 # Sắp xếp theo thứ tự FList (support giảm dần, tên tăng dần)
                 filtered.sort(key=lambda item: f_list_order.index(item))
                 self.transactions.append(filtered)
                 display_transactions_dict[f"T{i+1}"] = filtered # Lưu để hiển thị

        self.add_step("filter_transactions", "Quét lần 2: Lọc và sắp xếp lại giao dịch theo FList", {"transactions": display_transactions_dict})

        # Khởi tạo lại root node (quan trọng nếu hàm được gọi lại)
        self.root = TreeNode(None, 0)

        # Kiểm tra nếu không còn giao dịch nào sau khi lọc
        if not self.transactions:
             st.warning("Không có giao dịch nào chứa item phổ biến sau khi lọc.")
             # Thêm bước cây rỗng do không có giao dịch để chèn
             self.add_step("build_fptree_empty", "Xây dựng FP-Tree: Không có giao dịch sau khi lọc -> Cây rỗng.", {"root": self.root, "header_table": self.header_table})
             return self # Dừng sớm

        # Chèn từng giao dịch đã lọc và sắp xếp vào cây
        for transaction in self.transactions:
            self._insert_tree(transaction, self.root, self.header_table)

        # Kiểm tra lại xem cây có thực sự được xây dựng không (ví dụ: lỗi logic insert)
        if not any(self.root.children.values()):
            st.warning("FP-Tree rỗng sau khi cố gắng chèn các giao dịch (có thể do lỗi logic hoặc dữ liệu đặc biệt).")
            self.add_step("build_fptree_empty", "Xây dựng FP-Tree: Cây vẫn rỗng sau khi chèn các giao dịch.", {"root": self.root, "header_table": self.header_table})
        else:
            # Cây đã được xây dựng thành công
            self.add_step("build_fptree", "Xây dựng FP-Tree hoàn chỉnh từ các giao dịch đã lọc", {"root": self.root, "header_table": self.header_table})

        return self

    # --- _insert_tree (Sửa lỗi thụt lề tiềm ẩn, giữ logic) ---
    def _insert_tree(self, items, node, header_table):
        """Chèn một danh sách item (đã lọc, sắp xếp) vào cây FP-Tree."""
        if not items: return # Hết item để chèn

        item = items[0]
        # Thường item sẽ có trong header_table do đã lọc, nhưng kiểm tra lại cho chắc
        if item not in header_table:
             # print(f"Warning: Item '{item}' not in header table during insert.") # Debugging
             return # Bỏ qua item không có trong header (không nên xảy ra)

        # Kiểm tra xem item đã là con của node hiện tại chưa
        if item in node.children:
            child_node = node.children[item]
            child_node.increment() # Tăng count của node con đã tồn tại
        else:
            # Tạo node mới nếu chưa tồn tại
            new_node = TreeNode(item, 1, node) # Count khởi đầu là 1
            node.children[item] = new_node
            child_node = new_node # Node mới sẽ là node con
            # Cập nhật node-link trong header table
            freq_count, head_node = header_table[item]
            if head_node is None:
                # Đây là node đầu tiên của item này
                header_table[item][1] = new_node # Cập nhật head của link list
            else:
                # Duyệt đến cuối node-link và thêm node mới vào
                current = head_node
                while current.next:
                    current = current.next
                current.next = new_node # Nối node mới vào cuối

        # Gọi đệ quy để chèn các item còn lại, bắt đầu từ node con (child_node)
        self._insert_tree(items[1:], child_node, header_table)


    # --- mine_patterns (Cập nhật kiểm tra rỗng) ---
    def mine_patterns(self):
        """Bắt đầu quá trình khai thác các tập phổ biến từ FP-Tree."""
        # Kiểm tra điều kiện tiên quyết trước khi bắt đầu đệ quy
        if not self.root or not any(self.root.children.values()) or not self.header_table:
             st.warning("FP-Tree hoặc Header Table rỗng, không thể bắt đầu khai thác mẫu.")
             # Thêm bước thông báo không thể bắt đầu nếu chưa có
             if not any(s['step_type'] == 'start_mining_empty' for s in self.steps):
                 # Kiểm tra xem cây có rỗng không trước khi truy cập children
                 root_node = self.root if self.root else TreeNode(None, 0)
                 header = self.header_table if self.header_table else {}
                 self.add_step("start_mining_empty", "Không thể bắt đầu khai thác: FP-Tree hoặc Header Table rỗng.", {"root": root_node, "header_table": header})
             return self # Dừng

        self.patterns = [] # Khởi tạo lại danh sách mẫu tìm được
        # Bắt đầu quá trình đệ quy từ cây gốc và hậu tố rỗng
        self._mine_recursive(self.root, self.header_table, tuple()) # Hậu tố ban đầu là tuple rỗng

        # Xử lý kết quả cuối cùng: Loại bỏ trùng lặp (nếu có) và sắp xếp
        unique_patterns = {}
        # Giữ support cao nhất nếu có trùng lặp (thường không xảy ra nếu logic đúng)
        for pattern_tuple, support in self.patterns:
             # Sắp xếp pattern trước khi dùng làm key để đảm bảo tính duy nhất
             sorted_pattern = tuple(sorted(pattern_tuple))
             if sorted_pattern not in unique_patterns or support > unique_patterns[sorted_pattern]:
                 unique_patterns[sorted_pattern] = support

        # Chuyển lại thành list và sắp xếp theo support giảm dần, sau đó theo pattern tăng dần
        self.patterns = sorted(unique_patterns.items(), key=lambda x: (-x[1], tuple(x[0]))) # Sắp xếp cả theo pattern

        self.add_step("final_patterns", "Hoàn thành khai thác! Các tập phổ biến tìm được:", {"patterns": self.patterns})
        return self

    # --- _mine_recursive (Cập nhật đầy đủ theo giả mã) ---
    def _mine_recursive(self, current_tree_root, current_header_table, current_suffix_tuple):
        """
        Hàm đệ quy chính thực hiện khai thác FP-Growth.
        Tham số:
            current_tree_root: Node gốc của cây FP-Tree hiện tại (có thể là cây gốc hoặc cây điều kiện).
            current_header_table: Header Table tương ứng với cây hiện tại.
            current_suffix_tuple: Hậu tố (alpha α) hiện tại, là một tuple các item.
        """

        # --- Kiểm tra đầu vào của hàm đệ quy ---
        # (Phòng trường hợp cây/header rỗng được truyền vào do lỗi hoặc CPB rỗng)
        if not current_tree_root or not any(current_tree_root.children.values()) or not current_header_table:
             # Thêm bước log thông báo dừng nhánh đệ quy này
             suffix_str_debug = '{' + ', '.join(map(str, sorted(current_suffix_tuple))) + '}' if current_suffix_tuple else '{}'
             self.add_step("recursive_skip_empty",
                           f"[Dừng Nhánh Đệ Quy] Đầu vào không hợp lệ: Cây điều kiện hoặc Header Table rỗng (Hậu tố α={suffix_str_debug}).",
                           {"root": current_tree_root, "header_table": current_header_table}, # Truyền giá trị rỗng/None để biết tại sao dừng
                           context={"suffix": current_suffix_tuple})
             return # Dừng nhánh đệ quy này

        # --- [GM Line 1: Entry Point - Không có trong giả mã nhưng cần để theo dõi] ---
        current_suffix_str = '{' + ', '.join(map(str, sorted(current_suffix_tuple))) + '}' if current_suffix_tuple else '{}'
        # Xác định xem đây là cây gốc hay cây điều kiện
        is_root_call = (current_tree_root is self.root and not current_suffix_tuple)
        tree_desc = "FP-Tree Gốc" if is_root_call else f"Cây Điều Kiện cho α={current_suffix_str}"

        self.add_step("recursive_entry",
                     f"[Bắt đầu] Gọi FP-Growth với {tree_desc}",
                     {"root": current_tree_root, "header_table": current_header_table}, # Dữ liệu của bước này là cây và header hiện tại
                     context={"suffix": current_suffix_tuple, "active_header_table": current_header_table}) # Context lưu hậu tố và header đang hoạt động

        # --- [GM Line 2: IF FP-Tree chứa một đường đi P THEN] ---
        # Kiểm tra xem cây hiện tại có phải là Single Path không
        if self._is_single_path(current_tree_root):
            # Ghi log là đang xử lý trường hợp Single Path
            self.add_step("single_path_check",
                         f"[GM Line 2] Kiểm tra: {tree_desc} là một Single Path.",
                         {"root": current_tree_root, "header_table": current_header_table, "is_single_path": True},
                         context={"suffix": current_suffix_tuple, "active_header_table": current_header_table})

            # --- [GM Line 3: Tạo tất cả tổ hợp β của các mục trong P] ---
            # Trích xuất các item và count từ single path
            single_path_items_counts = self._extract_single_path_items(current_tree_root) # [(item, count), ...]
            single_path_items = [item for item, count in single_path_items_counts] # Chỉ lấy item
            path_items_display = [(item, count) for item, count in single_path_items_counts] # Dữ liệu để hiển thị

            # Log các item tìm thấy trên path
            self.add_step("single_path_items",
                         f"[GM Line 3a] Các Item và Count trên Single Path: {path_items_display}",
                         {"single_path_items": path_items_display},
                         context={"suffix": current_suffix_tuple})

            # Tạo dict để tra cứu count nhanh chóng
            item_to_count_map = dict(single_path_items_counts)

            # Tạo tất cả các tổ hợp con không rỗng (β) của các item trên path
            if single_path_items: # Chỉ tạo tổ hợp nếu có item trên path
                for i in range(1, len(single_path_items) + 1): # Tổ hợp từ 1 đến tất cả các item
                    for beta_tuple in combinations(single_path_items, i): # beta_tuple là một tổ hợp (item1, item2, ...)
                        beta_list = list(beta_tuple) # Chuyển sang list để dễ thao tác

                        # --- [GM Line 4: Ghi nhận mỗi tập β ∪ α như một tập phổ biến] ---
                        # Tạo mẫu đầy đủ bằng cách kết hợp tổ hợp β với hậu tố α hiện tại
                        full_pattern_list = beta_list + list(current_suffix_tuple)
                        full_pattern_tuple = tuple(sorted(full_pattern_list)) # Sắp xếp để đảm bảo tính duy nhất

                        # Tính support cho mẫu này: là giá trị count nhỏ nhất của các item trong β (từ path)
                        min_support_for_beta = float('inf')
                        if beta_tuple: # Đảm bảo beta không rỗng
                            min_support_for_beta = min(item_to_count_map[item] for item in beta_tuple)

                        # Thêm mẫu và support vào danh sách kết quả tổng
                        # Tránh thêm trùng lặp nếu mẫu đã tồn tại với support cao hơn (dù không nên xảy ra)
                        current_patterns_dict = dict(self.patterns)
                        if full_pattern_tuple not in current_patterns_dict or min_support_for_beta > current_patterns_dict[full_pattern_tuple]:
                           self.patterns.append((full_pattern_tuple, min_support_for_beta))

                        # Log việc tạo ra tổ hợp và mẫu phổ biến tương ứng
                        beta_str = '{' + ', '.join(map(str, sorted(beta_list))) + '}'
                        full_pattern_display = '{' + ', '.join(map(str, sorted(full_pattern_list))) + '}'
                        self.add_step("single_path_generate_combo",
                                     f"[GM Line 3b & 4] Tạo tổ hợp β={beta_str}. Ghi nhận mẫu: {full_pattern_display} (Support: {min_support_for_beta})",
                                     {"pattern": full_pattern_tuple, "support": min_support_for_beta, "beta_combo": beta_list, "source_single_path_items": path_items_display},
                                     context={"suffix": current_suffix_tuple})

            # Kết thúc xử lý nhánh Single Path này, không cần đi sâu hơn
            self.add_step("single_path_end", f"Kết thúc xử lý Single Path cho {tree_desc}.", {}, context={"suffix": current_suffix_tuple})
            return # Dừng đệ quy cho nhánh này

        else:
            # --- [GM Line 5: ELSE (Cây không phải Single Path)] ---
            # Log rằng cây không phải Single Path
            self.add_step("multi_path_check", # Sử dụng step_type khác để phân biệt
                         f"[GM Line 5] Kiểm tra: {tree_desc} có nhiều nhánh (Không phải Single Path).",
                         {"root": current_tree_root, "header_table": current_header_table, "is_single_path": False},
                         context={"suffix": current_suffix_tuple, "active_header_table": current_header_table})

            # --- [GM Line 6: FOR EACH mục ai trong Header Table (từ dưới lên) DO] ---
            # Lấy danh sách các item từ header table và đảo ngược để xử lý từ ít phổ biến đến nhiều
            items_to_process_list = list(current_header_table.keys())
            items_to_process_list.reverse() # Đảo ngược để duyệt từ dưới lên (ít support -> nhiều support)

            for item in items_to_process_list:
                # Lấy thông tin của item từ header table hiện tại
                if item not in current_header_table: continue # Bỏ qua nếu item không có (không nên xảy ra)
                freq_count, head_node = current_header_table[item]

                # Log bắt đầu xử lý item này
                self.add_step("process_item",
                             f"[GM Line 6] Xử lý item '{item}' (Support: {freq_count}) từ Header Table của {tree_desc}",
                             {"item": item, "support": freq_count, "root": current_tree_root, "header_table": current_header_table},
                             context={"suffix": current_suffix_tuple, "generating_tree": current_tree_root, "active_header_table": current_header_table})

                # --- [GM Line 7 & 8: Tạo mẫu β = {ai} ∪ α và Ghi nhận mẫu β] ---
                # Tạo mẫu mới bằng cách thêm item hiện tại vào hậu tố α
                new_pattern_list = [item] + list(current_suffix_tuple)
                new_pattern_tuple = tuple(sorted(new_pattern_list)) # Sắp xếp để duy nhất
                support = freq_count # Support của mẫu này là support của item 'aᵢ' trong cây hiện tại

                # Thêm mẫu này vào danh sách kết quả tổng
                current_patterns_dict = dict(self.patterns)
                if new_pattern_tuple not in current_patterns_dict or support > current_patterns_dict[new_pattern_tuple]:
                    self.patterns.append((new_pattern_tuple, support))

                # Log việc tìm thấy mẫu này
                pattern_display_str = '{' + ', '.join(map(str, new_pattern_tuple)) + '}'
                # Tránh log trùng nếu bước trước đó giống hệt (ít khi xảy ra)
                # if not self.steps or not (self.steps[-1].get("step_type") == "found_pattern" and self.steps[-1].get("data", {}).get("pattern") == new_pattern_tuple and self.steps[-1].get("data", {}).get("support") == support):
                self.add_step("found_pattern",
                                f"[GM Line 7-8] Ghi nhận mẫu β = {pattern_display_str} (Support: {support}) (từ item '{item}' + α={current_suffix_str})",
                                {"pattern": new_pattern_tuple, "support": support},
                                context={"suffix": current_suffix_tuple, "item": item, "generating_tree": current_tree_root, "active_header_table": current_header_table})

                # --- [GM Line 9: Xây dựng CPB(β) - Conditional Pattern Base] ---
                # Lấy các đường đi tiền tố (prefix paths) kết thúc bằng item hiện tại
                # prefix_paths_details = [(original_node, path_nodes_reversed, count), ...]
                prefix_paths_details = self._get_conditional_pattern_base(item, current_header_table)

                # --- [GM Line 10: IF CPB(β) ≠ Ø THEN] ---
                # Kiểm tra xem Conditional Pattern Base có rỗng không
                if not prefix_paths_details:
                    # Log rằng CPB rỗng
                    self.add_step("conditional_pattern_base_empty",
                                  f"[GM Line 9-10] CPB cho item '{item}' (với α={current_suffix_str}) rỗng. Không tạo cây điều kiện.",
                                  {"item": item},
                                  context={"suffix": current_suffix_tuple, "generating_tree": current_tree_root, "active_header_table": current_header_table, "generating_item": item})
                    continue # Chuyển sang item tiếp theo trong vòng lặp header table

                # --- CPB không rỗng ---
                # (Tính toán thông tin highlight cho CPB - phần này phức tạp, giữ nguyên logic)
                node_to_path_info_obj = defaultdict(list); path_colors_obj = {} ; edge_colors_obj={}
                available_colors = ["red", "blue", "green", "orange", "purple", "cyan", "magenta", "brown"] # Màu để highlight
                for i, (orig_node, path_rev, count) in enumerate(prefix_paths_details):
                    path_id = i # ID của đường đi
                    color = available_colors[i % len(available_colors)] # Chọn màu xoay vòng
                    path_colors_obj[path_id] = color # Lưu màu cho path_id
                    # Map node -> list các path_id đi qua nó
                    for node in path_rev: # Các node trên path (đảo ngược)
                        if path_id not in node_to_path_info_obj[node]: node_to_path_info_obj[node].append(path_id)
                    # Thêm cả node gốc của path (item đang xét)
                    if path_id not in node_to_path_info_obj[orig_node]: node_to_path_info_obj[orig_node].append(path_id)
                    # Map cạnh -> (path_id, color) để tô màu cạnh (ưu tiên path_id nhỏ hơn nếu trùng)
                    full_path_nodes = list(reversed(path_rev)) + [orig_node] # Path đầy đủ từ root -> orig_node
                    for j in range(len(full_path_nodes) - 1):
                        p_node, c_node = full_path_nodes[j], full_path_nodes[j+1] # Parent, Child
                        edge_key = (p_node, c_node) # Key là tuple (parent_node, child_node)
                        if edge_key not in edge_colors_obj or path_id < edge_colors_obj[edge_key][0]:
                            edge_colors_obj[edge_key] = (path_id, color) # Lưu path_id và màu cho cạnh

                # Chuyển ID object thành string để dùng trong Graphviz/ASCII
                hl_node_ids = {str(id(n)): pids for n, pids in node_to_path_info_obj.items()}
                hl_edge_ids = {(str(id(p)), str(id(c))): v for (p, c), v in edge_colors_obj.items()}
                hl_path_colors = path_colors_obj # Dict: path_id -> color name
                # Dữ liệu path để hiển thị text
                paths_disp = [([n.item for n in reversed(path_rev)], ct) for _, path_rev, ct in prefix_paths_details]

                # Log việc xây dựng CPB và thông tin highlight
                self.add_step("conditional_pattern_base",
                             f"[GM Line 9] Xây dựng CPB cho item '{item}' (với α={current_suffix_str}). Tìm thấy {len(paths_disp)} đường đi tiền tố.",
                             {"item": item, "paths_items_for_display": paths_disp, "generating_tree": current_tree_root,
                              "highlight_node_ids_to_path": hl_node_ids, # node_id_str -> [path_id]
                              "highlight_path_colors": hl_path_colors,     # path_id -> color_str
                              "highlight_edge_id_colors": hl_edge_ids},   # (parent_id_str, child_id_str) -> (path_id, color_str)
                             context={"suffix": current_suffix_tuple, "generating_item": item, "active_header_table": current_header_table})

                # --- [GM Line 11: Xây dựng FP-Tree_β từ CPB(β)] ---
                # Tạo danh sách các (path_nodes_reversed, count) để xây cây điều kiện
                prefix_paths_for_cond_tree = [(path_rev, ct) for _, path_rev, ct in prefix_paths_details]
                # Xây dựng cây điều kiện và header table điều kiện
                cond_tree_root, cond_header_table = self._build_conditional_fptree(prefix_paths_for_cond_tree)

                # --- [GM Line 12: IF FP-Tree_β ≠ Ø THEN] ---
                # Kiểm tra xem cây điều kiện và header table điều kiện có được tạo thành công không
                if cond_tree_root and cond_header_table: # Cả hai phải tồn tại và header không rỗng
                    # Log việc xây dựng thành công cây điều kiện
                    self.add_step("conditional_fptree",
                                 f"[GM Line 11] Xây dựng thành công Cây FP-Tree Điều Kiện (FP-Tree_β) cho item '{item}' (từ CPB).",
                                 {"item": item, "root": cond_tree_root, "header_table": cond_header_table}, # Dữ liệu là cây và header mới
                                 context={"suffix": current_suffix_tuple, "generating_item": item, # Context lưu item gốc
                                          "source_tree": current_tree_root, "parent_header_table": current_header_table}) # Context lưu cây/header cha

                    # --- [GM Line 13: Gọi đệ quy FP-Growth(FP-Tree_β, β)] ---
                    # Hậu tố mới cho lần gọi đệ quy chính là mẫu β vừa tạo (item + α cũ)
                    new_suffix_rec = new_pattern_tuple
                    new_suffix_rec_str = '{' + ', '.join(map(str, sorted(new_suffix_rec))) + '}'
                    # Log chuẩn bị gọi đệ quy
                    self.add_step("recursive_call",
                                 f"[GM Line 13] Gọi đệ quy FP-Growth với Cây Điều Kiện và hậu tố mới α = β = {new_suffix_rec_str}",
                                 {"root": cond_tree_root, "header_table": cond_header_table}, # Truyền cây/header mới vào data để bước tiếp theo có thể tham chiếu
                                 context={"suffix": new_suffix_rec}) # Context quan trọng là hậu tố MỚI

                    # Thực hiện gọi đệ quy
                    self._mine_recursive(cond_tree_root, cond_header_table, new_suffix_rec)

                    # Log quay lại từ cuộc gọi đệ quy (tùy chọn, có thể làm rối)
                    # self.add_step("recursive_return", f"Quay lại từ cuộc gọi đệ quy cho β={new_suffix_rec_str}", {}, context={"suffix": current_suffix_tuple})


                else:
                     # --- [GM Line 12: ELSE (Cây điều kiện rỗng)] ---
                     # Log rằng cây điều kiện rỗng sau khi xây dựng
                     self.add_step("conditional_fptree_empty",
                                   f"[GM Line 11-12] Cây FP-Tree Điều Kiện (FP-Tree_β) cho item '{item}' (với α={current_suffix_str}) rỗng sau khi xây dựng từ CPB. Không gọi đệ quy.",
                                   {"item": item},
                                   context={"suffix": current_suffix_tuple, "generating_item": item, "generating_tree": current_tree_root, "active_header_table": current_header_table})
            # Kết thúc vòng lặp FOR EACH item trong header table

        # Log kết thúc xử lý cho nhánh đệ quy hiện tại (tùy chọn)
        # self.add_step("recursive_exit", f"Kết thúc xử lý đệ quy cho hậu tố α={current_suffix_str}", {}, context={"suffix": current_suffix_tuple})

    # --- _get_conditional_pattern_base (Giữ nguyên logic) ---
    def _get_conditional_pattern_base(self, item, header_table):
        """Lấy các đường đi tiền tố (Conditional Pattern Base) cho một item."""
        # Kết quả: list của (node_gốc_của_item, list_các_node_tiền_tố_đảo_ngược, count_của_node_gốc)
        paths_with_details = []
        # Bắt đầu từ head của node-link cho item trong header table
        node = header_table.get(item, [None, None])[1] # Lấy head_node (phần tử thứ 2)
        while node:
            original_item_node = node # Lưu lại node của item đang xét trên path này
            path_nodes_reversed = [] # Lưu các node trên đường đi từ node này lên root (trừ root)
            count = node.count # Count của path này chính là count của node item
            parent = node.parent
            # Đi ngược lên cha cho đến khi gặp root (parent.item is None)
            while parent and parent.item is not None:
                path_nodes_reversed.append(parent) # Thêm node cha vào list
                parent = parent.parent # Đi tiếp lên cha của cha

            # Chỉ thêm path nếu nó có tiền tố (không phải là con trực tiếp của root)
            if path_nodes_reversed:
                paths_with_details.append((original_item_node, path_nodes_reversed, count))

            # Đi đến node tiếp theo trong node-link của item
            node = node.next
        return paths_with_details # List of (node, [parent, grandparent,...], count)

    # --- _build_conditional_fptree (Giữ nguyên logic) ---
    def _build_conditional_fptree(self, prefix_paths_with_nodes):
        """Xây dựng cây FP-Tree điều kiện từ Conditional Pattern Base."""
        # prefix_paths_with_nodes: list của ([parent, grandparent,...], count)

        # 1. Đếm support cho từng item trong các paths điều kiện
        cond_counts = defaultdict(int)
        for path_nodes_reversed, count in prefix_paths_with_nodes:
            for node in path_nodes_reversed: # Duyệt qua các node trên mỗi path
                cond_counts[node.item] += count # Cộng dồn count của path vào item

        # 2. Lọc các item đủ min_support trong ngữ cảnh điều kiện
        cond_frequent_items = {item: count for item, count in cond_counts.items() if count >= self.min_support}

        # Nếu không có item nào đủ support -> cây điều kiện rỗng
        if not cond_frequent_items:
            return None, None # Trả về None cho cả cây và header

        # 3. Sắp xếp các item phổ biến điều kiện (FList điều kiện)
        cond_frequent_items_sorted = dict(sorted(cond_frequent_items.items(), key=lambda x: (-x[1], x[0])))
        cond_f_list_order = list(cond_frequent_items_sorted.keys()) # Thứ tự để sắp xếp path

        # 4. Tạo header table điều kiện
        cond_header_table = {item: [freq, None] for item, freq in cond_frequent_items_sorted.items()}

        # 5. Tạo root cho cây điều kiện
        cond_root = TreeNode(None, 0)

        # 6. Chèn các path đã lọc và sắp xếp vào cây điều kiện
        for path_nodes_reversed, count in prefix_paths_with_nodes:
            # Lọc các item trong path này không thuộc FList điều kiện
            # Và lấy ra danh sách item (đảo ngược lại thứ tự gốc: gần root -> xa root)
            filtered_path_items = [node.item for node in reversed(path_nodes_reversed) if node.item in cond_frequent_items_sorted]

            if filtered_path_items:
                # Sắp xếp lại path theo thứ tự FList điều kiện
                filtered_path_items.sort(key=lambda item: cond_f_list_order.index(item))
                # Chèn path đã xử lý vào cây điều kiện, với count của path gốc
                self._insert_tree_conditional(filtered_path_items, cond_root, count, cond_header_table)

        # Kiểm tra lại nếu cây rỗng sau khi chèn (có thể xảy ra nếu logic insert lỗi)
        if not cond_root.children:
            return None, None

        return cond_root, cond_header_table

    # --- _insert_tree_conditional (Sửa lỗi thụt lề tiềm ẩn, giữ logic) ---
    def _insert_tree_conditional(self, items, node, count_multiplier, header_table):
         """Chèn một path vào cây FP-Tree điều kiện."""
         if not items: return # Hết item trong path

         item = items[0]
         # Kiểm tra item có trong header điều kiện không (đã được lọc trước đó nhưng chắc chắn)
         if item not in header_table:
             return

         # Kiểm tra xem item đã là con của node hiện tại chưa
         if item in node.children:
             child_node = node.children[item]
             # Tăng count bằng count của path gốc (count_multiplier)
             child_node.increment(count_multiplier)
         else:
             # Tạo node mới với count ban đầu là count_multiplier
             new_node = TreeNode(item, count_multiplier, node)
             node.children[item] = new_node
             child_node = new_node
             # Cập nhật node-link trong header table điều kiện
             freq_count, head_node = header_table[item]
             if head_node is None:
                 header_table[item][1] = new_node # Node đầu tiên
             else:
                 # Thêm vào cuối node-link
                 current = head_node
                 while current.next:
                     current = current.next
                 current.next = new_node # Nối vào cuối

         # Gọi đệ quy với các item còn lại và count_multiplier giữ nguyên
         self._insert_tree_conditional(items[1:], child_node, count_multiplier, header_table)


# --- Visualization Functions (Graphviz, ASCII, Utility - Giữ nguyên logic, sửa lỗi nhỏ nếu có) ---

# --- Graphviz Visualization ---
def add_graphviz_nodes_edges(graph, node, node_to_path_id_info=None, path_colors=None, edge_id_colors=None):
    """Hàm đệ quy thêm node và cạnh vào đối tượng Digraph của Graphviz."""
    if not node: return
    node_id = str(id(node))
    label = "Root" if node.item is None else f"{node.item}:{node.count}"
    node_attributes = {'label': label, 'shape': 'ellipse'}

    # Tô màu node nếu nó thuộc một hoặc nhiều path highlight (CPB)
    if node_to_path_id_info and node_id in node_to_path_id_info:
        path_ids_for_node = node_to_path_id_info.get(node_id, [])
        if path_ids_for_node:
            node_attributes['style'] = 'filled'
            # Tô màu theo path_id nhỏ nhất đi qua node đó
            first_path_id = sorted(path_ids_for_node)[0]
            node_attributes['fillcolor'] = path_colors.get(first_path_id, 'lightgrey') # Mặc định lightgrey

    graph.node(node_id, **node_attributes)

    # Thêm cạnh và gọi đệ quy cho các con (sắp xếp theo tên item cho ổn định)
    children_items = sorted(node.children.keys())
    for item_name in children_items:
        child_node = node.children[item_name]
        child_node_id = str(id(child_node))
        edge_attributes = {}
        edge_key = (node_id, child_node_id) # Key cho cạnh (parent_id, child_id)

        # Tô màu cạnh nếu nó thuộc một path highlight (CPB)
        if edge_id_colors and edge_key in edge_id_colors:
            path_id, color = edge_id_colors[edge_key]
            edge_attributes['color'] = color
            edge_attributes['penwidth'] = '2.0' # Làm đậm cạnh highlight

        graph.edge(node_id, child_node_id, **edge_attributes)
        # Gọi đệ quy cho nút con
        add_graphviz_nodes_edges(graph, child_node, node_to_path_id_info, path_colors, edge_id_colors)

def draw_fptree_graphviz(root, node_to_path_id_info=None, path_colors=None, edge_id_colors=None):
    """Tạo đối tượng Digraph của Graphviz cho FP-Tree."""
    if not root: return None
    dot = graphviz.Digraph(comment='FP-Tree', engine='dot') # Sử dụng engine 'dot'
    dot.attr(rankdir='TB') # Hướng từ trên xuống dưới
    # Gọi hàm đệ quy để thêm node và cạnh
    add_graphviz_nodes_edges(dot, root,
                            node_to_path_id_info=node_to_path_id_info or {},
                            path_colors=path_colors or {},
                            edge_id_colors=edge_id_colors or {})
    return dot

# --- ASCII Visualization ---
# Sửa lỗi SyntaxError và cải thiện logic prefix/connector
def _draw_ascii_recursive(node, prefix="", is_last=True, node_to_path_id_info=None, path_colors=None):
    """Hàm đệ quy vẽ cây ASCII."""
    if not node: return

    node_id = str(id(node))
    label = "Root" if node.item is None else f"{node.item}:{node.count}"

    # Xác định connector cho node hiện tại
    connector = "└── " if is_last else "├── "
    if node.parent is None:  # Root node không có connector
        connector = ""

    # Áp dụng màu nếu node được highlight
    display_label = label
    streamlit_color_map = {"red": "red", "blue": "blue", "green": "green", "orange": "orange",
                           "purple": "violet", "cyan": "cyan", "magenta": "magenta", "brown": "gray", "lightgrey": "gray"}
    if node_to_path_id_info and node_id in node_to_path_id_info:
        path_ids_for_node = node_to_path_id_info.get(node_id, [])
        if path_ids_for_node:
             first_path_id = sorted(path_ids_for_node)[0]
             color = path_colors.get(first_path_id, "lightgrey")
             display_color = streamlit_color_map.get(color, "gray")
             display_label = f":{display_color}[{label}]" # Dùng markdown màu của streamlit

    # In dòng cho node hiện tại
    st.markdown(f"`{prefix}{connector}{display_label}`", unsafe_allow_html=True)

    # Chuẩn bị prefix cho các node con
    child_prefix = prefix + ("    " if is_last else "│   ")

    # Lấy danh sách con và sắp xếp
    children_items = sorted(node.children.keys())
    num_children = len(children_items)

    # Gọi đệ quy cho từng con
    for i, item_name in enumerate(children_items):
        child_node = node.children[item_name]
        child_is_last = (i == num_children - 1) # Kiểm tra xem con có phải là cuối cùng không
        _draw_ascii_recursive(child_node, child_prefix, child_is_last, node_to_path_id_info, path_colors)


def draw_fptree_ascii(root, node_to_path_id_info=None, path_colors=None):
    """Vẽ FP-Tree bằng ký tự ASCII."""
    if not root:
        st.write("Không có cây để hiển thị ASCII.")
        return
    st.markdown("**Cấu trúc cây (ASCII):**")
    # Bắt đầu vẽ từ root, không có prefix ban đầu, root coi như là 'last' node ở level 0
    _draw_ascii_recursive(root, prefix="", is_last=True,
                         node_to_path_id_info=node_to_path_id_info or {},
                         path_colors=path_colors or {})


# --- Utility Functions ---
def show_header_table_df(header_table):
    """Tạo DataFrame để hiển thị Header Table."""
    if not header_table:
        return pd.DataFrame(columns=['Item', 'Frequency', 'Head of Node Link'])

    items, frequencies, head_node_links = [], [], []
    # Sắp xếp header table theo thứ tự FList (mặc định đã sort khi tạo)
    f_list_items = list(header_table.keys())

    for item in f_list_items:
        details = header_table[item]
        items.append(item)
        frequencies.append(details[0]) # Frequency
        head_node = details[1] # Head node của link list
        # Hiển thị thông tin node đầu tiên trong link list (nếu có)
        head_node_links.append("None" if head_node is None else f"-> Node({head_node.item}:{head_node.count})")

    df = pd.DataFrame({
        'Item': items,
        'Frequency': frequencies,
        'Head of Node Link': head_node_links
    })
    # Đặt Item làm index cho dễ nhìn
    return df.set_index('Item')

def format_patterns_df(patterns):
    """Tạo DataFrame để hiển thị các tập phổ biến tìm được."""
    if not patterns:
        return pd.DataFrame(columns=['Pattern', 'Support'])

    # patterns là list của (tuple_pattern, support)
    # Chuyển tuple_pattern thành string dạng {item1, item2,...}
    pattern_strs = ['{' + ', '.join(map(str, sorted(list(p)))) + '}' for p, s in patterns]
    supports = [s for p, s in patterns]

    df = pd.DataFrame({'Pattern': pattern_strs, 'Support': supports})
    # Sắp xếp lại lần cuối theo Support giảm dần, Pattern tăng dần
    df = df.sort_values(by=['Support', 'Pattern'], ascending=[False, True])
    return df.reset_index(drop=True) # Reset index để bắt đầu từ 0

# --- Hàm Phân tích Dataset mới (Định dạng Tx: [item1, item2,...]) ---
def parse_new_format(data_string: str) -> tuple[list[list[str]], list[str]]:
    """Phân tích chuỗi dữ liệu giao dịch theo định dạng 'Tx: [item1, item2,...]'."""
    transactions, errors = [], []
    lines = data_string.strip().split('\n')
    processed_tids = set() # Để kiểm tra TID trùng lặp

    for i, line in enumerate(lines):
        line_num = i + 1
        line = line.strip()
        if not line or line.startswith('#'): continue # Bỏ qua dòng trống hoặc comment

        # Tìm TID và phần items
        match_tid = re.match(r'^\s*([^:]+?)\s*:\s*', line)
        if not match_tid:
            errors.append(f"Dòng {line_num}: Thiếu định dạng 'TID:' ở đầu dòng.")
            continue
        tid = match_tid.group(1).strip()
        if not tid:
            errors.append(f"Dòng {line_num}: TID không được rỗng.")
            continue
        if tid in processed_tids:
             errors.append(f"Dòng {line_num}: TID '{tid}' bị trùng lặp.")
             # Vẫn xử lý nhưng cảnh báo
        processed_tids.add(tid)

        # Tìm phần danh sách item [...]
        match_items = re.search(r':\s*\[(.*?)\]', line)
        if not match_items:
            errors.append(f"Dòng {line_num} (TID: {tid}): Không tìm thấy danh sách item dạng '[item1, item2,...]'.")
            continue

        items_str = match_items.group(1)
        # Tách các item, loại bỏ khoảng trắng thừa và item rỗng
        items = [item.strip() for item in items_str.split(',') if item.strip()]

        if items:
            # Kiểm tra item hợp lệ (ví dụ không chứa ký tự đặc biệt nếu cần) - bỏ qua bước này
            transactions.append(items)
        else:
            # Vẫn thêm giao dịch rỗng nếu format đúng nhưng không có item bên trong []
            transactions.append([])
            # errors.append(f"Dòng {line_num} (TID: {tid}): Danh sách item rỗng sau dấu hai chấm.") # Có thể không coi là lỗi

    return transactions, errors

# --- Streamlit UI ---
# Dữ liệu mẫu
default_transactions_str = """T1: [A, B, C] 
T2: [B, C, D] 
T3: [A, C, D, E] 
T4: [A, D, E] 
T5: [A, B, C, E]"""
# Dữ liệu mẫu Single Path
default_single_path_str = """T1: [A, B, C]
T2: [A, B]
T3: [A, B, C, D]"""

# --- Sidebar Cài đặt ---
with st.sidebar:
    st.header("⚙️ Cài đặt")
    st.subheader("Dữ liệu giao dịch")
    data_option = st.radio("Chọn dữ liệu:", ("Mẫu Nhiều Nhánh", "Mẫu Single Path", "Nhập thủ công"), index=0, key="data_choice")

    transactions_input_str = ""
    if data_option == "Mẫu Nhiều Nhánh":
        transactions_input_str = default_transactions_str
        st.text_area("Dữ liệu mẫu (Nhiều Nhánh):", transactions_input_str, height=150, disabled=True)
    elif data_option == "Mẫu Single Path":
        transactions_input_str = default_single_path_str
        st.text_area("Dữ liệu mẫu (Single Path):", transactions_input_str, height=100, disabled=True)
    else: # Nhập thủ công
        transactions_input_str = st.text_area("Nhập dữ liệu (định dạng 'Tx: [item1, item2,...]', một giao dịch mỗi dòng)",
                                            default_transactions_str if 'last_transactions_str' not in st.session_state else st.session_state.last_transactions_str,
                                            height=150, key="manual_data")

    # Ngưỡng hỗ trợ
    min_support_input = st.slider("Ngưỡng hỗ trợ tối thiểu (min_support)",
                                  min_value=1, max_value=10,
                                  value=3 if 'last_min_support' not in st.session_state else st.session_state.last_min_support,
                                  step=1, key="min_sup_slider")

    # Tùy chọn hiển thị
    st.subheader("Trực quan hóa")
    prefer_ascii = st.checkbox("Ưu tiên vẽ cây bằng ASCII (nhanh hơn)", value=False, key="prefer_ascii")
    # Điều khiển auto-run delay
    # auto_run_delay = st.slider("Delay Tự động (giây)", 0.1, 5.0, 1.5, 0.1, key="auto_delay")

    # Nút Chạy / Đặt lại
    st.markdown("---")
    col_run, col_reset = st.columns(2)
    run_button = col_run.button("🚀 Chạy Thuật Toán", use_container_width=True, key="run")
    reset_button = col_reset.button("🔄 Đặt lại", use_container_width=True, key="reset")

# --- Khởi tạo/Reset State ---
if 'fp_growth_model' not in st.session_state: st.session_state.fp_growth_model = None
if 'current_step_index' not in st.session_state: st.session_state.current_step_index = 0
if 'is_autorun' not in st.session_state: st.session_state.is_autorun = False
if 'last_transactions_str' not in st.session_state: st.session_state.last_transactions_str = transactions_input_str
if 'last_min_support' not in st.session_state: st.session_state.last_min_support = min_support_input
if 'cpb_highlight_info' not in st.session_state: st.session_state.cpb_highlight_info = None # Lưu thông tin highlight CPB

if reset_button:
    # Xóa tất cả trạng thái liên quan đến lần chạy trước
    for key in list(st.session_state.keys()):
        if key.startswith('fp_growth') or key in ['current_step_index', 'is_autorun', 'last_transactions_str', 'last_min_support', 'cpb_highlight_info']:
            del st.session_state[key]
    st.rerun() # Chạy lại app để áp dụng trạng thái reset

# --- Logic Chạy Thuật Toán ---
model_needs_rerun = False
# Kiểm tra xem có cần chạy lại thuật toán không (dữ liệu hoặc min_support thay đổi)
if run_button:
    if (st.session_state.fp_growth_model is None or
        st.session_state.last_transactions_str != transactions_input_str or
        st.session_state.last_min_support != min_support_input):
        model_needs_rerun = True
    else:
        # Nếu không cần chạy lại model, chỉ reset về bước đầu tiên và tắt autorun
        st.session_state.current_step_index = 0
        st.session_state.is_autorun = False
        st.session_state.cpb_highlight_info = None # Xóa highlight cũ
        st.rerun() # Chạy lại để cập nhật UI về bước đầu

if model_needs_rerun:
    st.session_state.fp_growth_model = None # Xóa model cũ
    st.session_state.current_step_index = 0
    st.session_state.is_autorun = False
    st.session_state.cpb_highlight_info = None

    # Phân tích dữ liệu đầu vào
    parsed_transactions, parse_errors = parse_new_format(transactions_input_str)

    # Hiển thị lỗi phân tích nếu có
    if parse_errors:
        st.sidebar.warning("⚠️ Lỗi phân tích dữ liệu đầu vào:")
        for e in parse_errors:
            st.sidebar.caption(f"- {e}") # Hiển thị từng lỗi

    # Kiểm tra xem có giao dịch hợp lệ nào không
    if not parsed_transactions and not parse_errors: # Trường hợp input rỗng hợp lệ
         st.sidebar.info("Dữ liệu đầu vào không có giao dịch nào.")
         # Vẫn lưu trạng thái để không chạy lại liên tục
         st.session_state.last_transactions_str = transactions_input_str
         st.session_state.last_min_support = min_support_input
         # Tạo model rỗng để tránh lỗi
         model = FPGrowth(min_support=min_support_input)
         model.load_data([]) # Nạp dữ liệu rỗng để có bước load_data_empty
         st.session_state.fp_growth_model = model
         st.rerun()

    elif not parsed_transactions and parse_errors: # Trường hợp lỗi và không có giao dịch
        st.sidebar.error("Không phân tích được giao dịch hợp lệ nào do lỗi.")
        st.session_state.last_transactions_str = transactions_input_str # Vẫn lưu để tránh chạy lại
        st.session_state.last_min_support = min_support_input
        st.rerun() # Chạy lại để chỉ hiển thị lỗi

    else: # Có giao dịch hợp lệ (có thể có lỗi nhưng vẫn chạy với phần hợp lệ)
        with st.spinner("⏳ Đang chạy thuật toán FP-Growth..."):
            try:
                model = FPGrowth(min_support=min_support_input)
                # Các bước chính của thuật toán
                model.load_data(parsed_transactions)
                if model.transactions_input: # Chỉ chạy tiếp nếu load data thành công
                    model._scan1_find_frequent_items()
                    if model.frequent_items: # Chỉ chạy tiếp nếu có item phổ biến
                         model._scan2_build_tree()
                         # mine_patterns sẽ tự kiểm tra cây/header trước khi chạy
                         model.mine_patterns()
                    # else: các bước thông báo lỗi/dừng đã được thêm bên trong hàm
                st.session_state.fp_growth_model = model # Lưu model vào state
                st.session_state.last_transactions_str = transactions_input_str # Lưu input đã dùng
                st.session_state.last_min_support = min_support_input # Lưu min_sup đã dùng
            except ValueError as ve:
                 st.error(f"Lỗi cấu hình: {ve}")
                 st.session_state.fp_growth_model = None # Đảm bảo không có model lỗi
            except Exception as e:
                 st.error(f"Lỗi không mong muốn xảy ra: {e}")
                 st.exception(e) # In traceback vào log/console
                 st.session_state.fp_growth_model = None
        st.rerun() # Chạy lại để hiển thị kết quả bước đầu tiên

# --- Khu vực Hiển thị Chính ---
if st.session_state.fp_growth_model and st.session_state.fp_growth_model.steps:
    model = st.session_state.fp_growth_model
    total_steps = len(model.steps)
    step_index = st.session_state.current_step_index

    # Đảm bảo step_index không vượt quá giới hạn
    if step_index >= total_steps:
        step_index = total_steps - 1
        st.session_state.current_step_index = step_index
    if step_index < 0: # Trường hợp hy hữu
         step_index = 0
         st.session_state.current_step_index = step_index

    # Lấy thông tin của bước hiện tại
    current_step_info = model.steps[step_index]
    step_type = current_step_info["step_type"]
    description = current_step_info["description"]
    data = current_step_info["data"]         # Dữ liệu chính của bước (cây, header, pattern...)
    context = current_step_info["context"]   # Thông tin ngữ cảnh (hậu tố, item đang xét...)

    # --- Thanh điều khiển Bước ---
    st.markdown("---")
    nav_cols = st.columns([1, 1, 1, 1, 6]) # Thêm cột cho nút về đầu/cuối

    def go_to_step(new_index):
        target_index = max(0, min(new_index, total_steps - 1))
        if target_index != st.session_state.current_step_index:
             st.session_state.current_step_index = target_index
             st.session_state.is_autorun = False # Tắt autorun khi chuyển bước thủ công
             # Xóa highlight CPB khi chuyển bước, trừ khi bước mới là conditional_pattern_base
             next_step_type = model.steps[target_index]["step_type"] if target_index < total_steps else None
             if next_step_type != "conditional_pattern_base":
                 st.session_state.cpb_highlight_info = None
             st.rerun() # Chạy lại để cập nhật UI

    # Nút về Đầu
    if nav_cols[0].button("⏮️ Đầu", key="first_nav", disabled=(step_index <= 0), use_container_width=True): go_to_step(0)
    # Nút Lùi
    if nav_cols[1].button("⬅️ Trước", key="prev_nav", disabled=(step_index <= 0), use_container_width=True): go_to_step(step_index - 1)
    # Nút Tiến
    if nav_cols[2].button("Tiếp ➡️", key="next_nav", disabled=(step_index >= total_steps - 1), use_container_width=True): go_to_step(step_index + 1)
    # Nút về Cuối
    if nav_cols[3].button("⏭️ Cuối", key="last_nav", disabled=(step_index >= total_steps - 1), use_container_width=True): go_to_step(total_steps - 1)

    # Nút Tự động chạy / Tạm dừng (Loại bỏ)
    # auto_button_label = "⏸️ Tạm dừng" if st.session_state.is_autorun else "▶️ Tự động"
    # if nav_cols[2].button(auto_button_label, key="auto_nav"):
    #     st.session_state.is_autorun = not st.session_state.is_autorun
    #     # Nếu bắt đầu autorun từ bước cuối, quay về đầu
    #     if st.session_state.is_autorun and step_index == total_steps - 1:
    #         st.session_state.current_step_index = 0
    #         st.session_state.cpb_highlight_info = None
    #     st.rerun()

    # Thanh trượt chọn bước
    with nav_cols[4]:
         new_step_index = st.slider("Chọn bước:", 0, total_steps - 1, step_index, key="slider_nav", help="Kéo để chọn bước.")
         if new_step_index != step_index:
             go_to_step(new_step_index)
         # Hiển thị thông tin bước
         st.caption(f"Bước: **{step_index + 1}/{total_steps}** | Loại: `{step_type}`")


    # --- Layout Hiển thị Chính (2 cột) ---
    col_widths = [2, 3] if not prefer_ascii else [2, 2] # Điều chỉnh tỉ lệ nếu là ASCII
    display_cols = st.columns(col_widths)

    # === Cột 1: Thông tin Bước ===
    with display_cols[0]:
        st.markdown(f"**{description}**") # Mô tả của bước hiện tại
        st.markdown("---")

        # --- Hiển thị Header Table (Nếu có và phù hợp) ---
        header_to_display, header_caption, show_header = None, "", False

        # Logic xác định Header Table cần hiển thị và Caption tương ứng
        active_header = context.get("active_header_table") # Header của cây đang được xử lý
        parent_header = context.get("parent_header_table") # Header của cây cha (khi tạo cây ĐK)
        data_header = data.get("header_table") # Header được tạo/hiển thị trong bước này
        generating_header = context.get("generating_header") # Header dùng để tạo cây (ít dùng)

        # Ưu tiên header trong 'data' nếu bước này tạo/hiển thị nó trực tiếp
        if step_type in ["header_table_init", "build_fptree", "conditional_fptree", "build_fptree_empty"] and data_header is not None:
            header_to_display, show_header = data_header, True
            if step_type == "header_table_init": header_caption = "Header Table Ban đầu (FList):"
            elif step_type == "build_fptree": header_caption = "Header Table (Cây Gốc):"
            elif step_type == "conditional_fptree": item_ctx = context.get("generating_item", "?"); header_caption = f"Header Table (Cây Điều Kiện cho '{item_ctx}'):"
            elif step_type == "build_fptree_empty": header_caption = "Header Table (Khi Cây Rỗng):" # Có thể rỗng hoặc không

        # Nếu không, ưu tiên 'active_header' từ context cho các bước mining
        elif active_header is not None and step_type not in ["load_data", "frequency", "filter_transactions"]:
             header_to_display, show_header = active_header, True
             # Xác định ngữ cảnh của header này
             suffix_ctx = context.get("suffix", [])
             suffix_str = '{' + ', '.join(map(str, sorted(suffix_ctx))) + '}' if suffix_ctx else '{}'
             is_root_context = (active_header is model.header_table and not suffix_ctx)
             tree_type_desc = "Cây Gốc" if is_root_context else f"Cây ĐK (α={suffix_str})"

             if step_type == "recursive_entry": header_caption = f"Header Table ({tree_type_desc} - Bắt đầu):"
             elif step_type == "process_item": item_ctx = data.get("item", "?"); header_caption = f"Header Table ({tree_type_desc} - Xử lý '{item_ctx}'):"
             elif step_type in ["single_path_check", "multi_path_check"]: header_caption = f"Header Table ({tree_type_desc} - Kiểm tra Path):"
             elif step_type == "found_pattern": item_ctx = context.get("item", "?"); header_caption = f"Header Table ({tree_type_desc} - Khi tìm mẫu cho '{item_ctx}'):"
             elif step_type == "conditional_pattern_base": item_ctx = context.get("generating_item", "?"); header_caption = f"Header Table ({tree_type_desc} - Khi tạo CPB cho '{item_ctx}'):"
             elif step_type == "conditional_pattern_base_empty": item_ctx = context.get("generating_item", "?"); header_caption = f"Header Table ({tree_type_desc} - Khi CPB rỗng cho '{item_ctx}'):"
             elif step_type == "conditional_fptree_empty": item_ctx = context.get("generating_item", "?"); header_caption = f"Header Table ({tree_type_desc} - Cây cha của cây ĐK rỗng cho '{item_ctx}'):"
             elif step_type == "recursive_call": header_caption = f"Header Table ({tree_type_desc} - Chuẩn bị gọi đệ quy):"
             elif step_type in ["single_path_items", "single_path_generate_combo", "single_path_end"]: header_caption = f"Header Table ({tree_type_desc} - Của cây Single Path):"
             elif step_type == "recursive_skip_empty": header_caption = f"Header Table ({tree_type_desc} - Khi nhánh bị bỏ qua):"
             else: header_caption = f"Header Table ({tree_type_desc} - Ngữ cảnh):" # Mặc định

        # Fallback cho bước filter_transactions (hiển thị header gốc)
        elif step_type == "filter_transactions" and model and model.header_table:
             header_to_display, show_header = model.header_table, True
             header_caption = "Header Table (FList dùng để lọc & sắp xếp):"

        # Hiển thị DataFrame của Header Table nếu có
        if show_header:
            if header_to_display:
                st.write(f"**{header_caption}**")
                st.dataframe(show_header_table_df(header_to_display), use_container_width=True)
            else:
                st.info(f"{header_caption} - Rỗng.") # Thông báo nếu header rỗng
            st.markdown("---")

        # --- Hiển thị Thông tin Chi tiết của Bước ---
        # (Thêm các trường hợp hiển thị mới cho Single Path)
        if step_type == "load_data" or step_type == "load_data_empty":
            transactions_to_display = data.get("transactions")
            if isinstance(transactions_to_display, list):
                if transactions_to_display:
                    st.write("Dữ liệu gốc (đã phân tích):")
                    # Hiển thị giới hạn số giao dịch để tránh quá dài
                    max_display = 20
                    for i, tx in enumerate(transactions_to_display[:max_display]):
                        st.markdown(f"- **T{i+1}**: `{tx}`")
                    if len(transactions_to_display) > max_display:
                         st.caption(f"... và {len(transactions_to_display) - max_display} giao dịch khác.")
                else: st.info("Không có giao dịch hợp lệ nào được phân tích.")
            else: st.info("Không có dữ liệu giao dịch để hiển thị.")

        elif step_type == "frequency" or step_type == "frequency_empty":
            freqs = data.get("frequencies")
            frequent = data.get("frequent_items")
            min_sup = data.get('min_support', model.min_support if model else '?')
            if freqs: df_freq = pd.DataFrame(freqs.items(), columns=['Item', 'Count']); st.write("Tần suất ban đầu:"); st.dataframe(df_freq.sort_values(by='Count', ascending=False).reset_index(drop=True), hide_index=True, use_container_width=True)
            else: st.info("Không có dữ liệu tần suất.")
            if frequent: df_frequent = pd.DataFrame(frequent.items(), columns=['Item', 'Support']); st.write(f"Các Item Phổ biến (Support >= {min_sup}):"); st.dataframe(df_frequent.sort_values(by=['Support', 'Item'], ascending=[False, True]).reset_index(drop=True), hide_index=True, use_container_width=True)
            elif step_type != "frequency_empty": st.warning(f"Không tìm thấy item nào có Support >= {min_sup}.")

        elif step_type == "filter_transactions":
             transactions_dict = data.get("transactions")
             if transactions_dict:
                 st.write("Giao dịch đã lọc & sắp xếp theo FList:")
                 max_display = 20
                 items_list = list(transactions_dict.items())
                 for tx_id, items in items_list[:max_display]:
                     st.markdown(f"- **{tx_id}**: `{', '.join(map(str, items))}`")
                 if len(items_list) > max_display:
                     st.caption(f"... và {len(items_list) - max_display} giao dịch khác.")
             else: st.info("Không có giao dịch nào hợp lệ sau khi lọc.")

        elif step_type == "found_pattern":
             pattern = data.get('pattern', []); support = data.get('support', 'N/A')
             pattern_str = '{' + ', '.join(map(str, sorted(list(pattern)))) + '}'
             st.success(f"Tìm thấy: **{pattern_str}** (Support: {support})")

        elif step_type == "conditional_pattern_base":
             paths_items = data.get("paths_items_for_display", []) # [(path_list, count), ...]
             item_for_cpb = context.get('generating_item', '?') # Lấy từ context chính xác hơn
             if paths_items:
                 st.write(f"Các đường đi tiền tố (CPB) cho '{item_for_cpb}':")
                 path_colors = data.get("highlight_path_colors", {})
                 map_colors = {"red":"red","blue":"blue","green":"green","orange":"orange","purple":"violet","cyan":"cyan","magenta":"magenta","brown":"gray", "lightgrey":"gray"}
                 max_display = 15
                 for i, (path, count) in enumerate(paths_items[:max_display]):
                     path_id = i
                     gv_color = path_colors.get(path_id, "lightgrey")
                     disp_color = map_colors.get(gv_color, "gray")
                     path_str = ' → '.join(map(str, path)) if path else '(gốc)' # Hiển thị mũi tên
                     # Dùng markdown màu của streamlit
                     st.markdown(f"- **:{disp_color}[P{path_id + 1}]**: `{path_str}` (Count: {count})", unsafe_allow_html=True)
                 if len(paths_items) > max_display:
                      st.caption(f"... và {len(paths_items) - max_display} đường đi khác.")

                 # Lưu thông tin highlight vào session state để áp dụng cho cây bên cột 2
                 tree_obj_ref = data.get("generating_tree") # Tham chiếu đến cây gốc của CPB
                 if tree_obj_ref:
                     st.session_state.cpb_highlight_info = {
                         "node_to_path": data.get("highlight_node_ids_to_path",{}),
                         "path_colors": data.get("highlight_path_colors",{}),
                         "edge_colors": data.get("highlight_edge_id_colors",{}),
                         "applied_to_tree_id": id(tree_obj_ref), # Lưu ID của cây gốc
                         "generating_item_ctx": item_for_cpb,
                         "suffix_ctx": context.get("suffix",[])
                     }
             else:
                  # Nếu không có path nào, đảm bảo xóa highlight cũ
                  st.session_state.cpb_highlight_info = None

        # <<< Hiển thị cho các bước Single Path >>>
        elif step_type == "single_path_check":
            is_single = data.get("is_single_path")
            st.info(f"Kết quả kiểm tra: Cây hiện tại **{'LÀ' if is_single else 'KHÔNG PHẢI LÀ'}** một Single Path.")

        elif step_type == "single_path_items":
            items_counts = data.get("single_path_items", []) # [(item, count), ...]
            st.write("Item và Count trên đường đi đơn (bỏ qua root):")
            if items_counts:
                max_display = 20
                for item, count in items_counts[:max_display]:
                    st.markdown(f"- `{item}` : {count}")
                if len(items_counts) > max_display:
                    st.caption(f"... và {len(items_counts) - max_display} item khác.")
            else: st.info("Không có item nào trên đường đi đơn (ngoài root).")

        elif step_type == "single_path_generate_combo":
            beta_combo = data.get("beta_combo", [])
            pattern = data.get("pattern", [])
            support = data.get("support", "N/A")
            beta_str = '{' + ', '.join(map(str, sorted(beta_combo))) + '}'
            pattern_str = '{' + ', '.join(map(str, sorted(pattern))) + '}'
            st.write(f"Tạo tổ hợp β = `{beta_str}` từ Single Path.")
            st.success(f"Ghi nhận mẫu: **{pattern_str}** (Support: {support})")
        # ---

        elif step_type == "final_patterns":
             patterns_list = data.get("patterns")
             if patterns_list:
                 st.write(f"Tìm thấy tổng cộng {len(patterns_list)} tập phổ biến:")
                 st.dataframe(format_patterns_df(patterns_list), hide_index=True, use_container_width=True)
             else:
                 st.warning("Không tìm thấy tập phổ biến nào.")

        # Các bước khác thường chỉ có mô tả là đủ thông tin
        # elif step_type == "process_item": pass
        # elif step_type == "recursive_entry": pass
        # elif step_type == "recursive_call": pass
        # elif step_type in ["conditional_pattern_base_empty", "conditional_fptree_empty", "start_mining_empty", "build_fptree_empty", "no_frequent_items", "recursive_skip_empty", "single_path_end", "multi_path_check"]: pass

    # === Cột 2: Trực quan hóa Cây ===
    with display_cols[1]:
        tree_to_draw, caption_text = None, ""
        node_to_path_id_info_for_viz, path_colors_for_viz, edge_id_colors_for_viz = {}, {}, {}

        # --- Logic xác định cây cần vẽ ---
        # 1. Ưu tiên cây trong 'data' của bước hiện tại nếu nó được tạo/xử lý chính
        if step_type in ["build_fptree", "conditional_fptree", "build_fptree_empty", "recursive_call"] and data.get("root"):
            tree_to_draw = data.get("root")
        # 2. Nếu không, thử lấy cây từ 'context' (cây đang được xử lý hoặc cây nguồn)
        elif context.get("generating_tree"): # Cây đang được dùng để tạo CPB, xử lý item...
            tree_to_draw = context.get("generating_tree")
        elif context.get("source_tree"): # Cây nguồn đã tạo ra cây điều kiện hiện tại
            tree_to_draw = context.get("source_tree")
        elif data.get("root"): # Trường hợp khác có 'root' trong data (vd: recursive_entry)
             tree_to_draw = data.get("root")
        elif data.get("generating_tree"): # Trường hợp khác có 'generating_tree' (vd: CPB)
             tree_to_draw = data.get("generating_tree")

        # 3. Fallback: Nếu vẫn chưa có cây, thử tìm cây gần nhất ở các bước trước
        if tree_to_draw is None and step_index > 0:
             # Tìm lùi về các bước trước để lấy cây gần nhất đã được hiển thị/tạo
             for i in range(step_index - 1, -1, -1):
                  prev_step_info = model.steps[i]
                  prev_data = prev_step_info['data']
                  prev_ctx = prev_step_info['context']
                  candidate_tree = None
                  if 'root' in prev_data and isinstance(prev_data['root'], TreeNode):
                       candidate_tree = prev_data['root']
                  elif 'generating_tree' in prev_data and isinstance(prev_data['generating_tree'], TreeNode):
                       candidate_tree = prev_data['generating_tree']
                  elif 'generating_tree' in prev_ctx and isinstance(prev_ctx['generating_tree'], TreeNode):
                       candidate_tree = prev_ctx['generating_tree']
                  elif 'source_tree' in prev_ctx and isinstance(prev_ctx['source_tree'], TreeNode):
                       candidate_tree = prev_ctx['source_tree']

                  # Chỉ lấy cây nếu nó có vẻ hợp lệ (có gốc)
                  if candidate_tree and candidate_tree.item is None:
                      tree_to_draw = candidate_tree
                      caption_text = "(Hiển thị cây từ bước trước - ngữ cảnh)" # Thêm chú thích ngữ cảnh
                      break # Dừng tìm kiếm khi thấy cây hợp lệ

        # --- Xác định Caption dựa trên cây và bước hiện tại ---
        if tree_to_draw:
            tree_id = id(tree_to_draw)
            is_main_tree = (model.root and tree_id == id(model.root))
            current_suffix = context.get("suffix", None) # Lấy hậu tố từ context nếu có
            suffix_str = '{' + ', '.join(map(str, sorted(current_suffix))) + '}' if current_suffix else '{}'

            # Tạo caption mặc định dựa trên loại cây
            if is_main_tree and not current_suffix: caption_base = "FP-Tree Gốc"
            elif not is_main_tree and current_suffix is not None: caption_base = f"Cây Điều Kiện (α={suffix_str})"
            else: caption_base = "Cây FP-Tree" # Trường hợp khác

            # Tinh chỉnh caption dựa trên step_type
            if step_type == "build_fptree": caption_text = f"{caption_base} hoàn chỉnh."
            elif step_type == "conditional_fptree": generating_item = context.get("generating_item", "N/A"); caption_text = f"{caption_base} được tạo cho '{generating_item}'."
            elif step_type == "recursive_call": next_suffix = context.get("suffix",[]); next_suffix_str='{' + ', '.join(map(str, sorted(next_suffix))) + '}' if next_suffix else '{}'; caption_text = f"{caption_base} (sẽ dùng cho đệ quy với α={next_suffix_str})"
            elif step_type in ["single_path_check", "multi_path_check"]: is_single = data.get("is_single_path"); result = "Single Path" if is_single else "Nhiều Nhánh"; caption_text = f"{caption_base} (Kết quả kiểm tra: {result})"
            elif step_type == "recursive_entry": caption_text = f"{caption_base} (Bắt đầu xử lý đệ quy)"
            elif step_type == "process_item": item_ctx = data.get("item", "?"); caption_text = f"{caption_base} (Đang xử lý item '{item_ctx}')"
            elif step_type == "conditional_pattern_base": item_ctx = context.get("generating_item", "?"); caption_text = f"{caption_base} (Nguồn tạo CPB cho '{item_ctx}')"
            elif caption_text == "(Hiển thị cây từ bước trước - ngữ cảnh)": pass # Giữ nguyên caption fallback
            else: caption_text = caption_base # Sử dụng caption base nếu không có trường hợp đặc biệt

        # --- Kiểm tra và Áp dụng Highlight CPB từ Session State ---
        cpb_highlight_info = st.session_state.get("cpb_highlight_info")
        if isinstance(cpb_highlight_info, dict) and tree_to_draw:
            # Chỉ áp dụng highlight nếu ID của cây cần vẽ khớp với ID cây lúc highlight được tạo
            if id(tree_to_draw) == cpb_highlight_info.get("applied_to_tree_id"):
                node_to_path_id_info_for_viz = cpb_highlight_info.get("node_to_path", {})
                path_colors_for_viz = cpb_highlight_info.get("path_colors", {})
                edge_id_colors_for_viz = cpb_highlight_info.get("edge_colors", {})
                # Ghi đè caption để chỉ rõ đang highlight CPB
                if node_to_path_id_info_for_viz or edge_id_colors_for_viz:
                    item_ctx_ss = cpb_highlight_info.get("generating_item_ctx", "?")
                    suffix_ctx_ss = cpb_highlight_info.get("suffix_ctx", [])
                    suffix_str_ss = '{' + ', '.join(map(str, sorted(suffix_ctx_ss))) + '}' if suffix_ctx_ss else '{}'
                    caption_text = f"Highlight CPB cho '{item_ctx_ss}' (trong ngữ cảnh α={suffix_str_ss})"
            else:
                 # Nếu cây hiện tại khác cây highlight, xóa thông tin highlight để tránh áp dụng sai
                 # st.session_state.cpb_highlight_info = None # Không nên xóa ở đây, chỉ không áp dụng
                 pass

        # --- Vẽ Cây ---
        if tree_to_draw:
            # Kiểm tra xem cây có thực sự có con không (tránh vẽ cây chỉ có root)
            if any(tree_to_draw.children.values()):
                st.caption(caption_text) # Hiển thị caption đã xác định
                drawing_successful = False
                error_message = None

                if prefer_ascii:
                    try:
                        draw_fptree_ascii(tree_to_draw, node_to_path_id_info_for_viz, path_colors_for_viz)
                        drawing_successful = True
                    except Exception as ascii_error:
                         error_message = f"Lỗi vẽ ASCII: {ascii_error}"
                else: # Ưu tiên Graphviz
                    try:
                        graphviz_dot = draw_fptree_graphviz(tree_to_draw, node_to_path_id_info_for_viz, path_colors_for_viz, edge_id_colors_for_viz)
                        if graphviz_dot:
                            st.graphviz_chart(graphviz_dot)
                            drawing_successful = True
                        else:
                            error_message = "Graphviz tạo biểu đồ rỗng." # Lỗi tiềm ẩn
                    except graphviz.backend.execute.ExecutableNotFound as e:
                        error_message = f"Lỗi Graphviz: Không tìm thấy 'dot'. Cài đặt Graphviz và đảm bảo nó trong PATH hệ thống."
                        st.warning(error_message)
                        # Tự động chuyển sang ASCII nếu Graphviz lỗi
                        st.info("Chuyển sang vẽ bằng ASCII...")
                        try:
                            draw_fptree_ascii(tree_to_draw, node_to_path_id_info_for_viz, path_colors_for_viz)
                            drawing_successful = True # Vẫn thành công nếu ASCII vẽ được
                        except Exception as ascii_fallback_error:
                             error_message += f"\nLỗi vẽ ASCII dự phòng: {ascii_fallback_error}" # Ghi thêm lỗi ASCII
                             drawing_successful = False # Đánh dấu thất bại hoàn toàn
                    except Exception as draw_error:
                        error_message = f"Lỗi không mong muốn khi vẽ cây: {draw_error}"
                        st.warning(error_message)
                        st.info("Chuyển sang vẽ bằng ASCII...")
                        try:
                            draw_fptree_ascii(tree_to_draw, node_to_path_id_info_for_viz, path_colors_for_viz)
                            drawing_successful = True
                        except Exception as ascii_fallback_error:
                             error_message += f"\nLỗi vẽ ASCII dự phòng: {ascii_fallback_error}"
                             drawing_successful = False

                if not drawing_successful and error_message:
                    st.error(f"Không thể vẽ cây. {error_message}")
                elif not drawing_successful:
                     st.warning("Không thể vẽ cây (lý do không xác định).")

            else: # Cây chỉ có root node
                 steps_expecting_empty_tree = ["build_fptree_empty", "conditional_fptree_empty", "start_mining_empty", "no_frequent_items", "recursive_skip_empty"]
                 if step_type in steps_expecting_empty_tree:
                      st.info(f"{caption_text} - Cây rỗng (chỉ có nút Root).")
                 else:
                      st.warning(f"{caption_text} - Cây rỗng (chỉ có nút Root). Có thể không mong muốn ở bước này.")
        else: # Không xác định được cây nào để vẽ
            # Các bước không nhất thiết phải có cây
            steps_without_tree_needed = ["load_data", "load_data_empty", "frequency", "frequency_empty", "filter_transactions",
                                         "header_table_init", "found_pattern", "final_patterns", "single_path_items",
                                         "single_path_generate_combo", "conditional_pattern_base_empty",
                                         "start_mining_empty", "no_frequent_items"]
            if step_type not in steps_without_tree_needed:
                 st.info("Không có cây để hiển thị cho bước này.")


    # --- Logic Tự động chạy (Loại bỏ) ---
    # if st.session_state.is_autorun:
    #     if step_index < total_steps - 1:
    #         # Lấy delay từ slider
    #         delay = st.session_state.get("auto_delay", 1.5)
    #         time.sleep(delay)
    #         next_index = step_index + 1
    #         st.session_state.current_step_index = next_index
    #         # Xóa highlight CPB khi tự động chuyển bước
    #         st.session_state.cpb_highlight_info = None
    #         st.rerun()
    #     else: # Đã đến bước cuối
    #         st.session_state.is_autorun = False # Tự động dừng
    #         st.success("✅ Đã chạy tự động đến hết!")
    #         # Không cần rerun vì không có gì thay đổi nữa

# --- Trạng thái Ban đầu / Lỗi ---
elif not st.session_state.get('fp_growth_model'):
    st.info("Nhập dữ liệu và nhấn '🚀 Chạy Thuật Toán' để bắt đầu.")
elif not st.session_state.fp_growth_model.steps:
    st.warning("Thuật toán đã chạy nhưng không tạo ra bước nào. Kiểm tra lại dữ liệu đầu vào và ngưỡng hỗ trợ tối thiểu.")