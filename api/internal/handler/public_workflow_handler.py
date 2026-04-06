"""公共工作流Handler"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from pkg.response import success_json, success_message, validate_error_json
from internal.schema.public_workflow_schema import (
    ShareWorkflowToSquareReq,
    GetPublicWorkflowsWithPageReq,
    PublicWorkflowResp,
    LikeWorkflowResp,
    FavoriteWorkflowResp,
    ForkWorkflowResp,
)
from internal.service.public_workflow_service import PublicWorkflowService
from pkg.paginator import PageModel


@inject
@dataclass
class PublicWorkflowHandler:
    """公共工作流Handler"""
    public_workflow_service: PublicWorkflowService

    @login_required
    def share_workflow_to_square(self, workflow_id: UUID):
        """共享工作流到广场"""
        req = ShareWorkflowToSquareReq()
        if not req.validate():
            return validate_error_json(req.errors)

        tags = req.tags.data if req.tags.data else None
        self.public_workflow_service.share_workflow_to_square(workflow_id, tags, current_user)
        return success_message("工作流已共享到广场")

    @login_required
    def unshare_workflow_from_square(self, workflow_id: UUID):
        """取消工作流从广场的共享"""
        self.public_workflow_service.unshare_workflow_from_square(workflow_id, current_user)
        return success_message("工作流已从广场取消共享")

    def get_public_workflows_with_page(self):
        """获取公共工作流广场列表(支持未登录访问)"""
        req = GetPublicWorkflowsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        try:
            account = current_user if current_user.is_authenticated else None
        except:
            account = None

        workflows, paginator = self.public_workflow_service.get_public_workflows_with_page(req, account)
        return success_json(PageModel(list=workflows, paginator=paginator))

    @login_required
    def fork_public_workflow(self, workflow_id: UUID):
        """Fork公共工作流到个人空间"""
        workflow = self.public_workflow_service.fork_public_workflow(workflow_id, current_user)
        resp = ForkWorkflowResp()
        return success_json(resp.dump({"id": str(workflow.id), "name": workflow.name}))

    @login_required
    def like_workflow(self, workflow_id: UUID):
        """点赞/取消点赞工作流"""
        result = self.public_workflow_service.like_workflow(workflow_id, current_user)
        resp = LikeWorkflowResp()
        return success_json(resp.dump(result))

    @login_required
    def favorite_workflow(self, workflow_id: UUID):
        """收藏/取消收藏工作流"""
        result = self.public_workflow_service.favorite_workflow(workflow_id, current_user)
        resp = FavoriteWorkflowResp()
        return success_json(resp.dump(result))

    def get_public_workflow_detail(self, workflow_id: UUID):
        """获取公共工作流详情（支持未登录访问）"""
        try:
            account = current_user if current_user.is_authenticated else None
        except:
            account = None

        workflow_detail = self.public_workflow_service.get_public_workflow_detail(workflow_id, account)
        return success_json(workflow_detail)

    def get_public_workflow_draft_graph(self, workflow_id: UUID):
        """获取公共工作流的草稿图配置(支持未登录访问)"""
        graph = self.public_workflow_service.get_public_workflow_draft_graph(workflow_id)
        return success_json(graph)
