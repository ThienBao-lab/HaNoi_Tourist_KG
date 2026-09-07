# Pipeline KG Retrieval — Thiết kế mới

## Tổng quan kiến trúc

Cải tiến G-Retriever ở 3 điểm chính:
1. **Triple-level embedding** thay node/edge riêng
2. **GNN trên graph-of-triples** thay graph-of-nodes
3. **Q-Former** thay mean pool + MLP projection

---

## Pipeline 6 bước

```
                    ┌──────────────┐
                    │  Câu hỏi xq  │
                    │  (+ Ảnh)     │
                    └──────┬───────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     ▼                                           ▼
 BƯỚC 1                                      BƯỚC 2
 INDEXING                                    RETRIEVAL
 (offline)                                   (runtime)
     │                                           │
     ▼                                           ▼
 BƯỚC 3: GNN encode triples                     │
     │                                           │
     ▼                                           │
 BƯỚC 4: Fusion (concat + Linear)               │
     │                                           │
     ▼                                           │
 BƯỚC 5: Q-Former                               │
     │                                           │
     ▼                                           │
 BƯỚC 6: LLM (Qwen) ◄───────────────────────────┘
     │
     ▼
 Câu trả lời
```

---

## BƯỚC 1: INDEXING (Offline)

**Khác G-Retriever:** Embed toàn bộ triple, không embed node/edge riêng lẻ.

```
Với mỗi triple (h, r, t) trong KG:

  Triple embedding:
    zt = SentenceBERT("h r t")
    Ví dụ: zt = SentenceBERT("Văn Miếu – Quốc Tử Giám xây_dựng_năm 1070")
    → vector d chiều, chứa ĐẦY ĐỦ ngữ nghĩa: ai + quan hệ gì + với ai

  Node embeddings (cho bước Fusion):
    zn_h = SentenceBERT("h")    ← head entity
    zn_t = SentenceBERT("t")    ← tail entity

  Lưu tất cả vào NetworkX graph
```

**Tại sao không embed node/edge riêng?**
- Edge "xây_dựng_năm" embed riêng → vector không biết "ai xây", "xây cái gì"
- Triple "Văn Miếu xây_dựng_năm 1070" → vector chứa trọn vẹn 1 fact
- Retrieval chính xác hơn khi cosine(query, triple) thay vì cosine(query, node)

---

## BƯỚC 2: RETRIEVAL (Runtime)

**Giữ nguyên** pipeline KGRetriever đã build:

```
Input: câu hỏi (+ ảnh nếu có)

Seed selection (thứ tự ưu tiên):
  1. Keyword match — tìm tên di tích trong câu hỏi
  2. Visual match  — I-JEPA cosine với gallery (khi có ảnh)
  3. Embedding fallback — cosine similarity

PPR (HippoRAG):
  Personalized PageRank từ seed → relevance score cho mọi node

Subgraph extraction:
  Top-k nodes theo PPR score → lấy TẤT CẢ triples có chứa nodes đó
  (Bỏ Ek retrieval riêng — chỉ dùng Vk)

Output: N triples trong subgraph
  Ví dụ cho seed = "Văn Miếu":
    triple₁: (Văn Miếu, xây_dựng_năm, 1070)
    triple₂: (Văn Miếu, triều_đại, Nhà Lý)
    triple₃: (Văn Miếu, thuộc_quận, Quận Đống Đa)
    triple₄: (Văn Miếu, xây_dựng_bởi, Lý Thánh Tông)
    triple₅: (Văn Miếu, đặc_điểm, Khuê Văn Các)
    ...
```

---

## BƯỚC 3: GNN ENCODE TRIPLES

**Khác G-Retriever:** GNN chạy trên graph-of-triples, không phải graph-of-entities.

