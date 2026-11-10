import inspect
from typing import Any, Optional, Iterator
from flask import current_app
from pydantic import PrivateAttr, BaseModel, Field, create_model
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Input, Output
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from internal.exception import ValidateErrorException
from .entities.node_entity import NodeType
from .entities.variable_entity import VARIABLE_TYPE_MAP
from .entities.workflow_entity import WorkflowConfig, WorkflowState
from .nodes import (
    StartNode,
    LLMNode,
    ParameterExtractorNode,
    TemplateTransformNode,
    DatasetRetrievalNode,
    CodeNode,
    ToolNode,
    HttpRequestNode,
    TextProcessorNode,
    VariableAssignerNode,
    IfElseNode,
    EndNode,
)
# 节点类映射
NodeClasses = {
    NodeType.START.value: StartNode,
    NodeType.END.value: EndNode,
    NodeType.LLM.value: LLMNode,
    NodeType.TEMPLATE_TRANSFORM.value: TemplateTransformNode,
    NodeType.DATASET_RETRIEVAL.value: DatasetRetrievalNode,
    NodeType.CODE.value: CodeNode,
    NodeType.TOOL.value: ToolNode,
    NodeType.HTTP_REQUEST.value: HttpRequestNode,
    NodeType.TEXT_PROCESSOR.value: TextProcessorNode,
    NodeType.VARIABLE_ASSIGNER.value: VariableAssignerNode,
    NodeType.PARAMETER_EXTRACTOR.value: ParameterExtractorNode,
    NodeType.IF_ELSE.value: IfElseNode,
}


