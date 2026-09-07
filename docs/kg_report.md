---
title: Báo cáo tiến độ — Knowledge Graph cho hệ thống VLM du lịch Hà Nội
date: 09/2026
author: Thiên Bảo
---

# Báo cáo tiến độ: Xây dựng Knowledge Graph cho hệ thống hỏi đáp du lịch Hà Nội

## 1. Ý tưởng cốt lõi

### 1.1 Bài toán

Xây dựng hệ thống hỏi đáp du lịch Hà Nội, cho phép du khách chụp ảnh di tích và đặt câu hỏi bằng tiếng Việt. Hệ thống trả lời chính xác dựa trên hai nguồn thông tin:

- **VLM (Vision-Language Model):** I-JEPA + Qwen — đọc hiểu hình ảnh, mô tả kiến trúc, đặc điểm thị giác.
- **Knowledge Graph:** Cơ sở dữ liệu tri thức lịch sử Hà Nội — cung cấp facts cứng (năm xây dựng, triều đại, tên gọi...) đảm bảo chính xác 100%.

### 1.2 Tại sao cần Knowledge Graph

VLM thuần túy dễ bị hallucination khi trả lời facts lịch sử — không model nào nhìn ảnh Văn Miếu mà suy ra được năm 1070. KG đóng vai trò nguồn tri thức đáng tin cậy, được truy vấn và đưa vào prompt để ground câu trả lời của LLM.

### 1.3 Kiến trúc Late Fusion

Sau khi phân tích các phương pháp, chọn kiến trúc **late fusion** thay vì early injection:

- **Nhánh VLM:** I-JEPA + Qwen sinh câu trả lời dựa trên visual understanding (chạy độc lập).
- **Nhánh KG:** Truy vấn Knowledge Graph lấy facts chính xác.
- **Merge:** Qwen kết hợp hai nguồn thông tin qua prompt, ưu tiên KG cho facts cứng, VLM cho mô tả thị giác.

Lý do chọn late fusion: tránh hiện tượng shortcut learning — nếu chèn KG quá sớm, VLM sẽ lười học visual features vì đáp án đã có sẵn trong text KG.


## 2. Cơ sở lý thuyết — Các bài báo tham khảo

### 2.1 G-Retriever (He et al., NeurIPS 2024)

- **Đóng góp lấy:** Format textual graph (node/edge đều có text attributes), indexing bằng SentenceBERT, thuật toán Prize-Collecting Steiner Tree (PCST) cho subgraph extraction.
- **Hạn chế đã phân tích:** Retrieval tĩnh (cosine similarity + top-k), không trainable; chỉ 1 graph token cho LLM; PCST phụ thuộc hyperparameter thủ công; chỉ test trên single-domain benchmarks.
- **Áp dụng:** Sử dụng format indexing và text embedding cho KG; PCST được giữ lại cho khả năng mở rộng cross-domain (ẩm thực) trong tương lai.

### 2.2 HippoRAG (Gutiérrez et al., NeurIPS 2024)

- **Đóng góp lấy:** Personalized PageRank (PPR) từ seed nodes — relevance lan truyền qua cấu trúc graph thay vì chỉ dựa vào cosine similarity độc lập.
- **Ưu điểm so với G-Retriever:** Bridge nodes (ví dụ: tên quận nối di tích với quán ăn) tự động nhận relevance score cao nhờ PPR, không bị bỏ sót như cosine similarity.
- **Áp dụng:** PPR là phương pháp chính cho relevance scoring trong KGRetriever.

### 2.3 RoG — Reasoning on Graphs (Luo et al., NeurIPS 2024)

- **Đóng góp lấy:** Textualize subgraph thành reasoning paths thay vì flat CSV. LLM đọc paths tường minh hơn, giảm hallucination.
- **Áp dụng:** Output của KGRetriever là reasoning paths dạng "A → [relation] → B", không phải danh sách node/edge phẳng.

### 2.4 Các bài báo khác đã phân tích

- **GNN-RAG (ACL Findings 2025):** Trainable GNN retriever — hướng cải tiến tương lai.
- **GFM-RAG (NeurIPS 2025):** Graph foundation model, generalize cross-dataset.
- **GRAG (NAACL Findings 2025):** Dual textual + topological view.
- **Microsoft GraphRAG:** Community-level summarization cho corpus lớn.

### 2.5 Đóng góp riêng

- **Keyword-first seed selection:** Tìm entity bằng substring matching trước, embedding similarity chỉ là fallback. Giải quyết vấn đề SentenceBERT match sai entity khi câu hỏi chứa nhiều từ ngữ lịch sử.
- **Adaptive Router (thiết kế cho mở rộng):** Khi thêm domain ẩm thực, Router tự động chọn k-hop filter (single-domain) hoặc PCST (cross-domain) dựa trên phân bố domain của top PPR nodes.


