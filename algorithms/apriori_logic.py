# algorithms/apriori_logic.py
from collections import defaultdict
from itertools import combinations
import math
# PerformanceMetrics sẽ được truyền vào từ main visualizer script
# from utils.metrics_collector import PerformanceMetrics 

class AprioriAlgorithm:
    def __init__(self, transactions, min_support_count, metrics_collector):
        self.transactions_list_of_sets = [set(t) for t in transactions]
        self.num_transactions = len(transactions)
        self.min_support_count = min_support_count
        self.metrics = metrics_collector
        self.intermediate_steps_data = [] # Lưu trữ dữ liệu cho từng bước để trực quan hóa

    def _log_step_data(self, step_name, data_dict, k=None, notes=None):
        """Ghi lại dữ liệu của một bước."""
        log_entry = {"step_name": step_name, "data": data_dict}
        if k is not None:
            log_entry["k"] = k
        if notes is not None:
            log_entry["notes"] = notes
        self.intermediate_steps_data.append(log_entry)

    def _generate_L1(self):
        """Tạo tập 1-itemset phổ biến (L1)."""
        self.metrics.start_step("Apriori: Tạo L1 - Đếm 1-itemsets")
        item_counts = defaultdict(int)
        for transaction in self.transactions_list_of_sets:
            for item in transaction:
                item_counts[frozenset([item])] += 1
        
        self._log_step_data("Đếm 1-itemset ban đầu (C1)", dict(item_counts), k=1, 
                            notes=f"Tổng số 1-itemset ứng viên: {len(item_counts)}")
        self.metrics.record_apriori_candidates(1, len(item_counts))
        self.metrics.end_step(additional_info={"candidate_count": len(item_counts)})

        self.metrics.start_step("Apriori: Tạo L1 - Lọc theo min_support")
        L1 = {itemset: count for itemset, count in item_counts.items() if count >= self.min_support_count}
        self._log_step_data("L1 - 1-itemset phổ biến", dict(L1), k=1, 
                            notes=f"Số 1-itemset phổ biến: {len(L1)}")
        self.metrics.record_apriori_frequent_items(1, len(L1))
        self.metrics.end_step(additional_info={"frequent_count": len(L1)})
        return L1

    def _generate_candidates_Ck(self, Lk_minus_1_itemsets, k):
      """Tạo tập ứng viên k-itemset (Ck) từ (k-1)-itemset phổ biến (Lk-1)."""
      self.metrics.start_step(f"Apriori: Tạo C{k} - Bước Join")
      candidates_Ck = set()
      prev_frequent_items_list = list(Lk_minus_1_itemsets) # list of frozensets

      for i in range(len(prev_frequent_items_list)):
          for j in range(i + 1, len(prev_frequent_items_list)):
              itemset1 = prev_frequent_items_list[i]
              itemset2 = prev_frequent_items_list[j]
              union_set = itemset1 | itemset2
              if len(union_set) == k:
                  candidates_Ck.add(union_set)

      self._log_step_data(f"C{k} - Ứng viên {k}-itemset (sau Join)", 
                          list(candidates_Ck), k=k,
                          notes=f"Số ứng viên sau join: {len(candidates_Ck)}")
      self.metrics.end_step(additional_info={"candidates_after_join": len(candidates_Ck)})
      return candidates_Ck

    def _prune_candidates_Ck(self, Ck, Lk_minus_1_itemsets_set, k):
        """Bước tỉa: Loại bỏ các ứng viên trong Ck mà có tập con (k-1) không phổ biến."""
        self.metrics.start_step(f"Apriori: Tạo C{k} - Bước Prune")
        pruned_Ck = set()
        for candidate in Ck:
            is_valid = True
            # Tạo tất cả các (k-1)-subset của candidate
            for subset in combinations(candidate, k - 1):
                if frozenset(subset) not in Lk_minus_1_itemsets_set:
                    is_valid = False
                    break
            if is_valid:
                pruned_Ck.add(candidate)
        
        self._log_step_data(f"C{k} - Ứng viên {k}-itemset (sau Prune)", 
                            list(pruned_Ck), k=k,
                            notes=f"Số ứng viên sau prune: {len(pruned_Ck)}")
        self.metrics.record_apriori_candidates(k, len(pruned_Ck))
        self.metrics.end_step(additional_info={"candidates_after_prune": len(pruned_Ck)})
        return pruned_Ck

    def _scan_transactions_for_Lk(self, Ck_pruned, k):
        """Quét DB để đếm support cho các ứng viên đã tỉa và tạo Lk."""
        self.metrics.start_step(f"Apriori: Tạo L{k} - Đếm support và Lọc")
        item_counts = defaultdict(int)
        for transaction in self.transactions_list_of_sets:
            for candidate in Ck_pruned:
                if candidate.issubset(transaction):
                    item_counts[candidate] += 1
        
        Lk = {itemset: count for itemset, count in item_counts.items() if count >= self.min_support_count}
        self._log_step_data(f"L{k} - {k}-itemset phổ biến", dict(Lk), k=k,
                            notes=f"Số {k}-itemset phổ biến: {len(Lk)}")
        self.metrics.record_apriori_frequent_items(k, len(Lk))
        self.metrics.end_step(additional_info={"frequent_count": len(Lk)})
        return Lk

    def run(self):
        """Chạy thuật toán Apriori."""
        self.metrics.start_overall_measurement()
        self.intermediate_steps_data = [] # Reset
        
        all_frequent_itemsets = {} # {itemset: support_count}

        # Bước 1: Tạo L1
        L1 = self._generate_L1()
        if not L1:
            self.metrics.end_overall_measurement()
            return {}, self.intermediate_steps_data # Trả về dict rỗng nếu không có L1
        
        all_frequent_itemsets.update(L1)
        
        Lk_minus_1 = L1
        k = 2
        while Lk_minus_1: # Tiếp tục khi Lk-1 không rỗng
            Lk_minus_1_itemsets_set = set(Lk_minus_1.keys()) # Dùng cho bước prune

            # Tạo Ck
            candidates_Ck_joined = self._generate_candidates_Ck(Lk_minus_1_itemsets_set, k)
            if not candidates_Ck_joined:
                self._log_step_data(f"C{k} - Kết thúc", {}, k=k, notes="Không có ứng viên nào được tạo sau join.")
                break 

            # Prune Ck
            candidates_Ck_pruned = self._prune_candidates_Ck(candidates_Ck_joined, Lk_minus_1_itemsets_set, k)
            if not candidates_Ck_pruned:
                self._log_step_data(f"L{k} - Kết thúc", {}, k=k, notes="Không có ứng viên nào sau khi prune.")
                break
            
            # Tạo Lk bằng cách quét DB
            Lk = self._scan_transactions_for_Lk(candidates_Ck_pruned, k)
            if not Lk:
                self._log_step_data(f"L{k} - Kết thúc", {}, k=k, notes=f"Không có {k}-itemset phổ biến nào.")
                break

            all_frequent_itemsets.update(Lk)
            Lk_minus_1 = Lk
            k += 1
            
        self.metrics.end_overall_measurement()
        return all_frequent_itemsets, self.intermediate_steps_data

    def generate_association_rules(self, all_frequent_itemsets, min_confidence):
        """
        Sinh luật kết hợp từ các tập mục phổ biến.
        Args:
            all_frequent_itemsets (dict): {frozenset: support_count}
            min_confidence (float): Ngưỡng confidence tối thiểu.
        Returns:
            list: Danh sách các luật, mỗi luật là một dict.
        """
        if not all_frequent_itemsets:
            return []

        self.metrics.start_step("Apriori: Sinh Luật Kết Hợp")
        rules = []
        
        for itemset, support_itemset_count in all_frequent_itemsets.items():
            if len(itemset) < 2: # Luật cần ít nhất 2 item
                continue

            # Sinh tất cả các tập con không rỗng của itemset để làm tiền đề (antecedent)
            # Chỉ cần duyệt các tập con có độ dài từ 1 đến len(itemset)-1
            for i in range(1, len(itemset)):
                for antecedent_tuple in combinations(itemset, i):
                    antecedent = frozenset(antecedent_tuple)
                    consequent = itemset.difference(antecedent)

                    # Lấy support count của antecedent
                    support_antecedent_count = all_frequent_itemsets.get(antecedent)

                    if support_antecedent_count is None or support_antecedent_count == 0:
                        # Điều này không nên xảy ra nếu all_frequent_itemsets chứa tất cả các tập con phổ biến
                        continue 
                    
                    confidence = support_itemset_count / support_antecedent_count
                    
                    if confidence >= min_confidence:
                        support_itemset_frac = support_itemset_count / self.num_transactions
                        support_antecedent_frac = support_antecedent_count / self.num_transactions
                        
                        # Lấy support count của consequent để tính lift
                        support_consequent_count = all_frequent_itemsets.get(consequent)
                        if support_consequent_count is None: # Có thể xảy ra nếu consequent là 1 item đơn lẻ và không có trong L1 (ít khả năng)
                            support_consequent_frac = 0
                        else:
                            support_consequent_frac = support_consequent_count / self.num_transactions
                        
                        lift = 0
                        if support_antecedent_frac > 0 and support_consequent_frac > 0:
                            lift = support_itemset_frac / (support_antecedent_frac * support_consequent_frac)
                        else: # Tránh chia cho 0 nếu support của consequent là 0 (ví dụ, item không phổ biến đơn lẻ)
                            lift = 0 # Hoặc có thể coi là không xác định / không thú vị

                        rules.append({
                            "antecedent": tuple(sorted(list(antecedent))),
                            "consequent": tuple(sorted(list(consequent))),
                            "support": support_itemset_frac,
                            "confidence": confidence,
                            "lift": lift,
                            "itemset_support_count": support_itemset_count,
                            "antecedent_support_count": support_antecedent_count,
                            "consequent_support_count": support_consequent_count if support_consequent_count is not None else 0
                        })
        
        self._log_step_data("Luật Kết Hợp Đã Sinh", rules, 
                            notes=f"Số luật: {len(rules)} với min_confidence={min_confidence:.2f}")
        self.metrics.end_step(additional_info={"rules_generated": len(rules)})
        return rules
