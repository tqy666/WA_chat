import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import bm25s
import jieba
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_ollama import OllamaEmbeddings
from app.config.Setting import Settings, get_llm
from langchain.messages import AIMessage
from langchain_chroma import Chroma
import time

load_dotenv()


TOP_K = 3
RRF_K = 60
BM25_K1 = 1.5
BM25_B = 0.75

SYSTEM_PROMPT = (
    "你是一个WhatsApp跨境电商客服助手。"
    "用户会在WhatsApp上询问商品信息，例如：Robot Vacuum Cleaner, Outdoor Power Station, Sports Watch, Mechanical Keyboard等。"
    "当用户询问商品时，你必须先调用 search_knowledge_base 工具检索相关信息。"
    "回复规则（严格遵守）："
    "1. 只用用户使用的语言回复（用户用英文你用英文，用中文你用中文）"
    "2. 每个商品只输出：商品名称、价格、商品链接，用换行分隔"
    "3. 不要输出段落、描述、总结、分析等长文本"
    "4. 不要输出与商品无关的内容"
    "5. 最多推荐3个最相关的商品"
    "6. 如果没有找到相关商品，简短告知即可"
)


class RagServerTool:
    def __init__(self):
        self.collection_name = "openwa_webhook"
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.persist_dir = Path(__file__).resolve().parent.parent / "chroma_dir"
        self.vector_db = Chroma(
            persist_directory=str(self.persist_dir),
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
        )
        self.llm = get_llm()
        self.agent = None
        self.search_tool = self._create_search_tool()
        # BM25 in-memory cache
        self._bm25_retriever: Optional[bm25s.BM25] = None
        self._bm25_corpus_count: int = 0

    async def _ensure_agent(self):
        """懒加载 Agent"""
        if self.agent is not None:
            return self.agent
        self.agent = create_agent(
            model=self.llm,
            tools=[self.search_tool],
            system_prompt=SYSTEM_PROMPT,
        )

    def _create_search_tool(self):
        server = self

        @tool
        def search_knowledge_base(query: str) -> str:
            """搜索知识库，获取跨境电商相关文档"""
            return server.search_knowledge_base(query)

        return search_knowledge_base

    # ------------------------------------------------------------------
    # BM25 索引管理：从全量 Chroma 语料构建，内存缓存，文档数变化时自动重建
    # ------------------------------------------------------------------

    def _load_full_corpus(self) -> List[Dict]:
        """从 Chroma 向量库提取全部文档，构建 BM25 语料。"""
        collection = self.vector_db._collection
        count = collection.count()
        if count == 0:
            return []
        data = collection.get(include=["documents"])
        corpus = []
        for doc_id, text in zip(data["ids"], data["documents"]):
            if text:
                corpus.append({"id": doc_id, "content": text})
        return corpus

    def _ensure_bm25_index(self):
        """懒加载 BM25：仅在首次调用或文档数变化时重建（内存缓存）。"""
        current_count = self.vector_db._collection.count()
        if self._bm25_retriever is not None and self._bm25_corpus_count == current_count:
            return

        corpus = self._load_full_corpus()
        if not corpus:
            self._bm25_retriever = None
            self._bm25_corpus_count = 0
            return

        t0 = time.perf_counter()
        corpus_tokens = [jieba.lcut(doc["content"]) for doc in corpus]
        retriever = bm25s.BM25(k1=BM25_K1, b=BM25_B, corpus=corpus)
        retriever.index(corpus_tokens)
        self._bm25_retriever = retriever
        self._bm25_corpus_count = current_count
        print(f"BM25 索引已构建，共 {len(corpus)} 条文档，耗时 {(time.perf_counter() - t0) * 1000:.2f}ms")

    def bm25_search(self, query: str, k: int = TOP_K) -> List[Tuple[Dict, float]]:
        """BM25 检索：从全量语料中召回。"""
        self._ensure_bm25_index()
        if self._bm25_retriever is None:
            return []
        query_tokens = jieba.lcut(query)
        results, scores = self._bm25_retriever.retrieve([query_tokens], k=k)
        if results.size == 0:
            return []
        return [(results[0, i], scores[0, i]) for i in range(results.shape[1])]

    def reciprocal_rank_fusion(self, ranked_lists: List[List[Dict]], k: int = RRF_K) -> List[Dict]:
        """
        RRF 融合算法
        ranked_lists: 多个检索器返回的文档列表，每个文档需包含 'id' 字段
        """
        rrf_scores = {}
        doc_map = {}

        for rank_list in ranked_lists:
            for rank, doc in enumerate(rank_list, start=1):
                doc_id = doc["id"]
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
                doc_map[doc_id] = doc

        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_map[doc_id] for doc_id, _ in sorted_docs]

    def search_knowledge_base(self, query: str) -> str:
        """主搜索流程：向量检索 -> BM25检索 -> RRF融合 -> 返回文本"""
        start = time.perf_counter()

        # 1. 稠密检索（向量）
        vector_results = self.vector_db.similarity_search(query, k=TOP_K)
        print(f"向量检索耗时: {(time.perf_counter() - start) * 1000:.2f}ms")

        if not vector_results:
            return "未在向量库中找到相关文档"

        # 统一向量结果格式
        vector_docs = [{"id": doc.id, "content": doc.page_content} for doc in vector_results]

        # 2. 稀疏检索（BM25，从全量语料中召回）
        bm25_raw_results = self.bm25_search(query, k=TOP_K)
        print(f"BM25检索耗时: {(time.perf_counter() - start) * 1000:.2f}ms")

        # 3. RRF 融合
        bm25_docs = [doc for doc, _ in bm25_raw_results]
        final_docs = self.reciprocal_rank_fusion([vector_docs, bm25_docs])
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"RRF 融合完成，共 {len(final_docs)} 篇文档，累计耗时: {elapsed_ms:.2f}ms")

        # 4. 取融合后前 TOP_K 篇文档拼接为上下文
        context_docs = final_docs[:TOP_K]
        docs_content = "\n\n---\n\n".join([f"文档 {i + 1}:\n{doc['content']}" for i, doc in enumerate(context_docs)])
        if not docs_content.strip():
            return "未找到相关文档"

        return docs_content

    async def getKnowledge(self, query):
        await self._ensure_agent()
        final_content = ""
        try:
            async for chunk, metadata in self.agent.astream(
                    {"messages": [{"role": "user", "content": query}]},
                    stream_mode="messages",
            ):
                if isinstance(chunk, AIMessage) and chunk.content:
                    final_content += str(chunk.content)
        except Exception as exc:
            return f"搜索出错: {str(exc)}"
        return final_content


if __name__ == "__main__":
    import asyncio

    server = RagServerTool()
    query = "Outdoor Power Station"
    result = asyncio.run(server.getKnowledge(query))
    print(result)
