from pydantic import BaseModel, Field, field_validator
from internal.exception import ValidateErrorException
from enum import Enum

class ParameterType(str, Enum):
    """参数支持的类型"""
    STR: str = "str"
    INT: str = "int"
    FLOAT: str = "float"
    BOOL: str = "bool"

ParameterTypeMap = {
    ParameterType.STR: str,
    ParameterType.INT: int,
    ParameterType.FLOAT: float,
    ParameterType.BOOL: bool,
}

class ParameterIn(str, Enum):
    """参数支持存放的位置"""
    PATH: str = "path"
    QUERY: str = "query"
    HEADER: str = "header"
    COOKIE: str = "cookie"
    REQUEST_BODY: str = "request_body"

class OpenAPISchema(BaseModel):
    """OpenAPI规范的数据结构"""
    server: str = Field(default="", description="工具提供者的服务基础地址")
    description: str = Field(default="", description="工具提供者的描述信息")
    paths: dict[str, dict] = Field(default_factory=dict, description="工具提供者的路径参数字典")

    @field_validator("server",mode="before")
    def validate_server(cls,server:str) -> str:
        """校验server数据"""
        if server is None or server == "":
            raise ValidateErrorException("server不能为空且为字符串")
        return server

    @field_validator("description", mode="before")
    def validate_description(cls, description: str) -> str:
        """校验description数据"""
        if description is None or description == "":
            raise ValidateErrorException("description不能为空且为字符串")
        return description

    @field_validator("paths", mode="before")
    def validate_paths(cls, paths: dict[str,dict]) -> dict[str,dict]:
        """校验paths信息 涵盖方法获取 operationID唯一标识 parameters校验"""
        # paths 不能为空且类型为字典
        if not paths or not isinstance(paths,dict):
            raise ValidateErrorException("openapi_schema中的paths不能为空且必须为字典")

        # 提取paths里的每一格元素 并获取元素下的get/post方法对应的值
        methods = ["get","post"]
        interfaces = []
        extra_paths = {}
        for path, path_item in paths.items():
            for method in methods:
                # 检测是否存在特定的方法并提取信息
                if method in path_item:
                    interfaces.append({
                        "path": path,
                        "method": method,
                        "operation": path_item[method]
                    })

        # 遍历提取到的所有接口并校验信息 涵盖operationId唯一标识 parameters参数
        operation_ids = []
        for interface in interfaces:
            # 校验description/operationId/parameters字段
            if not isinstance(interface["operation"].get("description"),str):
                raise ValidateErrorException("description为字符串且不能为空")
            if not isinstance(interface["operation"].get("operationId"),str):
                raise ValidateErrorException("operationId为字符串且不能为空")
            if not isinstance(interface["operation"].get("parameters",[]), list):
                raise ValidateErrorException("parameters必须是列表或者为空")

            # 检测operationId是否是唯一的
            if interface["operation"]["operationId"] in operation_ids:
                raise ValidateErrorException(f"operationId必须唯一,{interface['operation']['operationId']}出现重复")
            operation_ids.append(interface["operation"]["operationId"])

            # 校验parameters参数格式是否正确
            for parameter in interface["operation"].get("parameters",[]):
                """校验name/in/description/required/type参数是否存在 并且类型正确"""
                if not isinstance(parameter.get("name"), str):
                    raise ValidateErrorException("parameter.name为字符串且不能为空")
                if not isinstance(parameter.get("description"), str):
                    raise ValidateErrorException("parameter.description为字符串且不能为空")
                if not isinstance(parameter.get("required"), bool):
                    raise ValidateErrorException("parameter.required为布尔值且不能为空")
                if (
                    not isinstance(parameter.get("in"),str)
                    or parameter.get("in") not in ParameterIn.__members__.values()
                ):
                    raise ValidateErrorException(
                        f"parameter.in参数必须为{'/'.join([item.value for item in ParameterIn])}"
                    )
                if (
                    not isinstance(parameter.get("type"),str)
                    or parameter.get("type") not in ParameterType.__members__.values()
                ):
                    raise ValidateErrorException(
                        f"parameter.type参数必须为{'/'.join([item.value for item in ParameterType])}"
                    )

            # 组装数据并更新
            extra_paths[interface["path"]] = {
                interface["method"]: {
                    "description": interface["operation"]["description"],
                    "operationId": interface["operation"]["operationId"],
                    "parameters": [{
                        "name": parameter.get("name"),
                        "in": parameter.get("in"),
                        "description": parameter.get("description"),
                        "required": parameter.get("required"),
                        "type": parameter.get("type"),
                    } for parameter in interface["operation"].get("parameters",[])]
                }
            }

        return extra_paths















