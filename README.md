# 📊 Phân Tích Giỏ Hàng & Khai Phá Luật Kết Hợp với Apriori & FP-Growth 🛒

Dự án này cung cấp một bộ công cụ trực quan và mạnh mẽ để thực hiện **phân tích giỏ hàng** và **khai phá luật kết hợp** từ dữ liệu giao dịch. Sử dụng hai thuật toán kinh điển là **Apriori** và **FP-Growth**, ứng dụng được xây dựng với giao diện web tương tác bằng **Streamlit**, cho phép người dùng dễ dàng tải lên và xử lý dữ liệu, tùy chỉnh tham số, theo dõi chi tiết quá trình thực thi thuật toán, trực quan hóa kết quả (bao gồm cả FP-Tree), và so sánh hiệu năng.

---

## ✨ Tính Năng Nổi Bật

Ứng dụng này nổi bật với các khả năng toàn diện, giúp người dùng từ trực quan hóa dữ liệu đến khai phá tri thức ẩn sâu:

- **Triển Khai Hai Thuật Toán Cốt Lõi:**

  - **Apriori:** Theo dõi từng bước tạo tập ứng viên (C<sub>k</sub>) và tập mục phổ biến (L<sub>k</sub>).
  - **FP-Growth:**
    - Trực quan hóa FP-Tree chính và các FP-Tree điều kiện một cách tương tác (sử dụng Graphviz).
    - Hiển thị Header Table, Conditional Pattern Base (CPB) trong quá trình khai phá.
    - Tối ưu hóa cho trường hợp cây là một đường đi đơn (Single Path).
    - Có tùy chọn `MAX_NODES_FOR_GRAPHICAL_VIEW` để giới hạn số nút khi vẽ cây, nếu vượt quá sẽ hiển thị Header Table thay vì cố gắng vẽ cây quá lớn.

- **Giao Diện Người Dùng Trực Quan (Streamlit):**

  - Thiết kế responsive, dễ sử dụng trên nhiều thiết bị.
  - Tách biệt giao diện cho Apriori và FP-Growth để dễ dàng so sánh song song.

- **Đa Dạng Phương Thức Nhập Liệu:**

  - **Tải File Lên:** Hỗ trợ các định dạng `CSV`, `Excel (.xlsx, .xls)`. Người dùng có thể tùy chỉnh tên cột cho Mã Giao Dịch, Tên Sản Phẩm, Mã Khách Hàng, và Quốc Gia.
  - **Nhập Trực Tiếp (Groceries List):** Dữ liệu dạng danh sách các sản phẩm, mỗi dòng một giao dịch. Tùy chỉnh ký tự phân tách, có/không có dòng tiêu đề, và tùy chọn bỏ qua cột đầu tiên.
  - **Nhập Trực Tiếp (Định dạng Tx: \[]):** Dữ liệu theo cấu trúc `TênGiaoDịch: [item1, item2,...]`.
  - Cung cấp dữ liệu mẫu mặc định cho các phương thức nhập trực tiếp để dễ dàng thử nghiệm.

- **Tiền Xử Lý & Lọc Dữ Liệu Nâng Cao (Cho file tải lên):**

  - **Làm Sạch Chuyên Biệt:** Tùy chọn áp dụng các quy tắc làm sạch dữ liệu cho bộ "Online Retail" (ví dụ: loại bỏ mã 'POST', 'MANUAL', giao dịch hủy 'C', Quantity <=0).
  - **Lọc Theo Điều Kiện:** Lọc dữ liệu dựa trên `Mã Khách Hàng (CustomerID)` và `Quốc Gia (Country)`. Tham khảo gợi ý các giá trị lọc phổ biến từ file [`goi_y_loc_theo_CusID_va_Quoc_gia.md`](./goi_y_loc_theo_CusID_va_Quoc_gia.md).

- **Trực Quan Hóa & Phân Tích Kết Quả Chi Tiết:**

  - Hiển thị rõ ràng **các tập mục phổ biến** với số đếm support của chúng.
  - Trình bày **luật kết hợp** cùng các chỉ số quan trọng: Support, Confidence, và Lift.
  - Theo dõi các bước trung gian và log của thuật toán.
  - **Bảng Tóm Tắt Luật Kết Hợp:** Cung cấp cái nhìn tổng quan, dễ hiểu về các luật kết hợp hàng đầu, được Việt hóa và đánh giá mức độ mạnh yếu của luật (ví dụ: "Rất Mạnh", "Khá Mạnh"). Giúp người dùng nhanh chóng xác định các mối quan hệ quan trọng.
  - **Biểu Đồ Mạng Lưới Luật Kết Hợp:** Trực quan hóa các luật kết hợp hàng đầu dưới dạng biểu đồ mạng tương tác. Các nút (sản phẩm) và cạnh (luật) được hiển thị rõ ràng, giúp người dùng dễ dàng nhận diện các sản phẩm thường được mua cùng nhau và mức độ liên quan của chúng. Các nút được tô màu để phân biệt trực quan hơn.

