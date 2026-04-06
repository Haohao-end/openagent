"""
标签处理器

处理标签相关的 HTTP 请求。
"""

from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask.typing import ResponseReturnValue
from flask_login import login_required, current_user
from injector import inject

from internal.schema.tag_schema import (
    CreateTagReq,
    GetHotTagsResp,
    GetMyTagsReq,
    GetTagDimensionsResp,
    TagResp,
    UpdateTagReq,
)
from internal.service import TagService
from pkg.paginator import PageModel
from pkg.response import not_found_message, success_json, success_message, validate_error_json


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
            account_id=current_user.id,
            name=req.name.data,
            description=req.description.data or "",
        )

        if not tag:
            return not_found_message("标签不存在")

        # 3. 返回更新成功响应
        return success_message("更新标签成功")

    @login_required
    def delete_tag(self, tag_id: UUID) -> ResponseReturnValue:
        """删除标签"""
        # 1. 调用服务删除标签
        tag = self.tag_service.delete_tag(tag_id, current_user.id)

        if not tag:
            return not_found_message("标签不存在")

        # 2. 返回删除成功响应
        return success_message("删除标签成功")

    @login_required
    def get_tag(self, tag_id: UUID) -> ResponseReturnValue:
        """获取标签详情"""
        # 1. 调用服务获取标签
        tag = self.tag_service.get_tag_by_id(tag_id, current_user.id)

        if not tag:
            return not_found_message("标签不存在")

        # 2. 返回标签信息
        resp = TagResp()
        return success_json(resp.dump(tag))

    @login_required
    def list_tags(self) -> ResponseReturnValue:
        """获取标签列表"""
        # 1. 提取请求参数
        req = GetMyTagsReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. 调用服务获取标签列表
        tags, paginator = self.tag_service.get_tags_with_page(
            req=req,
            account_id=current_user.id,
        )

        # 3. 返回标签列表
        resp = TagResp(many=True)
        return success_json(PageModel(list=resp.dump(tags), paginator=paginator))

    def get_dimensions(self) -> ResponseReturnValue:
        """获取标签维度"""
        resp = GetTagDimensionsResp()
        return success_json(resp.dump({
            "dimensions": self.tag_service.get_tag_dimensions(),
        }))

    def get_hot_tags(self) -> ResponseReturnValue:
        """获取热门标签"""
        resp = GetHotTagsResp()
        return success_json(resp.dump({
            "hot_tags": self.tag_service.get_hot_tags(),
        }))
