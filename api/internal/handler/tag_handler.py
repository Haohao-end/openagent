"""
标签处理器

处理标签相关的 HTTP 请求。
"""

from dataclasses import dataclass
from uuid import UUID
from flask.typing import ResponseReturnValue
from flask_login import login_required, current_user
from injector import inject

from internal.schema.tag_schema import (
    CreateTagReq,
    UpdateTagReq,
    TagResp,
    ListTagsResp,
    GetMyTagsReq,
)
from internal.service import TagService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message


@inject
@dataclass
class TagHandler:
    """标签处理器"""
    tag_service: TagService

    @login_required
    def create_tag(self) -> ResponseReturnValue:
        """创建标签"""
        # 1. 提取请求并校验
        req = CreateTagReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. 调用服务创建标签
        tag = self.tag_service.create_tag(
            account_id=current_user.id,
            name=req.name.data,
            description=req.description.data or "",
            tag_type=req.tag_type.data or "custom",
        )

        # 3. 返回创建成功响应
        return success_json({"id": tag.id})

    @login_required
    def update_tag(self, tag_id: UUID) -> ResponseReturnValue:
        """更新标签"""
        # 1. 提取请求并校验
        req = UpdateTagReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. 调用服务更新标签
        tag = self.tag_service.update_tag(
            tag_id=tag_id,
            name=req.name.data,
            description=req.description.data or "",
        )

        if not tag:
            return success_message("标签不存在", code="not_found", status_code=404)

        # 3. 返回更新成功响应
        return success_message("更新标签成功")

    @login_required
    def delete_tag(self, tag_id: UUID) -> ResponseReturnValue:
        """删除标签"""
        # 1. 调用服务删除标签
        tag = self.tag_service.delete_tag(tag_id)

        if not tag:
            return success_message("标签不存在", code="not_found", status_code=404)

        # 2. 返回删除成功响应
        return success_message("删除标签成功")

    @login_required
    def get_tag(self, tag_id: UUID) -> ResponseReturnValue:
        """获取标签详情"""
        # 1. 调用服务获取标签
        tag = self.tag_service.get_tag_by_id(tag_id)

        if not tag:
            return success_message("标签不存在", code="not_found", status_code=404)

        # 2. 返回标签信息
        resp = TagResp()
        return success_json(resp.dump(tag))

    @login_required
    def list_tags(self) -> ResponseReturnValue:
        """获取标签列表"""
        # 1. 提取请求参数
        req = GetMyTagsReq()
        page = req.page or 1
        page_size = req.page_size or 20

        # 2. 调用服务获取标签列表
        page_model = self.tag_service.get_tags_with_page(
            account_id=current_user.id,
            page=page,
            page_size=page_size,
        )

        # 3. 返回标签列表
        resp = ListTagsResp()
        return success_json(resp.dump(page_model))

    def get_tags(self) -> ResponseReturnValue:
        """获取所有标签（公开接口）"""
        # 1. 提取请求参数
        req = GetMyTagsReq()
        page = req.page or 1
        page_size = req.page_size or 20

        # 2. 调用服务获取标签列表
        page_model = self.tag_service.get_tags_with_page(
            account_id=current_user.id if current_user.is_authenticated else None,
            page=page,
            page_size=page_size,
        )

        # 3. 返回标签列表
        resp = ListTagsResp()
        return success_json(resp.dump(page_model))

    def get_dimensions(self) -> ResponseReturnValue:
        """获取标签维度"""
        # 返回标签维度信息
        dimensions = {
            "types": ["custom", "system", "category"],
            "statuses": ["active", "inactive", "archived"],
        }
        return success_json(dimensions)

    def get_hot_tags(self) -> ResponseReturnValue:
        """获取热门标签"""
        # 返回热门标签列表
        # 这里可以根据使用频率返回热门标签
        return success_json({"tags": []})
