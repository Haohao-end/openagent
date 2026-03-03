-- 检测postgres是否未安装uuid扩展 如果未安装则安装
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 将数据库默认时区固定为UTC（仅首次初始化数据目录时执行）
ALTER DATABASE llmops SET timezone TO 'UTC';
