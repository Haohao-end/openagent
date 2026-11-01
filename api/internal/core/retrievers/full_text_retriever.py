from collections import Counter
from typing import List
from uuid import UUID
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from pydantic import Field
from langchain_core.retrievers import BaseRetriever
from internal.entity.dataset_entity import DocumentStatus, SegmentStatus
from internal.model import Document, KeywordTable, Segment
from internal.service import JiebaService
from pkg.sqlalchemy import SQLAlchemy


class FullTextRetriever(BaseRetriever):
    """全文检索器"""
    db: SQLAlchemy
    dataset_ids: list[UUID]
    jieba_service: JiebaService
    search_kwargs: dict = Field(default_factory=dict)

    def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun,
    ) -> List[LCDocument]:
        """根据传递的query执行关键词检索获取LangChain文档列表"""
        # 1.将查询query转换成关键词列表
        keywords = self.jieba_service.extract_keywords(query, 10)

        # 2.查找指定知识库的关键词表
        keyword_tables = [
            keyword_table for keyword_table, in
            self.db.session.query(KeywordTable).with_entities(KeywordTable.keyword_table).filter(
                KeywordTable.dataset_id.in_(self.dataset_ids)
            ).all()
        ]

        # 3.遍历所有的知识库关键词表，找到匹配query关键词的id列表
        all_ids = []
        for keyword_table in keyword_tables:
            # 4.遍历每一个关键词表的每一项
            for keyword, segment_ids in keyword_table.items():
                # 5.如果数据存在则提取关键词对应的片段id列表
                if keyword in keywords:
                    all_ids.extend(segment_ids)

        # 6.统计segment_id出现的频率，这里可以使用Counter进行快速统计
        id_counter = Counter(all_ids)

        # 7.获取频率最高的前k条数据，格式为[(segment_id, freq), (segment_id, freq), ...]
        k = self.search_kwargs.get("k", 4)
        if k <= 0:
            return []
        ranked_ids = id_counter.most_common()
        batch_size = max(k, 100)
        document_dict = {}
        segment_dict = {}
        for offset in range(0, len(ranked_ids), batch_size):
            batch_ids = ranked_ids[offset:offset + batch_size]
            segments = self.db.session.query(Segment).filter(
                Segment.id.in_([segment_id for segment_id, _ in batch_ids]),
                Segment.dataset_id.in_(self.dataset_ids),
            ).all()
            document_dict.update({
                str(document.id): document
                for document in self.db.session.query(Document).filter(
                    Document.id.in_([segment.document_id for segment in segments])
                ).all()
            })
            segment_dict.update({
                str(segment.id): segment for segment in segments
                if segment.enabled
                and segment.status == SegmentStatus.COMPLETED.value
                and (document := document_dict.get(str(segment.document_id)))
                and document.enabled
                and document.status == DocumentStatus.COMPLETED.value
            })
            if len(segment_dict) >= k:
                break

        # 9.根据频率进行排序
        sorted_segments = [
            segment_dict[str(segment_id)] for segment_id, _ in ranked_ids
            if str(segment_id) in segment_dict
        ][:k]

        # 10.构建LangChain文档列表
        lc_documents = [LCDocument(
            page_content=segment.content,
            metadata={
                "account_id": str(segment.account_id),
                "dataset_id": str(segment.dataset_id),
                "document_id": str(segment.document_id),
                "segment_id": str(segment.id),
                "node_id": str(segment.node_id),
                "document_enabled": document_dict[str(segment.document_id)].enabled,
                "segment_enabled": segment.enabled,
                "score": 0,
            }
        ) for segment in sorted_segments]

        return lc_documents
