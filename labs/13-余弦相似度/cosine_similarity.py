"""手写余弦相似度 — 拆开向量检索的数学黑盒

不调 FAISS、不调 Chroma。纯 NumPy 实现余弦相似度计算。
用自己的 Embedding 向量验证结果。

用法：
    python cosine_similarity.py
"""
import json
import math
import numpy as np
from collections import Counter
from pathlib import Path


def tokenize(text):
    """简单中文分词：2-3 字词组切分"""
    tokens = []
    for i in range(len(text) - 1):
        tokens.append(text[i:i + 2])
        if i < len(text) - 2:
            tokens.append(text[i:i + 3])
    return tokens


def cosine_similarity(vec_a, vec_b):
    """
    两个向量的余弦相似度。

    公式：cos(θ) = (A·B) / (||A|| × ||B||)
    即：点积 除以 模的乘积

    结果范围 -1 到 1：
    -  1：方向完全一致
    -  0：正交（无关）
    - -1：方向完全相反
    """
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def euclidean_distance(vec_a, vec_b):
    """欧氏距离 —— 对比用"""
    return float(np.linalg.norm(np.array(vec_a) - np.array(vec_b)))


def build_vectors(documents):
    """TF-IDF 向量化——和 2.4 实验同样的逻辑"""
    all_tokens = set()
    for doc in documents:
        all_tokens.update(tokenize(doc))
    vocab = sorted(all_tokens)
    N = len(documents)

    idf = {}
    for word in vocab:
        doc_count = sum(1 for doc in documents if word in doc)
        idf[word] = math.log((N + 1) / (doc_count + 1)) + 1

    vectors = []
    for doc in documents:
        tokens = tokenize(doc)
        tf = Counter(tokens)
        vec = np.zeros(len(vocab), dtype="float32")
        for j, word in enumerate(vocab):
            vec[j] = tf.get(word, 0) * idf[word]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        vectors.append(vec)

    return vectors, vocab, idf


def query_to_vector(query, vocab, idf):
    """查询文本 → 向量"""
    tokens = tokenize(query)
    tf = Counter(tokens)
    vec = np.zeros(len(vocab), dtype="float32")
    for j, word in enumerate(vocab):
        vec[j] = tf.get(word, 0) * idf[word]
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


if __name__ == "__main__":
    print("=" * 60)
    print("手写余弦相似度 — 逐步验证")
    print("=" * 60)

    # ── 1. 自己和自己的相似度 ──
    a = np.array([1.0, 2.0, 3.0])
    self_sim = cosine_similarity(a, a)
    print(f"\n1. 同一个向量：cos_sim = {self_sim:.6f}")
    print(f"   预期 ≈ 1.0  ✅" if abs(self_sim - 1.0) < 0.001 else "   ❌")

    # ── 2. 正交向量 ──
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    ortho_sim = cosine_similarity(a, b)
    print(f"\n2. 正交向量：[1,0] vs [0,1]：cos_sim = {ortho_sim:.6f}")
    print(f"   预期 ≈ 0.0  ✅" if abs(ortho_sim) < 0.001 else "   ❌")

    # ── 3. 随机向量（应接近 0）──
    r1 = np.random.randn(100)
    r2 = np.random.randn(100)
    rand_sim = cosine_similarity(r1, r2)
    print(f"\n3. 两个随机 100 维向量：cos_sim = {rand_sim:.6f}")
    print(f"   预期接近 0  (实际 {rand_sim:.4f})")

    # ── 4. 实际案例检索 ──
    print(f"\n{'=' * 60}")
    print("4. 实际案例检索——20 条设备状态描述")
    print("=" * 60)

    # 加载案例（复用 2.4 的数据）
    cases_file = Path(__file__).parent / "data" / "cases.json"
    if not cases_file.exists():
        cases_file = Path(__file__).parent.parent / "18-图片相似度匹配" / "data" / "cases.json"
    if cases_file.exists():
        with open(cases_file, encoding="utf-8") as f:
            cases = json.load(f)
    else:
        cases = [
            "设备正面面板，所有指示灯绿色常亮，运行状态正常，无告警",
            "光纤接口红色告警灯闪烁，光模块疑似故障，需更换",
            "AAU 设备散热片严重积灰，表面温度偏高，需清理",
            "BBU 主控板 RUN 指示灯熄灭，ALM 红灯常亮，单板故障",
            "电源模块 PWR 指示灯绿色，电压输出 53.5V，正常",
        ]

    vectors, vocab, idf = build_vectors(cases)
    print(f"词表: {len(vocab)} 词，案例: {len(cases)} 条")

    # 查询
    queries = ["光纤红灯告警", "设备温度过高", "设备正常运行"]
    for query in queries:
        q_vec = query_to_vector(query, vocab, idf)

        print(f'\n🔍 "{query}"')
        print(f"   查询向量：{len(q_vec)} 维，非零 {(q_vec > 0).sum()} 维")
        print(f"   Top 5 关键词: ", end="")
        top_idx = np.argsort(q_vec)[-5:][::-1]
        top_words = [f"{vocab[i]}({q_vec[i]:.3f})" for i in top_idx if q_vec[i] > 0]
        print(", ".join(top_words[:5]))

        # 逐条计算余弦相似度
        results = []
        for i, vec in enumerate(vectors):
            sim = cosine_similarity(q_vec, vec)
            results.append((i, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        for rank, (idx, sim) in enumerate(results[:3]):
            bar = "█" * int(sim * 30 + 1)
            print(f"   {rank+1}. [{sim:.4f}] {bar}")
            print(f"      {cases[idx][:70]}")

    print(f"\n{'=' * 60}")
    print("完成——这就是 FAISS 底层在算的东西")
    print("=" * 60)
