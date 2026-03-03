import os.path
from typing import Union, Type, Any, Optional
import yaml
from pydantic import BaseModel, Field, model_validator
from internal.exception import FailException, NotFoundException
from internal.lib.helper import dynamic_import
from .default_model_parameter_template import DEFAULT_MODEL_PARAMETER_TEMPLATE
from .model_entity import ModelType, ModelEntity, BaseLanguageModel


class ProviderEntity(BaseModel):
    """模型提供商实体信息"""
    name: str = ""  # 提供商的名字
    label: str = ""  # 提供商的标签
    description: str = ""  # 提供商的描述信息
    icon: str = ""  # 提供商的图标
    background: str = ""  # 提供商的图标背景
    supported_model_types: list[ModelType] = Field(default_factory=list)  # 支持的模型类型


class Provider(BaseModel):
    """大语言模型服务提供商，在该类下，可以获取到该服务提供商的所有大语言模型、描述、图标、标签等多个信息"""
    name: str  # 提供商名字
    position: int  # 服务提供商的位置信息
    provider_entity: ProviderEntity  # 模型提供商实体
    model_entity_map: dict[str, ModelEntity] = Field(default_factory=dict)  # 模型实体映射
    model_class_map: dict[str, Union[None, Type[BaseLanguageModel]]] = Field(default_factory=dict)  # 模型类映射

    @model_validator(mode='after')
    def validate_provider(self) -> 'Provider':
        """服务提供者校验器，利用校验器完成该服务提供者的实体与类实例化"""
        # 1.获取服务提供商实体
        provider_entity = self.provider_entity

        # 2.动态导入服务提供商的模型类
        for model_type in provider_entity.supported_model_types:
            # 3.将类型的第一个字符转换成大写，其他不变，并构建类映射
            model_type_str = model_type.value  # 获取 Enum 的字符串值（如 "chat"）
            symbol_name = model_type_str[0].upper() + model_type_str[1:]  # "chat" -> "Chat"
            self.model_class_map[model_type_str] = dynamic_import(
                f"internal.core.language_model.providers.{provider_entity.name}.{model_type_str}",
                symbol_name
            )

        # 4.获取当前类所在的位置，provider提供商所在的位置
        current_path = os.path.abspath(__file__)
        entities_path = os.path.dirname(current_path)
        provider_path = os.path.join(os.path.dirname(entities_path), "providers", provider_entity.name)

        # 5.组装positions.yaml的位置，并读取数据
        positions_yaml_path = os.path.join(provider_path, "positions.yaml")
        with open(positions_yaml_path, encoding="utf-8") as f:
            positions_yaml_data = yaml.safe_load(f) or []
        if not isinstance(positions_yaml_data, list):
            raise FailException("positions.yaml数据格式错误")

        # 6.循环读取位置中的模型名字
        for model_name in positions_yaml_data:
            # 7.组装每一个模型的详细信息
            model_yaml_path = os.path.join(provider_path, f"{model_name}.yaml")
            with open(model_yaml_path, encoding="utf-8") as f:
                model_yaml_data = yaml.safe_load(f)

            # 8.循环读取模型中的parameters参数
            yaml_parameters = model_yaml_data.get("parameters")
            parameters = []
            for parameter in yaml_parameters:
                # 9.检测参数规则是否使用了模板配置
                use_template = parameter.get("use_template")
                if use_template:
                    # 10.使用了模板，则使用模板补全剩余数据，并删除use_template
                    default_parameter = DEFAULT_MODEL_PARAMETER_TEMPLATE.get(use_template)
                    del parameter["use_template"]
                    parameters.append({**default_parameter, **parameter})
                else:
                    # 11.未使用模板，则直接添加
                    parameters.append(parameter)

            # 12.修改对应模板的yaml数据，并创建ModelEntity随后传递给provider
            model_yaml_data["parameters"] = parameters
            self.model_entity_map[model_name] = ModelEntity(**model_yaml_data)

        return self

    def get_model_class(self, model_type: ModelType) -> Optional[Type[BaseLanguageModel]]:
        """根据传递的模型类型获取该提供者的模型类"""
        model_class = self.model_class_map.get(model_type, None)
        if model_class is None:
            raise NotFoundException("该模型类不存在，请核实后重试")
        return model_class

    def get_model_entity(self, model_name: str) -> Optional[ModelEntity]:
        """根据传递的模型名字获取模型实体信息"""
        model_entity = self.model_entity_map.get(model_name, None)
        if model_entity is None:
            raise NotFoundException("该模型实体不存在，请核实后重试")
        return model_entity

    def get_model_entities(self) -> list[ModelEntity]:
        """获取该服务提供者的所有模型实体列表信息"""
        return list(self.model_entity_map.values())