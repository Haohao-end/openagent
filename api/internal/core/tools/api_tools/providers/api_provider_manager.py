from dataclasses import dataclass
from typing import Type, Optional, Callable
from injector import inject
import requests
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel,create_model, Field
from internal.core.tools.api_tools.entities import ToolEntity,ParameterTypeMap, ParameterIn

@inject
@dataclass
class ApiProviderManager(BaseModel):
    """ API工具提供者管理器 能根据传递的工具配置信息生成自定义LangChain工具"""
    @classmethod
    def _create_tool_func_from_tool_entity(cls,tool_entity:ToolEntity) -> Callable:
        """根据传递的信息创建发起API请求的函数"""

        def tool_func(**kwargs) -> str:
            """API工具请求函数"""
            # 1. 定义变量存储来自path/query/header/cookie/request_body
            parameters = {
                ParameterIn.PATH: {},
                ParameterIn.HEADER: {},
                ParameterIn.QUERY: {},
                ParameterIn.COOKIE: {},
                ParameterIn.REQUEST_BODY: {},
            }
            # 2.更改参数结构映射
            parameter_map = {parameter.get("name"): parameter for parameter in tool_entity.parameters}
            header_map = {header.get("key"): header.get("value") for header in tool_entity.headers}

            # 3.循环遍历传递的所有字段并校验
            for key, value in kwargs.items():
                # 4.提取简直对关联的字段并校验
                parameter = parameter_map.get(key)
                if parameter is None:
                    continue

                # 5.将参数存储到合适的位置上 默认在query上
                parameters[parameter.get("in", ParameterIn.QUERY)][key] = value

            # 6.构建request请求并返回采集的内容
            return requests.request(
                method=tool_entity.method,
                url=tool_entity.url.format(**parameters[ParameterIn.PATH]),
                params=parameters[ParameterIn.QUERY],
                json=parameters[ParameterIn.REQUEST_BODY],
                headers={**header_map,**parameters[ParameterIn.HEADER]},
                cookies=parameters[ParameterIn.COOKIE]
            ).text

        return tool_func
    @classmethod
    def _create_model_from_parameters(cls, parameters: list[dict]) -> Type[BaseModel]:
        """根据传递的parameters参数创建BaseModel子类"""
        fields = {}
        for parameter in parameters:
            field_name = parameter.get("name")
            field_type = ParameterTypeMap.get(parameter.get("type"), str)
            field_required = parameter.get("required", True)
            field_description = parameter.get("description", "")

            fields[field_name] = (
                field_type if field_required else Optional[field_type],
                Field(description=field_description)
            )
        return create_model("DynamicModel", **fields)

    def get_tool(self, tool_entity: ToolEntity) -> BaseModel:
        """根据传递的配置获取自定义API工具"""
        return StructuredTool.from_function(
            func=self._create_tool_func_from_tool_entity(tool_entity),
            name=f"{tool_entity.id}_{tool_entity.name}",
            description=tool_entity.description,
            args_schema=self._create_model_from_parameters(tool_entity.parameters)
        )

