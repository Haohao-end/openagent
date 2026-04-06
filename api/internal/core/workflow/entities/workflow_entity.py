import re
from collections import defaultdict, deque
from typing import Any, TypedDict, Annotated
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from internal.exception import ValidateErrorException
from .edge_entity import BaseEdgeData
from .node_entity import BaseNodeData, NodeResult, NodeType
from .variable_entity import VariableEntity, VariableValueType

# 工作流配置校验信息
WORKFLOW_CONFIG_NAME_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]*$'
WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH = 1024


def _process_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """工作流状态字典归纳函数"""
    # 1.处理left和right出现空的情况
    left = left or {}
    right = right or {}

    # 2.合并更新字典并返回
    return {**left, **right}


def _process_node_results(left: list[NodeResult], right: list[NodeResult]) -> list[NodeResult]:
    """工作流状态节点结果列表归纳函数"""
    # 1.处理left和right出现空的情况
    left = left or []
    right = right or []

    # 2.合并列表更新后返回
    return left + right


class WorkflowConfig(BaseModel):
    """工作流配置信息"""
    account_id: UUID  # 用户的唯一标识数据
    name: str = ""  # 工作流名称，必须是英文
    description: str = ""  # 工作流描述信息，用于告知LLM什么时候需要调用工作流
    nodes: list[BaseNodeData] = Field(default_factory=list)  # 工作流对应的节点列表信息
    edges: list[BaseEdgeData] = Field(default_factory=list)  # 工作流对应的边列表信息

    @model_validator(mode='before')
    def validate_workflow_config(cls, values: dict[str, Any]):
        """自定义校验函数，用于校验工作流配置中的所有参数信息"""
        # 1.获取工作流名字name，并校验是否符合规则
        name = values.get("name", None)
        if not name or not re.match(WORKFLOW_CONFIG_NAME_PATTERN, name):
            raise ValidateErrorException("工作流名字仅支持字母、数字和下划线，且以字母/下划线为开头")

        # 2.校验工作流的描述信息，该描述信息是传递给LLM使用，长度不能超过1024个字符
        description = values.get("description", None)
        if not description or len(description) > WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH:
            raise ValidateErrorException("工作流描述信息长度不能超过1024个字符")

        # 3.获取节点和边列表信息
        nodes = values.get("nodes", [])
        edges = values.get("edges", [])

        # 4.校验nodes/edges数据类型和内容不能为空
        if not isinstance(nodes, list) or len(nodes) <= 0:
            raise ValidateErrorException("工作流节点列表信息错误，请核实后重试")
        if not isinstance(edges, list) or len(edges) <= 0:
            raise ValidateErrorException("工作流边列表信息错误，请核实后重试")

        # 5.节点数据类映射
        from internal.core.workflow.nodes import (
            CodeNodeData,
            DatasetRetrievalNodeData,
            EndNodeData,
            HttpRequestNodeData,
            IfElseNodeData,
            LLMNodeData,
            ParameterExtractorNodeData,
            StartNodeData,
            TemplateTransformNodeData,
            TextProcessorNodeData,
            ToolNodeData,
            VariableAssignerNodeData,
        )
        node_data_classes = {
            NodeType.START.value: StartNodeData,
            NodeType.END.value: EndNodeData,
            NodeType.LLM.value: LLMNodeData,
            NodeType.TEMPLATE_TRANSFORM.value: TemplateTransformNodeData,
            NodeType.DATASET_RETRIEVAL.value: DatasetRetrievalNodeData,
            NodeType.CODE.value: CodeNodeData,
            NodeType.TOOL.value: ToolNodeData,
            NodeType.HTTP_REQUEST.value: HttpRequestNodeData,
            NodeType.TEXT_PROCESSOR.value: TextProcessorNodeData,
            NodeType.VARIABLE_ASSIGNER.value: VariableAssignerNodeData,
            NodeType.PARAMETER_EXTRACTOR.value: ParameterExtractorNodeData,
            NodeType.IF_ELSE.value: IfElseNodeData,
        }

        # 5.循环遍历所有节点
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            # 6.判断每个节点数据类型为字典
            if not isinstance(node, dict):
                raise ValidateErrorException("工作流节点数据类型出错，请核实后重试")

            # 7.获取节点的类型并判断类型是否存在
            node_type = node.get("node_type", "")
            node_data_cls = node_data_classes.get(node_type, None)
            if not node_data_cls:
                raise ValidateErrorException("工作流节点类型出错，请核实后重试")

            # 8.实例化节点数据，使用BaseModel规则进行校验
            node_data = node_data_cls(**node)

            # 9.判断开始和结束节点是否唯一
            if node_data.node_type == NodeType.START.value:
                if start_nodes >= 1:
                    raise ValidateErrorException("工作流中只允许有1个开始节点")
                start_nodes += 1
            elif node_data.node_type == NodeType.END.value:
                if end_nodes >= 1:
                    raise ValidateErrorException("工作流中只允许有1个结束节点")
                end_nodes += 1

            # 10.判断nodes节点数据id是否唯一
            if node_data.id in node_data_dict:
                raise ValidateErrorException("工作流节点id必须唯一，请核实后重试")

            # 11.判断nodes节点数据title是否唯一
            if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                raise ValidateErrorException("工作流节点title必须唯一，请核实后重试")

            # 12.将数据添加到node_data_dict中
            node_data_dict[node_data.id] = node_data

        # 13.循环遍历edges数据
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            # 14.判断边数据类型为字典
            if not isinstance(edge, dict):
                raise ValidateErrorException("工作流边数据类型出错，请核实后重试")

            # 15.实例化边数据，使用BaseModel规则进行校验
            edge_data = BaseEdgeData(**edge)

            # 16.校验边edges的id是否唯一
            if edge_data.id in edge_data_dict:
                raise ValidateErrorException("工作流边数据id必须唯一，请核实后重试")

            # 17.校验边中的source/target/source_type/target_type必须和nodes对得上
            if (
                    edge_data.source not in node_data_dict
                    or edge_data.source_type != node_data_dict[edge_data.source].node_type
                    or edge_data.target not in node_data_dict
                    or edge_data.target_type != node_data_dict[edge_data.target].node_type
            ):
                raise ValidateErrorException("工作流边起点/终点对应的节点不存在或类型错误，请核实后重试")

            # 17.5 校验条件分支节点的边必须有 source_handle
            source_node = node_data_dict[edge_data.source]
            if source_node.node_type == NodeType.IF_ELSE.value:
                if not edge_data.source_handle:
                    raise ValidateErrorException(
                        f"条件分支节点 '{source_node.title}' 的边必须指定 source_handle (true/false)，"
                        f"请在前端从正确的句柄（绿色勾表示true，红色叉表示false）拖拽连线"
                    )
                if edge_data.source_handle not in ["true", "false"]:
                    raise ValidateErrorException(
                        f"条件分支节点 '{source_node.title}' 的 source_handle 必须是 'true' 或 'false'，"
                        f"当前值: {edge_data.source_handle}"
                    )

            # 18.校验边Edges里的边必须唯一(source+target+source_handle必须唯一)
            # 对于条件分支节点，允许多条边连接到同一目标，但 source_handle 必须不同
            if any(
                    (item.source == edge_data.source
                     and item.target == edge_data.target
                     and item.source_handle == edge_data.source_handle)
                    for item in edge_data_dict.values()
            ):
                raise ValidateErrorException("工作流边数据不能重复添加")

            # 19.基础数据校验通过，将数据添加到edge_data_dict中
            edge_data_dict[edge_data.id] = edge_data

        # 20.构建邻接表、逆邻接表、入度以及出度
        adj_list = cls._build_adj_list(edge_data_dict.values())
        reverse_adj_list = cls._build_reverse_adj_list(edge_data_dict.values())
        in_degree, out_degree = cls._build_degrees(edge_data_dict.values())

        # 21.从边的关系中校验是否有唯一的开始/结束节点(入度为0即为开始，出度为0即为结束)
        start_nodes = [node_data for node_data in node_data_dict.values() if in_degree[node_data.id] == 0]
        end_nodes = [node_data for node_data in node_data_dict.values() if out_degree[node_data.id] == 0]
        if (
                len(start_nodes) != 1
                or len(end_nodes) != 1
                or start_nodes[0].node_type != NodeType.START.value
                or end_nodes[0].node_type != NodeType.END.value
        ):
            raise ValidateErrorException("工作流中有且只有一个开始/结束节点作为图结构的起点和终点")

        # 22.获取唯一的开始节点
        start_node_data = start_nodes[0]

        # 23.使用edges边信息校验图的连通性，确保没有孤立的节点
        if not cls._is_connected(adj_list, start_node_data.id):
            raise ValidateErrorException("工作流中存在不可到达节点，图不联通，请核实后重试")

        # 24.校验edges中是否存在环路（即循环边结构）
        if cls._is_cycle(node_data_dict.values(), adj_list, in_degree):
            raise ValidateErrorException("工作流中存在环路，请核实后重试")

        # 25.校验nodes+edges中的数据引用是否正确，即inputs/outputs对应的数据
        cls._validate_inputs_ref(node_data_dict, reverse_adj_list)

        # 26.更新values值
        values["nodes"] = list(node_data_dict.values())
        values["edges"] = list(edge_data_dict.values())

        return values

    @classmethod
    def _is_connected(cls, adj_list: defaultdict[Any, list], start_node_id: UUID) -> bool:
        """根据传递的邻接表+开始节点id，使用BFS广度优先搜索遍历，检查图是否流通"""
        # 1.记录已访问的节点
        visited = set()

        # 2.创建双向队列，并记录开始访问节点对应的id
        queue = deque([start_node_id])
        visited.add(start_node_id)

        # 3.循环遍历队列，广度优先搜索节点对应的子节点
        while queue:
            node_id = queue.popleft()
            for neighbor in adj_list[node_id]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # 4.计算已访问的节点数量是否和总结点数相等，如果不相等则表示存在孤立节点，图不流通
        return len(visited) == len(adj_list)

    @classmethod
    def _is_cycle(
            cls,
            nodes: list[BaseNodeData],
            adj_list: defaultdict[Any, list],
            in_degree: defaultdict[Any, int],
    ) -> bool:
        """根据传递的节点列表、邻接表、入度数据，使用拓扑排序(Kahn算法)检测图中是否存在环，如果存在则返回True，不存在则返回False"""
        # 1.存储所有入度为0的节点id，即开始节点
        zero_in_degree_nodes = deque([node.id for node in nodes if in_degree[node.id] == 0])

        # 2.记录已访问的节点数
        visited_count = 0

        # 3.循环遍历入度为0的节点信息
        while zero_in_degree_nodes:
            # 4.从队列左侧取出一个入度为0的节点，并记录访问+1
            node_id = zero_in_degree_nodes.popleft()
            visited_count += 1

            # 5.循环遍历取到的节点的所有子节点
            for neighbor in adj_list[node_id]:
                # 6.将子节点的入度-1，并判断是否为0，如果是则添加到队列中
                in_degree[neighbor] -= 1

                # 7.Kahn算法的核心是，如果存在环，那么至少有一个非结束节点的入度大于等于2，并且该入度无法消减到0
                #   这就会导致该节点后续的所有子节点在该算法下都无法浏览，那么访问次数肯定小于总节点数
                if in_degree[neighbor] == 0:
                    zero_in_degree_nodes.append(neighbor)

        # 8.判断访问次数和总结点数是否相等，如果不等/小于则说明存在环
        return visited_count != len(nodes)

    @classmethod
    def _validate_inputs_ref(
            cls,
            node_data_dict: dict[UUID, BaseNodeData],
            reverse_adj_list: defaultdict[Any, list],
    ) -> None:
        """校验输入数据引用是否正确，如果出错则直接抛出异常"""
        # 1.循环遍历所有节点数据逐个处理
        for node_data in node_data_dict.values():
            # 2.提取该节点的所有前置节点
            predecessors = cls._get_predecessors(reverse_adj_list, node_data.id)

            # 3.如果节点数据类型不是START则校验输入数据引用（因为开始节点不需要校验）
            if node_data.node_type != NodeType.START.value:
                # 4.根据节点类型从inputs或者是outputs中提取需要校验的数据
                variables: list[VariableEntity] = (
                    node_data.inputs if node_data.node_type != NodeType.END.value
                    else node_data.outputs
                )

                # 5.循环遍历所有需要校验的变量信息
                for variable in variables:
                    # 6.如果变量类型为引用，则需要校验
                    if variable.value.type == VariableValueType.REF.value:
                        # 7.判断前置节点是否为空，或者引用id不在前置节点内，则直接抛出错误
                        if (
                                len(predecessors) <= 0
                                or variable.value.content.ref_node_id not in predecessors
                        ):
                            raise ValidateErrorException(f"工作流节点[{node_data.title}]引用数据出错，请核实后重试")

                        # 8.提取数据引用的前置节点数据
                        ref_node_data = node_data_dict.get(variable.value.content.ref_node_id)

                        # 9.获取引用变量列表，如果是开始节点则从inputs中获取数据，否则从outputs中获取数据
                        ref_variables = (
                            ref_node_data.inputs if ref_node_data.node_type == NodeType.START.value
                            else ref_node_data.outputs
                        )

                        # 10.判断引用变量列表中是否存在该引用名字
                        if not any(
                                ref_variable.name == variable.value.content.ref_var_name
                                for ref_variable in ref_variables
                        ):
                            raise ValidateErrorException(
                                f"工作流节点[{node_data.title}]引用了不存在的节点变量，请核实后重试")

    @classmethod
    def _build_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict[Any, list]:
        """构建邻接表，邻接表的key为节点的id，值为该节点的所有直接子节点(后继节点)"""
        adj_list = defaultdict(list)
        for edge in edges:
            adj_list[edge.source].append(edge.target)
        return adj_list

    @classmethod
    def _build_reverse_adj_list(cls, edges: list[BaseEdgeData]) -> defaultdict[Any, list]:
        """构建逆邻接表，逆邻接表的key是每个节点的id，值为该节点的直接父节点"""
        reverse_adj_list = defaultdict(list)
        for edge in edges:
            reverse_adj_list[edge.target].append(edge.source)
        return reverse_adj_list

    @classmethod
    def _build_degrees(cls, edges: list[BaseEdgeData]) -> tuple[defaultdict[Any, int], defaultdict[Any, int]]:
        """根据传递的边信息，计算每个节点的入度(in_degree)和出度(out_degree)
           in_degree: 指有多少个节点指向该节点
           out_degree: 该节点指向多少个其他节点
        """
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)

        for edge in edges:
            in_degree[edge.target] += 1
            out_degree[edge.source] += 1

        return in_degree, out_degree

    @classmethod
    def _get_predecessors(cls, reverse_adj_list: defaultdict[Any, list], target_node_id: UUID) -> list[UUID]:
        """根据传递的逆邻接表+目标节点id，获取该节点的所有前置节点"""
        visited = set()
        predecessors = []

        def dfs(node_id):
            """使用广度搜索优先算法遍历所有的前置节点"""
            if node_id not in visited:
                visited.add(node_id)
                if node_id != target_node_id:
                    predecessors.append(node_id)
                for neighbor in reverse_adj_list[node_id]:
                    dfs(neighbor)

        dfs(target_node_id)

        return predecessors


class WorkflowState(TypedDict):
    """工作流图程序状态字典"""
    inputs: Annotated[dict[str, Any], _process_dict]  # 工作流的最初始输入，也就是工具输入
    outputs: Annotated[dict[str, Any], _process_dict]  # 工作流的最终输出结果，也就是工具输出
    node_results: Annotated[list[NodeResult], _process_node_results]  # 各节点的运行结果
