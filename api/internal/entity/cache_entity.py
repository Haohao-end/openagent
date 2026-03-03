# 缓存所的过期时间，单位为妙，默认为600
LOCK_EXPIRE_TIME = 600

# 更新文档启用状态缓存锁
LOCK_DOCUMENT_UPDATE_ENABLED = "lock:document:update:enabled_{document_id}"

# 更新关键词表缓存锁
LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE = "lock:keyword_table:update:keyword_table_{dataset_id}"

# 更新片段启用状态缓存锁
LOCK_SEGMENT_UPDATE_ENABLED = "lock:segment:update:enabled_{segment_id}"