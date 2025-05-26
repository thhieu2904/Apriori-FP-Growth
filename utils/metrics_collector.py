# utils/metrics_collector.py
import time
import psutil
import os
from collections import defaultdict
from typing import Optional # Thêm Optional vào đây

class PerformanceMetrics:
    def __init__(self):
        self.overall_start_time = None
        self.overall_end_time = None
        self.overall_memory_before = None
        self.overall_memory_after = None
        
        self.step_timings = [] # List of dictionaries for each step
        self.current_step_name = None
        self.current_step_start_time = None
        self.current_step_memory_before = None
        
        # Specific metrics for algorithms
        self.apriori_candidates_generated_at_k = defaultdict(int)
        self.apriori_frequent_items_at_k = defaultdict(int)
        self.fp_nodes_in_tree = 0
        self.fp_conditional_trees_built = 0

    def _get_memory_usage_mb(self):
        """Trả về mức sử dụng bộ nhớ hiện tại của tiến trình (MB)."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)

    def start_overall_measurement(self):
        """Bắt đầu đo lường tổng thể."""
        self.overall_start_time = time.perf_counter()
        self.overall_memory_before = self._get_memory_usage_mb()
        self.step_timings = [] # Reset step timings

    def end_overall_measurement(self):
        """Kết thúc đo lường tổng thể."""
        self.overall_end_time = time.perf_counter()
        self.overall_memory_after = self._get_memory_usage_mb()

    def start_step(self, step_name):
        """Bắt đầu đo lường cho một bước cụ thể."""
        self.current_step_name = step_name
        self.current_step_start_time = time.perf_counter()
        self.current_step_memory_before = self._get_memory_usage_mb()

    def end_step(self, additional_info=None):
        """Kết thúc đo lường cho bước hiện tại."""
        if self.current_step_start_time is None:
            # print(f"Cảnh báo: end_step được gọi cho '{self.current_step_name}' mà không có start_step.")
            return

        step_end_time = time.perf_counter()
        step_memory_after = self._get_memory_usage_mb()
        
        duration = step_end_time - self.current_step_start_time
        memory_used_step = step_memory_after - self.current_step_memory_before
        
        step_data = {
            "step_name": self.current_step_name,
            "duration_seconds": duration,
            "memory_before_MB": self.current_step_memory_before,
            "memory_after_MB": step_memory_after,
            "memory_change_MB": memory_used_step,
        }
        if additional_info:
            step_data.update(additional_info)
            
        self.step_timings.append(step_data)
        
        # Reset for next step
        self.current_step_name = None
        self.current_step_start_time = None
        self.current_step_memory_before = None

    def record_apriori_candidates(self, k, count):
        self.apriori_candidates_generated_at_k[k] += count

    def record_apriori_frequent_items(self, k, count):
        self.apriori_frequent_items_at_k[k] += count

    def get_overall_metrics_summary(self):
        """Trả về tóm tắt số liệu tổng thể."""
        if self.overall_start_time is None or self.overall_end_time is None:
            return {
                "total_duration_seconds": "N/A",
                "initial_memory_MB": "N/A",
                "final_memory_MB": "N/A",
                "peak_memory_usage_MB": "N/A (ước tính đơn giản)" 
            }
        
        total_duration = self.overall_end_time - self.overall_start_time
        # Peak memory is simplified here; for true peak, continuous monitoring or a profiler is needed.
        # We can estimate peak as the max of 'memory_after_MB' across steps or overall_memory_after.
        max_step_memory = 0
        if self.step_timings:
            max_step_memory = max(s['memory_after_MB'] for s in self.step_timings if 'memory_after_MB' in s)
        
        peak_memory = max(self.overall_memory_before or 0, self.overall_memory_after or 0, max_step_memory)

        return {
            "total_duration_seconds": f"{total_duration:.4f}",
            "initial_memory_MB": f"{self.overall_memory_before:.2f}" if self.overall_memory_before is not None else "N/A",
            "final_memory_MB": f"{self.overall_memory_after:.2f}" if self.overall_memory_after is not None else "N/A",
            "peak_memory_usage_MB": f"{peak_memory:.2f}" if peak_memory > 0 else "N/A (ước tính)"
        }

    def get_step_metrics_table(self):
        """Trả về dữ liệu các bước dưới dạng list of dicts, phù hợp cho Pandas DataFrame."""
        return self.step_timings
        
    def get_apriori_metrics_summary(self):
        total_candidates = sum(self.apriori_candidates_generated_at_k.values())
        total_frequent = sum(self.apriori_frequent_items_at_k.values())
        return {
            "total_candidates_generated": total_candidates,
            "total_frequent_itemsets_found": total_frequent,
            "candidates_per_k": dict(self.apriori_candidates_generated_at_k),
            "frequent_itemsets_per_k": dict(self.apriori_frequent_items_at_k),
        }

    def get_fp_growth_metrics_summary(self):
        return {
            "nodes_in_fp_tree": self.fp_nodes_in_tree,
            "conditional_fp_trees_built": self.fp_conditional_trees_built,
        }

    def get_node_count_for_step(self, step_name_to_find: str) -> Optional[int]:
        """
        Lấy số lượng nút được ghi nhận cho một bước cụ thể.
        Giả sử số nút được lưu trong additional_info với key 'nodes_in_tree' 
        (dùng cho cây FP-Tree chính) hoặc một key tương tự cho cây điều kiện nếu bạn có log riêng.
        """
        for step_metric in self.step_timings: # Duyệt qua self.step_timings
            if step_metric.get("step_name") == step_name_to_find:
                additional_info = step_metric.get("additional_info", {})
                # Ưu tiên key 'nodes_in_tree' mà bạn đã dùng trong fp_growth_logic.py
                if "nodes_in_tree" in additional_info:
                    return additional_info["nodes_in_tree"]
                # Bạn có thể thêm các key khác ở đây nếu cần, ví dụ: 'conditional_tree_node_count'
        return None # Không tìm thấy thông tin số nút cho bước này
