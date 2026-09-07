"""
KGRetriever — Knowledge Graph Retriever cho di tích Hà Nội.

Usage:
    from kg_retriever import KGRetriever

    retriever = KGRetriever("kg/graph.pkl")
    result = retriever.query(question="Văn Miếu xây năm nào?")
    print(result["context"])
"""

import re, pickle
from collections import defaultdict

import numpy as np
import networkx as nx
from sentence_transformers import SentenceTransformer


class KGRetriever:

    def __init__(self, graph_path, encoder_name="paraphrase-multilingual-MiniLM-L12-v2"):
        with open(graph_path, "rb") as f:
            self.G = pickle.load(f)
        self._encoder = None
        self._encoder_name = encoder_name
        self._landmarks = [n for n in self.G if self.G.nodes[n].get("type") == "Landmark"]
        self._restaurants = [n for n in self.G if self.G.nodes[n].get("type") == "Restaurant"]
        self._priority_nodes = self._landmarks + self._restaurants
        self._img_embs = {}
        for nid in self.G.nodes:
            if "image_embedding" in self.G.nodes[nid]:
                self._img_embs[nid] = np.array(self.G.nodes[nid]["image_embedding"])
        self._G_und = self.G.to_undirected()

    @property
    def encoder(self):
        if self._encoder is None:
            self._encoder = SentenceTransformer(self._encoder_name)
        return self._encoder

    def keyword_match(self, question):
        question_lower = question.lower()
        best_node, best_len = None, 0
        for nid in self._priority_nodes:
            nid_lower = nid.lower()
            if nid_lower in question_lower and len(nid) > best_len:
                best_node, best_len = nid, len(nid)
            name_parts = re.split(r"\s*[–\-]\s*", nid)
            for part in name_parts:
                part = part.strip()
                if len(part) >= 3 and part.lower() in question_lower and len(part) > best_len:
                    best_node, best_len = nid, len(part)
            for alias in self.G.nodes[nid].get("aliases", []):
                if len(alias) >= 3 and alias.lower() in question_lower and len(alias) > best_len:
                    best_node, best_len = nid, len(alias)
        return best_node, best_len

    def embedding_match(self, question, top_k=1):
        q_emb = self.encoder.encode(question)
        scores = {}
        for nid in self._priority_nodes:
            if "text_embedding" in self.G.nodes[nid]:
                emb = np.array(self.G.nodes[nid]["text_embedding"])
                cos = float(np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb) + 1e-8))
                scores[nid] = cos
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    def visual_match(self, image_embedding, top_k=3):
        if not self._img_embs:
            return []
        scores = {}
        for nid, emb in self._img_embs.items():
            cos = float(np.dot(image_embedding, emb) / (np.linalg.norm(image_embedding) * np.linalg.norm(emb) + 1e-8))
            scores[nid] = cos
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    def find_seed(self, question=None, image_embedding=None, confidence_threshold=0.3):
        if question:
            node, match_len = self.keyword_match(question)
            if node:
                return node, min(match_len / 10.0, 1.0), "keyword"
        if image_embedding is not None:
            results = self.visual_match(image_embedding)
            if results and results[0][1] >= confidence_threshold:
                return results[0][0], results[0][1], "visual"
        if question:
            results = self.embedding_match(question)
            if results:
                return results[0][0], results[0][1], "embedding"
        return None, 0.0, "none"

    def personalized_pagerank(self, seeds, alpha=0.15, top_n=20):
        valid = [s for s in seeds if s in self._G_und]
        if not valid:
            return []
        pers = {s: 1.0 / len(valid) for s in valid}
        try:
            ppr = nx.pagerank(self._G_und, alpha=alpha, personalization=pers, max_iter=100)
        except:
            ppr = pers
        return sorted(ppr.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def extract_paths(self, seed, targets, max_hops=2):
        triples, seen = [], set()
        for target in targets:
            if target == seed:
                continue
            try:
                for path in nx.all_simple_paths(self._G_und, seed, target, cutoff=max_hops):
                    for i in range(len(path) - 1):
                        s, d = path[i], path[i + 1]
                        edge = self.G.get_edge_data(s, d)
                        if edge:
                            rel, src, dst = edge.get("relation", "liên_quan"), s, d
                        else:
                            edge = self.G.get_edge_data(d, s)
                            rel = edge.get("relation", "liên_quan") if edge else "liên_quan"
                            src, dst = d, s
                        key = (src, rel, dst)
                        if key not in seen:
                            triples.append((src, rel, dst))
                            seen.add(key)
            except:
                continue
        return triples

    def textualize(self, entity, triples, max_lines=15):
        lines = []
        desc = self.G.nodes.get(entity, {})
        etype = desc.get("type", "")
        if etype:
            lines.append(f"[{etype}] {entity}")
        for key in ("xây_dựng_năm", "thuộc_quận", "triều_đại", "phong_cách_kiến_trúc", "loại_món", "tôn_giáo"):
            val = desc.get(key)
            if val:
                lines.append(f"  {key}: {val}")
        lines.append("")
        for src, rel, dst in triples[:max_lines]:
            lines.append(f"  {src} → [{rel}] → {dst}")
        return "
".join(lines)

    def query(self, question=None, image_embedding=None, top_n_ppr=15, max_hops=2, confidence_threshold=0.3):
        entity, confidence, method = self.find_seed(question=question, image_embedding=image_embedding, confidence_threshold=confidence_threshold)
        if entity is None:
            return {"entity": None, "confidence": 0.0, "method": "none", "context": "Không nhận diện được di tích.", "triples": [], "ppr_scores": []}
        ppr_results = self.personalized_pagerank([entity], top_n=top_n_ppr)
        ppr_nodes = [n for n, _ in ppr_results]
        triples = self.extract_paths(entity, ppr_nodes, max_hops=max_hops)
        context = self.textualize(entity, triples)
        return {"entity": entity, "confidence": confidence, "method": method, "context": context, "triples": triples, "ppr_scores": ppr_results[:10]}

    def get_entity_info(self, entity):
        if entity not in self.G:
            return {}
        attrs = dict(self.G.nodes[entity])
        attrs.pop("text_embedding", None)
        attrs.pop("image_embedding", None)
        edges_out = [(entity, d, self.G.edges[entity, d].get("relation", "?")) for d in self.G.successors(entity)]
        edges_in = [(s, entity, self.G.edges[s, entity].get("relation", "?")) for s in self.G.predecessors(entity)]
        return {"attrs": attrs, "edges_out": edges_out, "edges_in": edges_in}

    def list_landmarks(self):
        return sorted(self._landmarks)

    def list_restaurants(self):
        return sorted(self._restaurants)

    def stats(self):
        print(f"Nodes: {self.G.number_of_nodes()}, Edges: {self.G.number_of_edges()}")
        print(f"Landmarks: {len(self._landmarks)}, Restaurants: {len(self._restaurants)}")
        print(f"Image embeddings: {len(self._img_embs)}")
