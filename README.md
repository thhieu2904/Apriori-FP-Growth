# Basket Analysis – Khai phá luật kết hợp với Apriori & FP-Growth

Dự án triển khai hai thuật toán khai phá luật kết hợp phổ biến (Apriori & FP-Growth) trên dữ liệu giao dịch bán lẻ, với giao diện Streamlit trực quan. Người dùng có thể upload dữ liệu CSV/Excel, tùy chỉnh tham số, theo dõi kết quả và so sánh hiệu năng.

---

## 1. Cài đặt môi trường

```bash
pip install streamlit pandas graphviz openpyxl psutil
```

> Nếu dùng Windows và muốn trực quan FP-Tree, tải Graphviz:
> [https://graphviz.gitlab.io/\_pages/Download/Download_windows.html](https://graphviz.gitlab.io/_pages/Download/Download_windows.html)
> Và thêm vào PATH nếu cần.

---

## 2. Tổ chức mã nguồn

```
your_project/
├─ main_apriori_visualizer.py       # Giao diện Streamlit: Apriori
├─ main_fp_growth_visualizer.py     # Giao diện Streamlit: FP-Growth
├─ algorithms/
│    ├─ apriori_logic.py            # Thuật toán Apriori
│    └─ fp_growth_logic.py          # Thuật toán FP-Growth
├─ utils/
│    ├─ data_loader.py              # Đọc & xử lý dữ liệu
│    ├─ metrics_collector.py        # Đo hiệu năng
│    └─ visualizers.py              # Trực quan hóa bảng, cây, luật
├─ data/
│    └─ (file csv, xlsx mẫu và thực tế)
```

---

## 3. Cách chạy

```bash
streamlit run main_apriori_visualizer.py
# hoặc
streamlit run main_fp_growth_visualizer.py
```

Sau đó truy cập trình duyệt, upload file dữ liệu (csv/xlsx), tùy chỉnh và khai phá trực tiếp.

---

## 4. Yêu cầu dữ liệu

- File cần có tối thiểu 2 cột: `InvoiceNo` (hoặc tương đương) và `Description` (tên sản phẩm).
- Hỗ trợ đọc cả CSV và Excel (xls/xlsx).
- Có thể dùng các file mẫu nhỏ hoặc file lớn Online Retail thực tế.

---

## 5. Chức năng nổi bật

- Tiền xử lý dữ liệu bán lẻ (Online Retail hoặc mẫu nhỏ).
- Khai phá luật kết hợp với hai thuật toán kinh điển (Apriori, FP-Growth).
- Hiển thị chi tiết từng bước khai phá, trực quan hóa FP-Tree, bảng luật kết hợp.
- Đo, so sánh hiệu năng hai giải thuật trực tiếp trên giao diện.
- Có thể mở song song hai app để đối chiếu kết quả và hiệu suất.

---

## 6. Liên hệ & tác giả

- **Tác giả:** Nguyễn Thanh Hiếu, 2025
- **Ứng dụng:** Đồ án học thuật, nghiên cứu & demo khai phá dữ liệu

---