```
Xây graph-of-triples:
  Nodes:  mỗi triple là 1 node
          Input feature = zt (triple embedding từ bước 1)
  Edges:  nối 2 triple-nodes nếu share entity

  Ví dụ:
    triple₁ (Văn Miếu, xây_dựng_năm, 1070)
    triple₂ (Văn Miếu, triều_đại, Nhà Lý)
    triple₃ (Văn Miếu, thuộc_quận, Đống Đa)
    triple₄ (Nhà Lý, tiếp_nối, Nhà Trần)

    triple₁ ←→ triple₂  (share "Văn Miếu")
    triple₁ ←→ triple₃  (share "Văn Miếu")
    triple₂ ←→ triple₃  (share "Văn Miếu")
    triple₂ ←→ triple₄  (share "Nhà Lý")

GNN (GAT, 2-3 layers):
  Input:  [zt₁, zt₂, ..., ztN]     (N triple embeddings, d chiều)
  Output: [gt₁, gt₂, ..., gtN]     (N enriched vectors, d chiều)

  Sau GNN:
    gt₁ (Văn Miếu xây 1070) bây giờ biết cả triều đại + quận
    gt₂ (Văn Miếu triều Lý) bây giờ biết cả năm xây + quận
    → Inter-fact enrichment qua message passing
```

**Tại sao graph-of-triples chứ không graph-of-entities?**
- G-Retriever: GNN trên entity graph → node "Văn Miếu" nhận message từ "1070", "Nhà Lý"... nhưng relation type bị mất (GNN không biết "1070" là năm xây hay năm trùng tu)
- Graph-of-triples: mỗi node là 1 fact hoàn chỉnh, GNN encode quan hệ GIỮA các facts

---

## BƯỚC 4: FUSION

**Concat head + tail embeddings qua Linear layer.**

```
Với mỗi triple i:
  gtᵢ     = GNN output          (d dim) — triple đã enriched
  zn_hᵢ   = SentenceBERT(head)  (d dim) — anchor head entity
  zn_tᵢ   = SentenceBERT(tail)  (d dim) — anchor tail entity

  Concat:  cᵢ = [gtᵢ ; zn_hᵢ ; zn_tᵢ]   (3d dim)
  Linear:  fᵢ = Linear(cᵢ)               (3d → d)

Output: [f₁, f₂, ..., fN]  (N vectors, d chiều)
```

**Tại sao concat + Linear (không phải cộng)?**
- Phép cộng giả định cùng scale → sai nếu GNN output khác distribution với SentenceBERT
- Linear tự học trọng số: câu hỏi "xây năm nào?" → ưu tiên tail (1070); "ai xây?" → ưu tiên head
- Giữ cả head lẫn tail anchor — triple embedding sau GNN có thể "trôi", node embeddings neo lại

**Params:** Linear(3d → d) = 3d² + d ≈ 443K params (với d=384). Nhỏ.

**Ablation:** So sánh 3 cách
```
Baseline:  fᵢ = gtᵢ + zn_hᵢ                          (0 params)
Proposed:  fᵢ = Linear([gtᵢ ; zn_hᵢ ; zn_tᵢ])        (443K params)
Gated:     α = σ(W[gtᵢ ; zn_hᵢ ; zn_tᵢ])
           fᵢ = α * gtᵢ + (1-α) * (zn_hᵢ + zn_tᵢ)   (linh hoạt nhất)
```

---

## BƯỚC 5: Q-FORMER

**Thay thế mean pool + MLP (1 graph token) bằng multi-token cross-attention.**

```
Input:
  [f₁, f₂, ..., fN]           N enriched triple vectors (d dim)
  [q₁, q₂, ..., qM]           M learnable query tokens (d dim, random init)

Q-Former architecture (2-3 transformer layers):
  Mỗi layer:
    Self-attention:   queries attend lẫn nhau
    Cross-attention:  queries attend vào triple vectors [f₁..fN]
    FFN

Output:
  [q₁', q₂', ..., qM']       M graph tokens (d dim)
  → Mỗi token capture khía cạnh khác nhau của subgraph

  Ví dụ:
    q₁' → focus vào facts thời gian (năm xây, trùng tu)
    q₂' → focus vào facts vị trí (quận, tọa lạc)
    q₃' → focus vào facts kiến trúc (phong cách, đặc điểm)
    q₄' → focus vào facts quan hệ (triều đại, người xây)
```

**Hyperparameters:**
```
M (query tokens):     4-8 (ablation: 2, 4, 8, 16)
Layers:               2-3
Heads:                4-8
d (dimension):        384 (match SentenceBERT)
```

**Tại sao Q-Former?**
- G-Retriever: mean pool → 1 vector → MLP → 1 token. LLM nhận 1 token gánh hết info
- Q-Former: M tokens, mỗi token attend vào subset facts khác nhau
- Consistent với BLIP-2 (vision Q-Former) → cùng kiến trúc, dễ giải thích

---

