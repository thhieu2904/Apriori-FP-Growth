# algorithms/fp_growth_logic.py
from collections import defaultdict, Counter
from itertools import combinations
# PerformanceMetrics sẽ được truyền vào từ main visualizer script
# from utils.metrics_collector import PerformanceMetrics 

class TreeNode:
    """Nút trong FP-Tree (tương tự file demo của bạn)"""
    def __init__(self, item_name, count, parent_node):
        self.item_name = item_name
        self.count = count
        self.parent = parent_node
        self.children = {}  # {item_name: TreeNode}
        self.next_node_link = None  # Liên kết đến nút tiếp theo có cùng item_name

    def increment_count(self, count_val):
        self.count += count_val

class FPGrowthAlgorithm:
    def __init__(self, transactions, min_support_count, metrics_collector):
        self.transactions = transactions # list of lists
        self.min_support_count = min_support_count
        self.metrics = metrics_collector
        self.intermediate_steps_data = []
        self.num_transactions = len(transactions)
        self.frequent_itemsets_final = {} # {frozenset: support_count}

    def _log_step_data(self, step_name, data_dict, notes=None, tree_dot=None, header_table_data=None):
        log_entry = {"step_name": step_name, "data": data_dict}
        if notes is not None: log_entry["notes"] = notes
        if tree_dot is not None: log_entry["tree_dot_object"] = tree_dot # Đối tượng graphviz DOT
        if header_table_data is not None: log_entry["header_table"] = header_table_data
        self.intermediate_steps_data.append(log_entry)

    def _scan1_find_frequent_1_itemsets_and_order(self):
        """
        Quét DB lần 1: Tìm các 1-itemset phổ biến và thứ tự của chúng (giảm dần theo support).
        """
        self.metrics.start_step("FP-Growth: Quét lần 1 - Tìm 1-itemset phổ biến")
        item_counts = Counter()
        for transaction in self.transactions:
            for item in transaction:
                item_counts[item] += 1
        
        self._log_step_data("Đếm 1-itemset ban đầu", dict(item_counts), 
                            notes=f"Tổng số item duy nhất ban đầu: {len(item_counts)}")

        frequent_1_itemsets_counts = {
            item: count for item, count in item_counts.items() if count >= self.min_support_count
        }
        # Sắp xếp theo tần suất giảm dần, sau đó theo tên item (để ổn định)
        ordered_frequent_items = sorted(
            frequent_1_itemsets_counts.keys(),
            key=lambda item: (frequent_1_itemsets_counts[item], item),
            reverse=True
        )
        
        self._log_step_data("1-itemset phổ biến (L1) và Thứ tự", 
                            {"counts": frequent_1_itemsets_counts, "order": ordered_frequent_items},
                            notes=f"Số 1-itemset phổ biến: {len(ordered_frequent_items)}")
        self.metrics.end_step(additional_info={"frequent_1_item_count": len(ordered_frequent_items)})
        
        if not ordered_frequent_items:
            return None, None # Không có item phổ biến nào
        return frequent_1_itemsets_counts, ordered_frequent_items

    def _build_fp_tree(self, ordered_transactions, frequent_1_item_counts):
        """
        Xây dựng FP-Tree từ các giao dịch đã được sắp xếp và lọc.
        """
        self.metrics.start_step("FP-Growth: Xây dựng FP-Tree chính")
        
        # Khởi tạo Header Table: item -> {'count': tổng count, 'node': con trỏ đến nút đầu tiên}
        header_table = {
            item: {'count': frequent_1_item_counts[item], 'node': None}
            for item in frequent_1_item_counts
        }
        
        root_node = TreeNode(item_name='root', count=1, parent_node=None)
        
        for transaction_items, transaction_count in ordered_transactions: # transaction_count thường là 1 trừ khi có trọng số
            current_node = root_node
            for item in transaction_items: # Các item đã được sắp xếp theo thứ tự L
                # Thêm item vào cây con của current_node
                child_node = current_node.children.get(item)
                if child_node:
                    child_node.increment_count(transaction_count)
                else:
                    child_node = TreeNode(item_name=item, count=transaction_count, parent_node=current_node)
                    current_node.children[item] = child_node
                    
                    # Liên kết nút mới vào header_table
                    # Nối vào đầu danh sách liên kết
                    if header_table[item]['node'] is None:
                        header_table[item]['node'] = child_node
                    else:
                        # Tìm cuối danh sách liên kết hiện tại và nối vào
                        temp_node = header_table[item]['node']
                        while temp_node.next_node_link is not None:
                            temp_node = temp_node.next_node_link
                        temp_node.next_node_link = child_node
                current_node = child_node # Di chuyển xuống nút con
        
        # Đếm số node trong cây (ước tính)
        num_nodes = 1 # for root
        queue = [root_node]
        while queue:
            node = queue.pop(0)
            num_nodes += len(node.children)
            for child in node.children.values():
                queue.append(child)
        self.metrics.fp_nodes_in_tree = num_nodes

        self._log_step_data("FP-Tree Chính đã xây dựng", 
                            {"message": "Cây đã được xây dựng. Xem trực quan hóa."},
                            notes=f"Số nút ước tính trong cây: {num_nodes}",
                            tree_dot=root_node, # Truyền root node để visualizer vẽ
                            header_table_data=header_table) # Truyền header table
        self.metrics.end_step(additional_info={"nodes_in_tree": num_nodes})
        return root_node, header_table

    def _mine_fp_tree_recursively(self, current_tree_root, current_header_table, prefix_path, min_sup_count):
        """
        Khai phá FP-Tree (hoặc Conditional FP-Tree) một cách đệ quy.
        Args:
            current_tree_root (TreeNode): Nút gốc của cây hiện tại.
            current_header_table (dict): Header table của cây hiện tại.
            prefix_path (frozenset): Tiền tố itemset đang được xét.
            min_sup_count (int): Ngưỡng support tối thiểu.
        """
        # Sắp xếp header table theo tần suất tăng dần (heuristic)
        # Trong demo gốc là giảm dần, nhưng nhiều tài liệu đề xuất tăng dần để xử lý item ít phổ biến trước
        sorted_items_in_header = sorted(
            current_header_table.items(), 
            key=lambda item_data_pair: item_data_pair[1]['count'] # Sắp theo count
        )

        for item_name, item_data in sorted_items_in_header:
            # Tạo frequent itemset mới: prefix + item_name
            new_frequent_itemset = prefix_path.union(frozenset([item_name]))
            self.frequent_itemsets_final[new_frequent_itemset] = item_data['count']
            
            self.metrics.start_step(f"FP-Growth: Khai phá cho item '{item_name}' với tiền tố {list(prefix_path) if prefix_path else '{}'}")

            # 1. Xây dựng Conditional Pattern Base (CPB)
            conditional_pattern_base = []
            path_node = item_data['node'] # Nút đầu tiên trong chuỗi liên kết của item_name
            
            while path_node is not None:
                # Lấy đường đi từ nút này lên gốc (không bao gồm nút item_name hiện tại)
                single_path_to_root = []
                temp_parent_node = path_node.parent
                # Điều kiện dừng được thay đổi để không phụ thuộc vào item_name cụ thể của root,
                # mà dựa vào việc node cha của nó có phải là None không (tức là nó là root).
                while temp_parent_node is not None and temp_parent_node.parent is not None:
                    single_path_to_root.append(temp_parent_node.item_name)
                    temp_parent_node = temp_parent_node.parent

                
                if single_path_to_root: # Chỉ thêm nếu đường đi không rỗng
                    # Đường đi đang ngược (từ node lên root), đảo lại
                    conditional_pattern_base.append({'path': list(reversed(single_path_to_root)), 'count': path_node.count})
                path_node = path_node.next_node_link
            
            self._log_step_data(f"Conditional Pattern Base cho '{item_name}' (tiền tố: {prefix_path})",
                                {"item": item_name, "prefix": list(prefix_path), "cpb": conditional_pattern_base},
                                notes=f"Tìm thấy {len(conditional_pattern_base)} đường đi.")

            # 2. Xây dựng Conditional FP-Tree từ CPB
            # Đếm tần suất các item trong CPB
            conditional_item_counts = Counter()
            for entry in conditional_pattern_base:
                for item_in_path in entry['path']:
                    conditional_item_counts[item_in_path] += entry['count']
            
            # Lọc các item phổ biến trong CPB
            frequent_items_in_cpb = {
                item: count for item, count in conditional_item_counts.items() if count >= min_sup_count
            }
            
            if not frequent_items_in_cpb:
                self._log_step_data(f"Kết thúc nhánh cho '{item_name}'", 
                                    {"message": "Không có item phổ biến nào trong Conditional Pattern Base."},
                                    notes="Không xây dựng Conditional FP-Tree.")
                self.metrics.end_step(additional_info={"conditional_tree_items": 0})
                continue # Chuyển sang item tiếp theo trong header table

            # Sắp xếp lại các đường đi trong CPB theo thứ tự item phổ biến mới
            ordered_conditional_paths = []
            for entry in conditional_pattern_base:
                ordered_path = [item for item in entry['path'] if item in frequent_items_in_cpb]
                # Sắp xếp path theo thứ tự tần suất giảm dần của frequent_items_in_cpb
                ordered_path.sort(key=lambda i: (frequent_items_in_cpb[i], i), reverse=True)
                if ordered_path:
                    ordered_conditional_paths.append({'path': ordered_path, 'count': entry['count']})
            
            # Xây dựng Conditional FP-Tree (tương tự _build_fp_tree)
            if ordered_conditional_paths:
                # Chuyển đổi ordered_conditional_paths sang dạng [(path_list, count)]
                paths_for_tree_build = [(p['path'], p['count']) for p in ordered_conditional_paths]
                
                cond_tree_root, cond_header_table = self._build_fp_tree_for_conditional(
                    paths_for_tree_build, frequent_items_in_cpb, 
                    log_prefix=f"Conditional cho '{item_name}' (tiền tố: {prefix_path})"
                )
                self.metrics.fp_conditional_trees_built += 1
                
                if cond_tree_root.children: # Nếu conditional tree không rỗng
                    # Đệ quy khai phá conditional tree
                    self._mine_fp_tree_recursively(cond_tree_root, cond_header_table, new_frequent_itemset, min_sup_count)
            
            self.metrics.end_step(additional_info={"conditional_tree_items": len(frequent_items_in_cpb)})


    def _build_fp_tree_for_conditional(self, ordered_paths_with_counts, frequent_items_in_paths, log_prefix=""):
        """Hàm phụ để xây dựng FP-Tree (chính hoặc có điều kiện)."""
        # Header table cho cây này
        current_header_table = {
            item: {'count': frequent_items_in_paths[item], 'node': None}
            for item in frequent_items_in_paths
        }
        root = TreeNode(item_name='cond_root', count=1, parent_node=None) # Tên root khác để phân biệt

        for path_items, path_count in ordered_paths_with_counts:
            current_node = root
            for item in path_items: # Items đã được sắp xếp theo L (của conditional context)
                child = current_node.children.get(item)
                if child:
                    child.increment_count(path_count)
                else:
                    child = TreeNode(item_name=item, count=path_count, parent_node=current_node)
                    current_node.children[item] = child
                    
                    if current_header_table[item]['node'] is None:
                        current_header_table[item]['node'] = child
                    else:
                        temp_node = current_header_table[item]['node']
                        while temp_node.next_node_link is not None:
                            temp_node = temp_node.next_node_link
                        temp_node.next_node_link = child
                current_node = child
        
        num_nodes = 1 
        q = [root]; visited_nodes_count = set()
        while q:
            n = q.pop(0)
            if id(n) in visited_nodes_count: continue
            visited_nodes_count.add(id(n))
            num_nodes +=1
            for child_node in n.children.values(): q.append(child_node)

        self._log_step_data(f"Xây dựng {log_prefix} FP-Tree",
                            {"message": "Cây đã được xây dựng. Xem trực quan hóa."},
                            notes=f"Số nút ước tính: {num_nodes}",
                            tree_dot=root, header_table_data=current_header_table)
        return root, current_header_table

    def run(self):
        self.metrics.start_overall_measurement()
        self.intermediate_steps_data = []
        self.frequent_itemsets_final = {}

        # 1. Quét DB lần 1: Tìm L1 và thứ tự
        frequent_1_item_counts, ordered_frequent_1_items = self._scan1_find_frequent_1_itemsets_and_order()
        if not ordered_frequent_1_items:
            self._log_step_data("Kết thúc sớm", {"message": "Không có 1-itemset phổ biến nào."}, 
                                notes="Thuật toán FP-Growth dừng.")
            self.metrics.end_overall_measurement()
            return {}, self.intermediate_steps_data

        # 2. Sắp xếp lại các giao dịch theo thứ tự L (ordered_frequent_1_items) và loại bỏ item không phổ biến
        self.metrics.start_step("FP-Growth: Chuẩn bị giao dịch cho xây dựng cây")
        ordered_transactions_for_tree = []
        for transaction in self.transactions:
            # Lọc item không phổ biến và sắp xếp theo thứ tự L
            filtered_transaction = [item for item in transaction if item in frequent_1_item_counts]
            # Sắp xếp filtered_transaction theo thứ tự của ordered_frequent_1_items
            # Tạo một map từ item sang index của nó trong ordered_frequent_1_items để sort
            order_map = {item: i for i, item in enumerate(ordered_frequent_1_items)}
            # Sắp xếp dựa trên index này (tức là theo count giảm dần, rồi theo tên)
            filtered_transaction.sort(key=lambda item: order_map[item])
            
            if filtered_transaction:
                ordered_transactions_for_tree.append((filtered_transaction, 1)) # (transaction_items, count=1)
        
        self._log_step_data("Giao dịch đã sắp xếp và lọc", 
                            {"count": len(ordered_transactions_for_tree), 
                             "example": ordered_transactions_for_tree[:5] if ordered_transactions_for_tree else []},
                            notes=f"Số giao dịch sau khi lọc và sắp xếp: {len(ordered_transactions_for_tree)}")
        self.metrics.end_step()

        if not ordered_transactions_for_tree:
             self._log_step_data("Kết thúc sớm", {"message": "Không có giao dịch nào sau khi lọc item không phổ biến."}, 
                                notes="Thuật toán FP-Growth dừng.")
             self.metrics.end_overall_measurement()
             return {}, self.intermediate_steps_data

        # 3. Xây dựng FP-Tree chính
        main_fp_tree_root, main_header_table = self._build_fp_tree(ordered_transactions_for_tree, frequent_1_item_counts)
        if not main_fp_tree_root.children: # Cây rỗng
            self._log_step_data("Kết thúc sớm", {"message": "FP-Tree chính rỗng sau khi xây dựng."},
                                notes="Thuật toán FP-Growth dừng.")
            self.metrics.end_overall_measurement()
            return {}, self.intermediate_steps_data

        # 4. Khai phá FP-Tree đệ quy
        self.metrics.start_step("FP-Growth: Bắt đầu khai phá đệ quy FP-Tree")
        self._mine_fp_tree_recursively(main_fp_tree_root, main_header_table, frozenset(), self.min_support_count)
        self.metrics.end_step()
        
        self._log_step_data("Hoàn thành khai phá", 
                            {"total_frequent_itemsets": len(self.frequent_itemsets_final)},
                            notes="Đã tìm thấy tất cả các tập mục phổ biến.")
        
        self.metrics.end_overall_measurement()
        return self.frequent_itemsets_final, self.intermediate_steps_data

    def generate_association_rules(self, all_frequent_itemsets, min_confidence):
        """Sinh luật kết hợp (tương tự Apriori)."""
        if not all_frequent_itemsets:
            return []

        self.metrics.start_step("FP-Growth: Sinh Luật Kết Hợp")
        rules = []
        
        for itemset, support_itemset_count in all_frequent_itemsets.items():
            if len(itemset) < 2:
                continue
            for i in range(1, len(itemset)):
                for antecedent_tuple in combinations(itemset, i):
                    antecedent = frozenset(antecedent_tuple)
                    consequent = itemset.difference(antecedent)
                    support_antecedent_count = all_frequent_itemsets.get(antecedent)
                    if support_antecedent_count is None or support_antecedent_count == 0:
                        continue
                    confidence = support_itemset_count / support_antecedent_count
                    if confidence >= min_confidence:
                        support_itemset_frac = support_itemset_count / self.num_transactions
                        support_antecedent_frac = support_antecedent_count / self.num_transactions
                        support_consequent_count = all_frequent_itemsets.get(consequent, 0) # Lấy count, nếu không có thì là 0
                        support_consequent_frac = support_consequent_count / self.num_transactions
                        
                        lift = 0
                        if support_antecedent_frac > 0 and support_consequent_frac > 0:
                            lift = support_itemset_frac / (support_antecedent_frac * support_consequent_frac)
                        
                        rules.append({
                            "antecedent": tuple(sorted(list(antecedent))),
                            "consequent": tuple(sorted(list(consequent))),
                            "support": support_itemset_frac,
                            "confidence": confidence,
                            "lift": lift,
                            "itemset_support_count": support_itemset_count,
                            "antecedent_support_count": support_antecedent_count,
                            "consequent_support_count": support_consequent_count
                        })
        
        self._log_step_data("Luật Kết Hợp Đã Sinh (FP-Growth)", rules, 
                            notes=f"Số luật: {len(rules)} với min_confidence={min_confidence:.2f}")
        self.metrics.end_step(additional_info={"rules_generated": len(rules)})
        return rules