- **Đo Lường & So Sánh Hiệu Năng:**

  - Thu thập và hiển thị các số liệu hiệu năng: tổng thời gian chạy, sử dụng bộ nhớ (ban đầu, cuối cùng, đỉnh ước tính).
  - Cung cấp thông tin chi tiết về số lượng ứng viên/tập mục phổ biến (Apriori), số nút trong FP-Tree, số Conditional FP-Tree được xây dựng (FP-Growth).
  - Phân tích hiệu năng từng bước chính của thuật toán.

- **Tùy Chỉnh Tham Số Linh Hoạt:**

  - Điều chỉnh Ngưỡng Support Tối Thiểu (%) và Ngưỡng Confidence Tối Thiểu (%) thông qua thanh trượt trực quan.
  - Giá trị support tuyệt đối được tính toán và hiển thị dựa trên tỷ lệ phần trăm và tổng số giao dịch.

- **Khả Năng Tương Tác:**
  - Nút "Đặt lại Tất cả" cho phép xóa trạng thái hiện tại và bắt đầu phân tích mới một cách dễ dàng.

---

## 🛠️ Công Nghệ Sử Dụng

- **Python 3.x**
- **Streamlit:** Xây dựng giao diện người dùng web tương tác.
- **Pandas:** Xử lý, thao tác và phân tích dữ liệu.
- **Graphviz:** Trực quan hóa cấu trúc cây FP-Tree.
- **Psutil:** Thu thập thông tin về sử dụng bộ nhớ hệ thống (được sử dụng bởi `metrics_collector.py`).
- **Openpyxl:** Đọc và ghi file định dạng Excel.
- **Pyvis:** Tạo biểu đồ mạng lưới tương tác cho các luật kết hợp.

---

## ⚙️ Cài Đặt Môi Trường