## 3. Công nghệ sử dụng

### 3.1 Mô hình AI

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Trích xuất triplets | Qwen3-8B (bfloat16) | Extract (head, relation, tail) từ bài Wikipedia |
| Text embeddings | paraphrase-multilingual-MiniLM-L12-v2 | Encode node/edge thành vectors, hỗ trợ tiếng Việt |
| Visual encoder (VLM) | I-JEPA ViT-H/14 | Encode ảnh di tích (chưa tích hợp, bước tiếp theo) |
| Language model (VLM) | Qwen | Sinh câu trả lời + merge context (chưa tích hợp) |

### 3.2 Công cụ và thư viện

| Công cụ | Vai trò |
|---|---|
| NetworkX | Lưu trữ và truy vấn đồ thị (PPR, path finding, subgraph) |
| SentenceTransformers | Encode text embeddings multilingual |
| Wikipedia API | Nguồn dữ liệu di tích (plain text extraction) |
| PyYAML | Parse Markdown frontmatter |
| Kaggle (T4 GPU) | Môi trường chạy Qwen3-8B |

### 3.3 Lưu trữ dữ liệu

- **Source of truth:** Markdown files (human-readable, git-trackable, dễ review/sửa).
- **Runtime:** NetworkX graph serialized bằng pickle (graph.pkl).
- **Embeddings:** Lưu trực tiếp trong node/edge attributes của NetworkX.


## 4. Pipeline thực hiện

### 4.1 Tổng quan

```
Bước 1a: Scrape Wikipedia      → wiki_raw/ (JSON)
Bước 1b: Curate ẩm thực        → food_raw/ (JSON)
Bước 2:  Extract triplets       → triplets_raw/ (JSON)
Bước 2.5: Normalize + Markdown  → kg_markdown/ (MD)
          → Human review
Bước 3:  Build Graph            → kg/graph.pkl
Bước 4:  KGRetriever module     → kg_retriever.py
```

### 4.2 Chi tiết từng bước

**Bước 1a — Cào Wikipedia (scrape_wiki)**
- Nguồn: Wikipedia tiếng Việt, 11 categories + 32 bài chỉ định thủ công.
- Filter: Chỉ giữ bài liên quan Hà Nội (keyword matching).
- Kết quả: 91 bài viết.
- Rate limit: 0.5s/bài, tổng ~5-10 phút.

**Bước 1b — Dữ liệu ẩm thực (curate thủ công)**
- Nguồn: CSV curate thủ công, không dùng LLM extract (đảm bảo chính xác).
- Kết quả: 20 quán ăn nổi tiếng, 17 loại món, 16 quận/huyện.
- Mỗi quán có: loại món, địa chỉ, giá, giờ mở cửa, nổi tiếng vì, di tích gần nhất + khoảng cách.

**Bước 2 — Trích xuất triplets (Qwen3-8B)**
- Model: Qwen3-8B, bfloat16 trên Kaggle T4.
- Prompt: Few-shot với ví dụ Chùa Một Cột, danh sách relation chuẩn.
- Post-processing: Normalize relation (gom ~500 biến thể về ~20 relation chuẩn), normalize entity (thống nhất tên triều đại, địa danh), validate (loại triplet vô nghĩa, quá dài, trùng lặp).
- Kết quả: 3174 raw triplets → 2366 sau normalize (tỉ lệ giữ 74.5%).
- Thời gian: ~2 tiếng (với thinking mode bật).

**Bước 2.5 — Markdown + Human review**
- Gộp triplets theo head entity → 1 file Markdown/entity.
- Format: YAML frontmatter (name, type, aliases, key attributes) + Relations section.
- Phân loại tự động: landmarks/, food/, dishes/, locations/.

**Bước 3 — Build Graph**
- Parse Markdown → NetworkX DiGraph.
- Entity resolution qua alias mapping.
- Merge fragmented nodes (SequenceMatcher, threshold 0.75): 65 → 28 connected components.
- Encode text embeddings: multilingual SentenceBERT cho tất cả nodes + edges.
- Output: graph.pkl.

**Bước 4 — KGRetriever module**
- Class Python, import được từ bất kỳ pipeline nào.
- Seed selection: keyword match → visual match (I-JEPA, khi có gallery) → embedding fallback.
- Retrieval: Personalized PageRank từ seed → extract reasoning paths → textualize.
- Output: dict chứa entity, confidence, method, context text, triples, PPR scores.


## 5. Kết quả đạt được

### 5.1 Quy mô Knowledge Graph