## BƯỚC 6: LLM GENERATION

```
Input cho Qwen (frozen + LoRA):

  [q₁', q₂', ..., qM']          ← M graph tokens (soft prompt)
  +
  tokenize(textualized subgraph) ← text backup (reasoning paths)
  +
  tokenize(câu hỏi)             ← query

  → Qwen sinh câu trả lời
```

**Tại sao giữ cả graph tokens LẪN textualized subgraph?**
- Graph tokens: compact, structural info qua GNN + Q-Former
- Text: explicit facts mà LLM đọc được trực tiếp
- Ablation: chỉ graph tokens vs chỉ text vs cả hai

---

## So sánh tổng thể

```
                        G-Retriever            Pipeline mới
────────────────────────────────────────────────────────────────
Đơn vị embed            Node + Edge riêng      Triple (h,r,t)
Retrieval               Vk + Ek (cosine)       Vk only (keyword+PPR)
GNN graph structure     Entity graph            Graph-of-triples
GNN encode cái gì       Node embeddings        Triple embeddings
Edge info trong GNN      Qua message passing    Đã có sẵn trong triple
Graph→LLM bridge        Mean pool → MLP        Concat+Linear → Q-Former
LLM nhận                1 graph token           M graph tokens
Fusion                  Không có                Concat(GNN, head, tail) → Linear
Trainable params        MLP + GNN              GNN + Linear + Q-Former
Ablation points         Ít                      Nhiều (fusion type, M, layers)
```

---

## Diagram

```
  KG triples                    Câu hỏi
  (h,r,t)                      xq
      │                          │
      │ SentenceBERT             │ Keyword / PPR
      ▼                          ▼
  ┌────────┐              ┌────────────┐
  │Triple  │              │ Retrieval  │
  │Embed zt│              │ → Subgraph │
  │Node    │              │   N triples│
  │Embed   │              └─────┬──────┘
  │zn_h,   │                    │
  │zn_t    │                    │
  └───┬────┘                    │
      │                         │
      │    ┌────────────────────┘
      │    │
      ▼    ▼
  ┌──────────────────────────────────────┐
  │  BƯỚC 3: GNN (GAT, 2-3 layers)      │
  │                                      │
  │  Graph-of-triples:                   │
  │    Node features = zt (triple embed) │
  │    Edges = share entity              │
  │                                      │
  │  Output: [gt₁, gt₂, ..., gtN]       │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │  BƯỚC 4: FUSION                      │
  │                                      │
  │  fᵢ = Linear([gtᵢ ; zn_hᵢ ; zn_tᵢ])│
  │        (3d → d)                      │
  │                                      │
  │  Output: [f₁, f₂, ..., fN]          │
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │  BƯỚC 5: Q-FORMER                   │
  │                                      │
  │  M learnable queries                 │
  │    × cross-attention                 │
  │    × [f₁, ..., fN]                  │
  │                                      │
  │  Output: [q₁', ..., qM'] graph tokens│
  └──────────────┬───────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────┐
  │  BƯỚC 6: LLM (Qwen, frozen + LoRA)  │
  │                                      │
  │  Input: [graph tokens]               │
  │       + [textualized subgraph]       │
  │       + [câu hỏi]                   │
  │                                      │
  │  → Câu trả lời tiếng Việt           │
  └──────────────────────────────────────┘
```

---

## Contributions so với G-Retriever

1. **Triple-level embedding:** Đơn vị ngữ nghĩa hoàn chỉnh thay node/edge riêng lẻ
2. **Graph-of-triples GNN:** Encode inter-fact relationships, relation type không bị mất
3. **Concat fusion với head+tail anchoring:** Model tự học ưu tiên head/tail tùy context
4. **Q-Former bridge:** Multi-token attention thay 1 pooled token
5. **Vk-only retrieval:** Đơn giản hóa, kết hợp keyword match + PPR (HippoRAG)

## Ablation plan

```
Exp 1: Fusion type     — cộng vs concat+Linear vs gated
Exp 2: Query tokens M  — 2, 4, 8, 16
Exp 3: GNN layers      — 1, 2, 3
Exp 4: GNN cần không   — Q-Former on raw triple embed vs GNN-encoded
Exp 5: Text backup     — graph tokens only vs text only vs cả hai
Exp 6: Node anchoring  — head only vs head+tail vs không anchor
```
