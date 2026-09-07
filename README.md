# 🏛️ Hanoi Tourism Knowledge Graph

Knowledge Graph về di tích lịch sử và ẩm thực Hà Nội, phục vụ hệ thống hỏi đáp du lịch VLM (I-JEPA + Qwen) trong kiến trúc late fusion.

## Quick Start

```python
from kg_retriever import KGRetriever

retriever = KGRetriever("models/graph.pkl")
result = retriever.query(question="Văn Miếu xây dựng năm nào?")
print(result["context"])
```

## KG Stats

| Metric | Giá trị |
|--------|---------|
| Nodes | ~2000+ |
| Edges | ~2400+ |
| Landmarks | ~90 di tích |
| Restaurants | 20 quán ăn |
| Dishes | 17 loại món |
| Districts | 16 quận/huyện |
| Test queries | 8/8 seed đúng |

## Pipeline

| Bước | Script / Notebook | Mô tả | GPU |
|------|-------------------|-------|-----|
| 1a | `kg_scrape.py scrape-landmarks` | Cào Wikipedia tiếng Việt (91 bài) | ❌ |
| 1b | `kg_scrape.py scrape-food` | Curate ẩm thực (20 quán + 17 món) | ❌ |
| 2 | `notebooks/kg_step2.ipynb` | Extract triplets bằng Qwen3-8B | ✅ |
| 2.5 | `notebooks/kg_step2.ipynb` | Normalize + Markdown (human review) | ❌ |
| 3 | `notebooks/kg_step3_v2.ipynb` | Build graph + text embeddings | ❌ |
| 4 | `notebooks/kg_step4.ipynb` | KGRetriever module + test | ❌ |

## Cấu trúc repo

```
HaNoi_Tourist_KG/
├── kg_scrape.py              # Bước 1: scrape Wikipedia + curate food
├── kg_retriever.py           # Module chính (import được)
├── models/
│   └── graph.pkl             # NetworkX graph + embeddings
├── notebooks/
│   ├── kg_step2.ipynb        # Extract triplets (Qwen3-8B)
│   ├── kg_step3_v2.ipynb     # Build graph
│   └── kg_step4.ipynb        # KGRetriever + test
├── data/
│   └── kg_markdown/          # Source of truth (human-reviewable)
│       ├── landmarks/        # ~90 di tích
│       ├── food/             # 20 quán ăn
│       ├── dishes/           # 17 loại món
│       └── locations/        # 16 quận/huyện
├── docs/
│   ├── kg_report.md          # Báo cáo tiến độ
│   └── pipeline_design_v2.md # Thiết kế pipeline mới
├── requirements.txt
└── .gitignore
```

## Reproduce

```bash
# Bước 1: Scrape data
python kg_scrape.py scrape-landmarks --out data/wiki_raw/
python kg_scrape.py scrape-food --out data/food_raw/

# Bước 2-4: Chạy notebooks trên Kaggle (bước 2 cần GPU)
```

## Công nghệ

| Thành phần | Công nghệ |
|-----------|-----------|
| Extract triplets | Qwen3-8B (bfloat16) |
| Text embeddings | paraphrase-multilingual-MiniLM-L12-v2 |
| Graph storage | NetworkX + pickle |
| Retrieval | Keyword match + Personalized PageRank |
| Data format | Markdown (source of truth) |

## Bài báo tham khảo

- **G-Retriever** (He et al., NeurIPS 2024) — Textual graph indexing, PCST
- **HippoRAG** (Gutiérrez et al., NeurIPS 2024) — Personalized PageRank retrieval
- **RoG** (Luo et al., NeurIPS 2024) — Reasoning paths textualization
- **GNN-RAG** (Mavromatis & Karypis, ACL Findings 2025) — Trainable GNN retriever
- **GRAG** (Hu et al., NAACL Findings 2025) — Dual textual + topological view

## License

MIT