class Workflow(BaseTool):
    """工作流LangChain工具类"""
    _workflow_config: WorkflowConfig = PrivateAttr(None)
    _workflow: CompiledStateGraph = PrivateAttr(None)

    def __init__(self, workflow_config: WorkflowConfig, **kwargs: Any):
        """构造函数，完成工作流函数的初始化"""
        # 1.调用父类构造函数完成基础数据初始化
        super().__init__(
            name=workflow_config.name,
            description=workflow_config.description,
            args_schema=self._build_args_schema(workflow_config),
            **kwargs
        )

        # 2.完善工作流配置与工作流图结构程序的初始化
        self._workflow_config = workflow_config
        self._workflow = self._build_workflow()

    @classmethod
    def _build_args_schema(cls, workflow_config: WorkflowConfig) -> type[BaseModel]:
        """构建输入参数结构体"""
        # 1.提取开始节点的输入参数信息
        fields = {}
        inputs = next(
            (node.inputs for node in workflow_config.nodes if node.node_type == NodeType.START.value),
            []
        )

        # 2.循环遍历所有输入信息并创建字段映射
        for input in inputs:
            field_name = input.name
            field_type = VARIABLE_TYPE_MAP.get(input.type, str)
            field_required = input.required
            field_description = input.description

            fields[field_name] = (
                field_type if field_required else Optional[field_type],
                Field(default=... if field_required else None, description=field_description),
            )

        # 3.调用create_model创建一个BaseModel类，并使用上述分析好的字段
        return create_model("DynamicModel", **fields)

    def _build_workflow(self) -> CompiledStateGraph:
        """构建编译后的工作流图程序"""
        # 1.创建graph图程序结构
        graph = StateGraph(WorkflowState)
        node_types = {}
        incoming_edges = {}

        def find_result(state, node_flag):
            for result in reversed(state.get("node_results", [])):
                node_type = result.node_data.node_type
                if isinstance(node_type, NodeType):
                    node_type = node_type.value
                if f"{node_type}_{result.node_data.id}" == node_flag:
                    return result
            return None

        def active(node_flag, state, seen=None):
            if node_types.get(node_flag) == NodeType.START:
                return True
            seen = set() if seen is None else seen
            if node_flag in seen:
                return None
            seen.add(node_flag)
            statuses = []
            for source, source_type, handle in incoming_edges.get(node_flag, []):
                source_active = active(source, state, seen.copy())
                if source_active is False:
                    statuses.append(False)
                elif source_active is None:
                    statuses.append(None)
                elif source_type == NodeType.IF_ELSE:
                    result = find_result(state, source)
                    if result is None:
                        statuses.append(None)
                    else:
                        selected = "true" if result.outputs.get("result", True) else "false"
                        statuses.append(selected == (handle or "true"))
                else:
                    statuses.append(True)
            if any(status is True for status in statuses):
                return True
            return None if any(status is None for status in statuses) else False

        def ready(node_flag, state):
            if find_result(state, node_flag) is not None:
                return False
            if node_types.get(node_flag) == NodeType.START:
                return True
            has_active_predecessor = False
            for source, source_type, handle in incoming_edges.get(node_flag, []):
                source_active = active(source, state)
                if source_active is None:
                    return False
                if source_active is False:
                    continue
                result = find_result(state, source)
                if result is None:
                    return False
                if source_type == NodeType.IF_ELSE:
                    selected = "true" if result.outputs.get("result", True) else "false"
                    if selected != (handle or "true"):
                        continue
                has_active_predecessor = True
            return has_active_predecessor

        class WorkflowNodeRunner:
            def __init__(self, node_flag, node):
                self.node_flag = node_flag
                self.node = node

            async def __call__(self, state, config=None):
                if not ready(self.node_flag, state):
                    return {}
                if hasattr(self.node, "ainvoke"):
                    return await self.node.ainvoke(state, config=config)
                result = self.node(state)
                return await result if inspect.isawaitable(result) else result

        # 2.提取nodes和edges信息
        nodes = self._workflow_config.nodes
        edges = self._workflow_config.edges

        # 3.循环遍历nodes节点信息添加节点
        for node in nodes:
            node_type = node.node_type
            if isinstance(node_type, str):
                node_type = NodeType(node_type)
            node_flag = f"{node_type.value}_{node.id}"
            node_types[node_flag] = node_type
            if node.node_type == NodeType.START.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.START.value](node_data=node)),
                )
            elif node.node_type == NodeType.LLM.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.LLM.value](node_data=node)),
                )
            elif node.node_type == NodeType.TEMPLATE_TRANSFORM.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.TEMPLATE_TRANSFORM.value](node_data=node)),
                )
            elif node.node_type == NodeType.DATASET_RETRIEVAL.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(
                        node_flag,
                        NodeClasses[NodeType.DATASET_RETRIEVAL.value](
                            flask_app=current_app._get_current_object(),
                            account_id=self._workflow_config.account_id,
                            node_data=node,
                        ),
                    ),
                )
            elif node.node_type == NodeType.CODE.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.CODE.value](node_data=node)),
                )
            elif node.node_type == NodeType.TOOL.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.TOOL.value](node_data=node)),
                )
            elif node.node_type == NodeType.HTTP_REQUEST.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.HTTP_REQUEST.value](node_data=node)),
                )
            elif node.node_type == NodeType.TEXT_PROCESSOR.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.TEXT_PROCESSOR.value](node_data=node)),
                )
            elif node.node_type == NodeType.VARIABLE_ASSIGNER.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.VARIABLE_ASSIGNER.value](node_data=node)),
                )
            elif node.node_type == NodeType.PARAMETER_EXTRACTOR.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.PARAMETER_EXTRACTOR.value](node_data=node)),
                )
            elif node.node_type == NodeType.IF_ELSE.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.IF_ELSE.value](node_data=node)),
                )
            elif node.node_type == NodeType.END.value:
                graph.add_node(
                    node_flag,
                    WorkflowNodeRunner(node_flag, NodeClasses[NodeType.END.value](node_data=node)),
                )
            else:
                raise ValidateErrorException("工作流节点类型错误，请核实后重试")

        # 4.循环遍历edges信息，区分普通边和条件边
        parallel_edges = {}  # key:终点，value:起点列表（普通边）
        conditional_edges = {}  # key:if_else节点，value:条件边配置
        incoming_edges = {}
        start_node = ""
        end_node = ""

        for edge in edges:
            source_node = f"{edge.source_type.value}_{edge.source}"
            target_node = f"{edge.target_type.value}_{edge.target}"
            incoming_edges.setdefault(target_node, []).append(
                (source_node, edge.source_type, edge.source_handle)
            )

            # 检测是否为条件边（从 if_else 节点出发的边）
            if edge.source_type == NodeType.IF_ELSE.value:
                if source_node not in conditional_edges:
                    conditional_edges[source_node] = {}
                # source_handle 为 "true" 或 "false"，如果为 None 则默认为 "true"
                branch = edge.source_handle if edge.source_handle is not None else "true"
                conditional_edges[source_node][branch] = target_node
            else:
                # 普通边处理（包括指向 if_else 的边）
                # 注意：不要将多个入边作为并行边，而是单独添加
                if target_node not in parallel_edges:
                    parallel_edges[target_node] = []
                parallel_edges[target_node].append(source_node)

            # 检测特殊节点（开始节点、结束节点）
            if edge.source_type == NodeType.START.value:
                start_node = source_node
            if edge.target_type == NodeType.END.value:
                end_node = target_node

        # 5.设置开始和终点
        graph.set_entry_point(start_node)
        graph.set_finish_point(end_node)

        # 6.保留每条普通边，由节点运行器只等待当前执行路径中的前置节点。
        for target_node, source_nodes in parallel_edges.items():
            for source_node in source_nodes:
                graph.add_edge(source_node, target_node)

        # 7.添加条件边
        for if_else_node, branches in conditional_edges.items():
            # 创建条件函数，根据节点输出的 result 决定路径
            def create_condition_func(node_id):
                def condition_func(state: WorkflowState):
                    node_result = find_result(state, node_id)
                    result = node_result.outputs.get("result", True) if node_result else True
                    return "true" if result else "false"
                return condition_func

            # An unwired condition side means that branch terminates the workflow.
            path_map = {
                "true": branches.get("true", END),
                "false": branches.get("false", END),
            }
            graph.add_conditional_edges(
                if_else_node,
                create_condition_func(if_else_node),
                path_map
            )

        # 8.构建图程序并编译
        return graph.compile()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """工作流组件基础run方法"""
        # 1.调用工作流获取结果信息
        result = self._workflow.invoke({"inputs": kwargs})

        # 2.提取响应结果的outputs内容作为输出
        return result.get("outputs", {})

    def stream(
            self,
            input: Input,
            config: Optional[RunnableConfig] = None,
            **kwargs: Optional[Any],
    ) -> Iterator[Output]:
        """工作流流式输出每个节点对应的结果"""
        validated_input = self.args_schema.model_validate(input).model_dump(exclude_unset=True)
        return self._workflow.stream({"inputs": validated_input}, config=config)
