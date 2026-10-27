from __future__ import annotations

import io
from dataclasses import dataclass
from uuid import UUID

from flask import redirect, request, send_file
from flask_login import login_required
from injector import inject
from werkzeug.datastructures import MultiDict

from internal.schema.skill_schema import (
    GetSkillsCategoriesResp,
    GetSkillsWithPageReq,
    RollbackSkillPackageReq,
    SkillPackageResp,
    SkillVersionResp,
)
from internal.service.skill_service import SkillService
from pkg.paginator import PageModel
from pkg.response import success_json, success_message, validate_error_json


@inject
@dataclass
class SkillHandler:
    """技能包处理器。"""

    skill_service: SkillService

    def get_skill_categories(self):
        """获取技能分类统计。"""
        resp = GetSkillsCategoriesResp()
        return success_json(resp.dump(self.skill_service.get_skill_categories()))

    def get_skills_with_page(self):
        """获取技能包列表。"""
        req = GetSkillsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        skills, paginator = self.skill_service.get_skill_packages_with_page(req)
        resp = SkillPackageResp(many=True)
        return success_json(PageModel(list=resp.dump(skills), paginator=paginator))

    def get_skill_package(self, skill_id: UUID):
        """获取技能包详情。"""
        skill_package = self.skill_service.get_skill_package(skill_id)
        resp = SkillPackageResp()
        return success_json(resp.dump(skill_package))

    def get_skill_package_icon(self, skill_id: UUID):
        """获取技能包图标。"""
        icon, mimetype, icon_url = self.skill_service.get_skill_package_icon(skill_id)
        if icon_url:
            return redirect(icon_url)
        if icon is None:
            icon = b""
        return send_file(io.BytesIO(icon), mimetype or "application/octet-stream")

    def get_skill_package_versions(self, skill_id: UUID):
        """获取技能包版本历史。"""
        versions = self.skill_service.get_skill_package_versions(skill_id)
        resp = SkillVersionResp(many=True)
        return success_json({"list": resp.dump(versions)})

    @login_required
    def enable_skill_package(self, skill_id: UUID):
        """启用技能包。"""
        self.skill_service.enable_skill_package(skill_id)
        return success_message("启用技能包成功")

    @login_required
    def disable_skill_package(self, skill_id: UUID):
        """停用技能包。"""
        self.skill_service.disable_skill_package(skill_id)
        return success_message("停用技能包成功")

    @login_required
    def sync_skill_package(self, skill_id: UUID):
        """强制同步技能包到 SCF。"""
        self.skill_service.sync_skill_package(skill_id)
        return success_message("同步技能包成功")

    @login_required
    def rollback_skill_package(self, skill_id: UUID):
        """回滚技能包版本。"""
        data = request.get_json(force=True, silent=True)
        data = data if isinstance(data, dict) else {}
        req = RollbackSkillPackageReq(formdata=MultiDict(data))
        if not req.validate():
            return validate_error_json(req.errors)

        self.skill_service.rollback_skill_package(skill_id, int(req.version.data))
        return success_message("回滚技能包成功")
