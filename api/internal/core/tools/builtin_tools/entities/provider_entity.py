from pydantic import BaseModel, ConfigDict, Field
from typing import Any
from .tool_entity import ToolEntity
import os.path
import yaml
from internal.lib.helper import dynamic_import
class ProviderEntity(BaseModel):
    """服务提供商实体 映射的数据时providers.yaml里的每条记录"""
    name:str # 名字
    label:str # 标签
    description:str # 描述
    icon:str # 图标地址
    background:str # 图标的颜色
    category:str #种类信息
    created_at: int = 0 #提供商/工具创建的时间戳




class Provider(BaseModel):
    """服务提供商 可以获取到该服务提供商的所有工具 描述 图标等多个信息"""
    name: str  # 服务提供商的名字
    position: int  # 服务提供商的顺序
    provider_entity: ProviderEntity  # 服务提供商的实体
    tool_entity_map: dict[str, ToolEntity] = Field(default_factory=dict)  # 工具实体映射表
    tool_func_map: dict[str, Any] = Field(default_factory=dict)  # 工具函数映射表

    def __init__(self, **kwargs):
        """构造函数 完成对应服务提供商的初始化"""
        super().__init__(**kwargs)
        self._provider_init()

    model_config = ConfigDict(protected_namespaces=())

    def get_tool(self, tool_name: str) -> Any:
        """根据工具的名字 来获取该服务提供商下的指定工具"""
        return self.tool_func_map.get(tool_name)

    def get_tool_entity(self, tool_name: str) -> ToolEntity:
        """根据工具的名字 来获取该服务提供商下的指定工具的实体信息"""
        return self.tool_entity_map.get(tool_name)

    def get_tool_entities(self) -> list[ToolEntity]:
        """获取该服务提供商下的所有工具实体信息列表"""
        return list(self.tool_entity_map.values())
    def _provider_init(self):
        """服务提供商初始化函数"""
        # 获取当前类的路径 计算得到对应的服务提供商的地址/路径
        current_path = os.path.abspath(__file__)
        # 获取entities的路径
        entities_path = os.path.dirname(current_path)
        # 获取工具的路径(先获取entities所在的文件夹路径,再拼接providers和providers下的名称获取工具路径)
        provider_path = os.path.join(os.path.dirname(entities_path), "providers", self.name)

        # 组装获取工具的positions.yaml数据
        positions_yaml_path = os.path.join(provider_path, "positions.yaml")
        with open(positions_yaml_path, encoding="utf-8") as f:
            positions_yaml_data = yaml.safe_load(f)


        # 循环读取位置信息获取服务提供商的工具名字
        for tool_name in positions_yaml_data:
            # 获取工具的yaml数据
            tool_yaml_path = os.path.join(provider_path, f"{tool_name}.yaml")
            with open(tool_yaml_path,encoding="utf-8") as f:
                tool_yaml_data = yaml.safe_load(f)
            # 将工具信息实体(google_serper.yaml)赋值到tool_entity_map中
            self.tool_entity_map[tool_name] = ToolEntity(**tool_yaml_data)

            # 动态导入对应的工具(如google_serper.py下的google_serper函数)填充到tool_func_map中
            self.tool_func_map[tool_name] = dynamic_import(
                f"internal.core.tools.builtin_tools.providers.{self.name}",
                tool_name
            )
