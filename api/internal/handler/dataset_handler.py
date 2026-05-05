from dataclasses import dataclass
from uuid import UUID
from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.core.file_extractor import FileExtractor
from internal.schema.dataset_schema import (
    CreateDatasetReq,
    GetDatasetResp,
    UpdateDatasetReq,
    GetDatasetsWithPageReq,
    GetDatasetsWithPageResp,
    HitReq,
    GetDatasetQueriesResp,
)
from internal.service import (
    DatasetService,
    EmbeddingsService,
    JiebaService,
    VectorDatabaseService,
)
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_message, success_json
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class DatasetHandler:
    """知识库处理器"""
    db: SQLAlchemy
    file_extractor: FileExtractor
    dataset_service: DatasetService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    vector_database_service: VectorDatabaseService

    @login_required
    def hit(self, dataset_id: UUID):
        """根据传递的知识库id+检索参数执行召回测试"""
        # 1.提取数据并校验
        req = HitReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务执行检索策略
        hit_result = self.dataset_service.hit(dataset_id, req, current_user)

        return success_json(hit_result)

    @login_required
    def get_dataset_queries(self, dataset_id: UUID):
        """根据传递的知识库id获取最近的10条查询记录"""
        dataset_queries = self.dataset_service.get_dataset_queries(dataset_id, current_user)
        resp = GetDatasetQueriesResp(many=True)
        return success_json(resp.dump(dataset_queries))

    @login_required
    def create_dataset(self):
        """创建知识库"""
        # 1.提取请求并校验
        req = CreateDatasetReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务创建知识库
        self.dataset_service.create_dataset(req, current_user)

        # 3.返回成功调用提示
        return success_message("创建知识库成功")

    @login_required
    def get_dataset(self, dataset_id: UUID):
        """根据传递的知识库id获取详情"""
        dataset = self.dataset_service.get_dataset(dataset_id, current_user)
        resp = GetDatasetResp()

        return success_json(resp.dump(dataset))

    @login_required
    def update_dataset(self, dataset_id: UUID):
        """根据传递的知识库id+信息更新知识库"""
        # 1.提取请求并校验
        req = UpdateDatasetReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务创建知识库
        self.dataset_service.update_dataset(dataset_id, req, current_user)

        # 3.返回成功调用提示
        return success_message("更新知识库成功")

    @login_required
    def delete_dataset(self, dataset_id: UUID):
        """根据传递的知识库id删除知识库"""
        self.dataset_service.delete_dataset(dataset_id, current_user)
        return success_message("删除知识库成功")

    @login_required
    def get_datasets_with_page(self):
        """获取知识库分页+搜索列表数据"""
        # 1.提取query数据并校验
        req = GetDatasetsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取分页数据
        datasets, paginator = self.dataset_service.get_datasets_with_page(req, current_user)

        # 3.构建响应
        resp = GetDatasetsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(datasets), paginator=paginator))

    @login_required
    def regenerate_icon(self, dataset_id: UUID):
        """根据传递的知识库id重新生成知识库图标"""
        icon_url = self.dataset_service.regenerate_icon(dataset_id, current_user)
        return success_json({"icon": icon_url})

    @login_required
    def generate_icon_preview(self):
        """根据传递的名称和描述生成图标预览（不保存到知识库）"""
        # 1.获取请求数据
        data = request.get_json(force=True, silent=True) or {}
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        # 2.校验名称不能为空
        if not name:
            return validate_error_json({'name': ['知识库名称不能为空']})

        # 3.调用服务生成图标
        icon_url = self.dataset_service.generate_icon_preview(name, description)

        return success_json({"icon": icon_url})