| Metric | Giá trị |
|---|---|
| Tổng nodes | ~2000+ |
| Tổng edges | ~2400+ |
| Landmarks | ~90 di tích |
| Restaurants | 20 quán ăn |
| Dishes | 17 loại món |
| Districts (bridge nodes) | 16 quận/huyện |
| Node types | Landmark, Restaurant, Dish, Location, Person, Dynasty, Year, Style, Entity, Alias |
| Relation types | ~20 loại chuẩn hóa |
| Connected components | 28 (largest: ~2060 nodes) |

### 5.2 Kết quả test query (8/8 seed đúng)

| Câu hỏi | Seed | Method | Kết quả chính |
|---|---|---|---|
| Văn Miếu xây dựng năm nào? | Văn Miếu – Quốc Tử Giám | keyword | xây_dựng_năm: 1070, triều_đại: Nhà Lý |
| Chùa Một Cột ở quận nào? | Chùa Một Cột | keyword | tọa_lạc: Hà Nội/Thăng Long (qua Chùa Diên Hựu) |
| Quán phở nào gần Hồ Hoàn Kiếm? | Hồ Hoàn Kiếm | keyword | Tìm được các phố xung quanh, chưa kết nối trực tiếp quán phở |
| Nhà hát Lớn do ai thiết kế? | Nhà hát Lớn Hà Nội | keyword | xây_dựng_bởi: người Pháp, năm 1901 |
| Cầu Long Biên xây năm nào? | Cầu Long Biên | keyword | 1898-1902, Daydé & Pillé, lịch sử chi tiết |
| Chùa Trấn Quốc triều đại nào? | Chùa Trấn Quốc | keyword | Lý Nam Đế (541-547), Bánh Tôm Hồ Tây gần |
| Nhà tù Hỏa Lò tên khác là gì? | Nhà tù Hỏa Lò | keyword | 1896, thực dân Pháp, sự kiện lịch sử đầy đủ |
| Đền Ngọc Sơn thờ ai? | Đền Ngọc Sơn | keyword | Có quán ăn gần (Cà Phê Giảng, Bánh Mì 25, Xôi Yến) |

### 5.3 Late fusion prompt (mô phỏng)

KGRetriever sinh context text ~300-500 tokens, đủ nhỏ để nhét vào prompt Qwen mà không tốn nhiều context window. Format reasoning paths giúp LLM dễ trích xuất thông tin hơn flat CSV.


## 6. Hạn chế hiện tại

1. **Một số di tích quan trọng bị thiếu** trong bước scrape (Văn Miếu ban đầu bị miss do tên Wikipedia dùng en-dash). Đã bổ sung thủ công, cần check thêm.

2. **Quán phở chưa kết nối trực tiếp với Hồ Hoàn Kiếm qua PPR** — food nodes và landmark nodes nằm ở vùng graph khác nhau, cần cải thiện bridge connections.

3. **Chưa có image gallery** cho visual matching — seed selection hiện chỉ dùng keyword + embedding, chưa dùng I-JEPA.

4. **Graph fragmented** (28 components) — có 26 components nhỏ (<5 nodes) bị rời, cần cải thiện entity resolution.

5. **Chưa tích hợp vào VLM pipeline** — KGRetriever module sẵn sàng nhưng chưa kết nối với I-JEPA + Qwen inference.


## 7. Kế hoạch tiếp theo

### Ngắn hạn
- Bổ sung di tích thiếu + cải thiện entity resolution.
- Thu thập image gallery (10-20 ảnh/di tích) cho visual matching.
- Tích hợp KGRetriever vào VLM pipeline (late fusion).
- Đánh giá end-to-end trên bộ test câu hỏi.

### Trung hạn
- Mở rộng KG thêm layer ẩm thực đầy đủ hơn.
- Implement Adaptive Router cho cross-domain queries.
- Cải thiện food-landmark connectivity.

### Dài hạn
- Trainable retriever (GNN-RAG style) thay thế cosine + PPR tĩnh.
- Multi-turn conversation (hệ thống gợi ý chủ động).
- Đánh giá so sánh với baseline VLM thuần (đo mức giảm hallucination).


## 8. Deliverables hiện tại

| File | Mô tả |
|---|---|
| `kg_retriever.py` | Module Python, import được, chứa class KGRetriever |
| `graph.pkl` | NetworkX graph với text embeddings (~2000+ nodes) |
| `kg_markdown/` | Markdown files cho human review (landmarks, food, dishes, locations) |
| `kg_scrape.py` | Script bước 1 (scrape Wikipedia + food) |
| `kg_extract.py` | Script bước 2 (extract triplets + normalize) |
| Notebooks (Kaggle) | kg_step2.ipynb, kg_step3_v2.ipynb, kg_step4.ipynb |