1.  **Cài đặt Python:** Đảm bảo bạn đã cài đặt Python (khuyến nghị phiên bản 3.8 trở lên).
2.  **Tạo môi trường ảo (Khuyến khích):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Trên Linux/macOS
    venv\Scripts\activate    # Trên Windows
    ```
3.  **Cài đặt các thư viện cần thiết:**
    ```bash
    pip install streamlit pandas graphviz openpyxl psutil
    ```
4.  **Cài đặt Graphviz (Bắt buộc để trực quan hóa FP-Tree dạng đồ họa):**
    - **Windows:**
      - Tải bộ cài đặt từ: [https://graphviz.gitlab.io/\_pages/Download/Download_windows.html](https://graphviz.gitlab.io/_pages/Download/Download_windows.html)
      - Trong quá trình cài đặt, **đảm bảo chọn tùy chọn "Add Graphviz to the system PATH"** (Thêm Graphviz vào biến môi trường PATH cho người dùng hiện tại hoặc tất cả người dùng). Nếu không, bạn cần thêm thủ công thư mục `bin` của Graphviz (ví dụ: `C:\Program Files\Graphviz\bin`) vào biến môi trường PATH của hệ thống.
    - **Linux (Ubuntu/Debian):**
      ```bash
      sudo apt-get update
      sudo apt-get install graphviz
      ```
    - **macOS (sử dụng Homebrew):**
      ```bash
      brew install graphviz
      ```
    - _Lưu ý:_ Nếu Graphviz không được cài đặt hoặc không tìm thấy trong PATH, chức năng trực quan hóa FP-Tree dạng đồ họa sẽ không hoạt động. Ứng dụng (phiên bản FP-Growth) sẽ hiển thị Header Table khi cây quá lớn hoặc có thể không hiển thị cây nếu Graphviz thiếu.

---

## 📂 Tổ Chức Mã Nguồn

Dự án được tổ chức như sau:

```text
project/
├── .streamlit/
│   └── config.toml                # File cấu hình theme cho Streamlit
├── algorithms/
│   ├── apriori_logic.py           # Logic thuật toán Apriori
│   └── fp_growth_logic.py         # Logic thuật toán FP-Growth
├── data/                          # Dữ liệu mẫu
│   └── online_retail.csv
├── utils/
│   ├── data_loader.py             # Tải và xử lý dữ liệu
│   ├── metrics_collector.py       # Đo lường hiệu năng
│   └── visualizers.py             # Trực quan hóa dữ liệu
├── goi_y_loc_theo_CusID_va_Quoc_gia.md # Ghi chú gợi ý các giá trị lọc
├── main_apriori_visualizer.py     # Giao diện Streamlit Apriori
├── main_fp_growth_visualizer.py   # Giao diện Streamlit FP-Growth
└── README.md                      # File hướng dẫn này
```

---

## 🚀 Cách Chạy Ứng Dụng

1.  Mở Terminal (hoặc Command Prompt/PowerShell trên Windows).
2.  Điều hướng đến thư mục gốc của dự án (ví dụ: `your_project_root`).
3.  Nếu bạn đã tạo môi trường ảo, hãy kích hoạt nó.
4.  Chạy một trong các lệnh sau để khởi động ứng dụng tương ứng:

    - **Để khởi chạy trình trực quan Apriori:**
      ```bash
      streamlit run main_apriori_visualizer.py
      ```
    - **Để khởi chạy trình trực quan FP-Growth:**
      ```bash
      streamlit run main_fp_growth_visualizer.py
      ```

5.  Streamlit sẽ tự động mở một tab mới trong trình duyệt web mặc định của bạn, hiển thị giao diện ứng dụng.
6.  Sử dụng thanh bên (sidebar) để chọn phương thức nhập liệu, tải file hoặc nhập dữ liệu, cấu hình các tham số và tùy chọn lọc, sau đó nhấn nút "🚀 Chạy Thuật Toán..." để bắt đầu phân tích.

---

## 📋 Yêu Cầu Dữ Liệu Đầu Vào

- **Đối với file tải lên (`CSV`, `Excel`):**
  - Cần có ít nhất một cột định danh giao dịch (mặc định là `InvoiceNo`) và một cột chứa tên sản phẩm/item (mặc định là `Description`). Tên các cột này có thể được tùy chỉnh trên giao diện.
  - Nếu sử dụng các tùy chọn lọc nâng cao (CustomerID, Country), file cần có các cột tương ứng.
- **Đối với nhập liệu trực tiếp (Groceries List):**
  - Mỗi dòng đại diện cho một giao dịch.
  - Các item trong một giao dịch được phân tách bằng một ký tự do người dùng định nghĩa (mặc định là dấu phẩy `,`).
  - Có tùy chọn bỏ qua dòng tiêu đề và bỏ qua cột đầu tiên của mỗi dòng (hữu ích cho một số định dạng file groceries).
- **Đối với nhập liệu trực tiếp (Định dạng `Tx: []`):**
  - Mỗi dòng phải theo định dạng `TênGiaoDịch: [item1, item2, item3,...]`. Ví dụ: `T1: [A, B, C]`.

---

## 💡 Hướng Dẫn Sử Dụng & Gợi Ý

1.  **Chọn Phương Thức Nhập Liệu:** Trên thanh bên, chọn cách bạn muốn cung cấp dữ liệu (tải file hoặc nhập trực tiếp).
2.  **Cấu Hình Dữ Liệu:**
    - Nếu tải file, chỉ định đúng tên các cột quan trọng.
    - Nếu nhập trực tiếp, đảm bảo dữ liệu tuân theo định dạng đã chọn.
3.  **Áp Dụng Lọc (Nếu Cần):** Đối với file tải lên, bạn có thể sử dụng các tùy chọn lọc nâng cao theo Mã Khách Hàng hoặc Quốc Gia. Tham khảo file `goi_y_loc_theo_CusID_va_Quoc_gia.md` để có các giá trị gợi ý khi làm việc với dữ liệu Online Retail.
4.  **Thiết Lập Tham Số Thuật Toán:** Điều chỉnh `Ngưỡng Support Tối Thiểu (%)` và `Ngưỡng Confidence Tối Thiểu (%)` cho phù hợp với bộ dữ liệu và mục tiêu phân tích của bạn.
5.  **Chạy Phân Tích:** Nhấn nút "🚀 Chạy Thuật Toán..."
6.  **Khám Phá Kết Quả:**

    - **Tab "Tổng Quan & Số Liệu":** Xem xét thời gian chạy, mức sử dụng bộ nhớ và các thống kê chung.
    - **Tab "Bước Trung Gian" / "Bước Trung Gian & FP-Tree":** Theo dõi các bước xử lý của thuật toán. Với FP-Growth, đây là nơi bạn có thể thấy FP-Tree được trực quan hóa.
    - **Tab "Tập Mục Phổ Biến":** Xem danh sách các itemset thường xuyên xuất hiện cùng nhau.
    - **Tab "Luật Kết Hợp":**
      - Phân tích các luật được sinh ra, chú ý đến các chỉ số support, confidence, và lift.
      - **Bảng tóm tắt các luật hàng đầu:** Xem phiên bản Việt hóa và đánh giá trực quan về độ mạnh của các luật quan trọng nhất.
      - **Biểu đồ mạng lưới:** Khám phá mối quan hệ giữa các sản phẩm thông qua biểu đồ tương tác, hiển thị trực quan các luật kết hợp mạnh nhất.

7.  **Thử Nghiệm & So Sánh:**
    - Thay đổi các ngưỡng support và confidence để xem kết quả thay đổi như thế nào.
    - Chạy cả hai ứng dụng Apriori và FP-Growth trên cùng một bộ dữ liệu và tham số để so sánh trực tiếp kết quả và hiệu suất.
8.  **Đặt Lại:** Sử dụng nút "🔄 Đặt lại Tất cả" nếu bạn muốn xóa mọi trạng thái và bắt đầu một phiên phân tích mới.

---

## 🧑‍💻 Tác Giả & Liên Hệ

- **Tác giả:** Nguyễn Thanh Hiếu, 2025
- **Mục đích:** Đồ án học thuật, nghiên cứu và minh họa các thuật toán khai phá dữ liệu trong lĩnh vực phân tích giỏ hàng.

---

Hy vọng bạn tìm thấy dự án này hữu ích và dễ sử dụng! Nếu có bất kỳ câu hỏi, góp ý hoặc phát hiện lỗi, vui lòng tạo một "Issue" trên repository GitHub của dự án.
