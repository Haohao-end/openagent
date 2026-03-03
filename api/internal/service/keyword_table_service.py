from dataclasses import dataclass
from uuid import UUID
from injector import inject
from redis import Redis
from internal.entity.cache_entity import (
    LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE,
    LOCK_EXPIRE_TIME,
)
from internal.model import Segment, KeywordTable
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class KeywordTableService(BaseService):
    """知识库关键词表服务"""
    db: SQLAlchemy
    redis_client: Redis

    def get_keyword_table_from_dataset_id(self, dataset_id: UUID) -> KeywordTable:
        """根据传递的知识库id获取关键词表"""
        keyword_table = self.db.session.query(KeywordTable).filter(
            KeywordTable.dataset_id == dataset_id,
        ).one_or_none()
        if keyword_table is None:
            keyword_table = self.create(KeywordTable, dataset_id=dataset_id, keyword_table={})

        return keyword_table

    def delete_keyword_table_from_ids(self, dataset_id: UUID, segment_ids: list[UUID]) -> None:
        """根据传递的知识库id+片段id列表删除对应关键词表中多余的数据"""
        # 1.删除知识库关键词表里多余的数据，该操作需要上锁，避免在并发的情况下拿到错误的数据
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            # 2.获取当前知识库的关键词表
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)
            keyword_table = keyword_table_record.keyword_table.copy()

            # 3.将片段id列表转换成集合，并创建关键词集合用于清除空关键词
            segment_ids_to_delete = set([str(segment_id) for segment_id in segment_ids])
            keywords_to_delete = set()

            # 4.循环遍历所有关键词执行判断与更新
            for keyword, ids in keyword_table.items():
                ids_set = set(ids)
                if segment_ids_to_delete.intersection(ids_set):
                    keyword_table[keyword] = list(ids_set.difference(segment_ids_to_delete))
                    if not keyword_table[keyword]:
                        keywords_to_delete.add(keyword)

            # 5.检测空关键词数据并删除（关键词并没有映射任何字段id的数据）
            for keyword in keywords_to_delete:
                del keyword_table[keyword]

            # 6.将数据更新到关键词表中
            self.update(keyword_table_record, keyword_table=keyword_table)

    def add_keyword_table_from_ids(self, dataset_id: UUID, segment_ids: list[UUID]) -> None:
        """根据传递的知识库id + 片段id列表，在关键词表中添加关键词"""
        # 1.新增知识库关键词表里多余的数据，该操作需要上锁，避免在并发的情况下拿到错误的数据
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            # 2.获取指定知识库的关键词表
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }

            # 3.根据segment_ids查找片段的关键词信息
            segments = self.db.session.query(Segment).with_entities(Segment.id, Segment.keywords).filter(
                Segment.id.in_(segment_ids),
            ).all()

            # 4.循环将新关键词添加到关键词表中
            for id, keywords in segments:
                for keyword in keywords:
                    # 若keyword_table没有keyword
                    if keyword not in keyword_table:
                        # 先初始化这个keyword为空集合 方便后面添加id
                        keyword_table[keyword] = set()
                    # 无论是个keyword不在keyword_table还是keyword在keyword_table,
                    # 都向其添加segment_id => "keyword": {"segment_id"}
                    keyword_table[keyword].add(str(id))

            # 5.更新关键词表
            self.update(
                keyword_table_record,
                keyword_table={field: list(value) for field, value in keyword_table.items()}
            )
