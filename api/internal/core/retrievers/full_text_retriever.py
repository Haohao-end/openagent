from collections import Counter
from typing import List
from uuid import UUID
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from pydantic import Field
from langchain_core.retrievers import BaseRetriever
from internal.model import KeywordTable, Segment
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
        top_k_ids = id_counter.most_common(k)

        # 8.根据得到的id列表检索数据库得到片段列表信息
        segments = self.db.session.query(Segment).filter(
            Segment.id.in_([id for id, _ in top_k_ids])
        ).all()
        segment_dict = {
            str(segment.id): segment for segment in segments
        }

        # 9.根据频率进行排序
        sorted_segments = [segment_dict[str(id)] for id, freq in top_k_ids if id in segment_dict]

        # 10.构建LangChain文档列表
        lc_documents = [LCDocument(
            page_content=segment.content,
            metadata={
                "account_id": str(segment.account_id),
                "dataset_id": str(segment.dataset_id),
                "document_id": str(segment.document_id),
                "segment_id": str(segment.id),
                "node_id": str(segment.node_id),
                "document_enabled": True,
                "segment_enabled": True,
                "score": 0,
            }
        ) for segment in sorted_segments]

        return lc_documents
