import time
from typing import Optional
from langchain_core.runnables import RunnableConfig
from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from .if_else_entity import IfElseNodeData, ConditionOperator, LogicalOperator


class IfElseNode(BaseNode):
    """条件分支节点"""
    node_data: IfElseNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """条件分支节点，根据条件判断结果决定执行路径"""
        # 1.提取节点中的输入数据
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2.执行条件判断
        condition_result = self._evaluate_conditions(inputs_dict)

        # 3.构建输出数据（包含条件判断结果和输入数据的透传）
        outputs = {
            "result": condition_result,  # true 或 false
            **inputs_dict,  # 透传所有输入数据
        }

        # 4.构建响应状态并返回
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED.value,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }

    def _evaluate_conditions(self, inputs_dict: dict) -> bool:
        """评估所有条件，返回最终判断结果"""
        # 如果没有配置条件，默认返回 True
        if not self.node_data.conditions:
            return True

        # 评估每个条件
        condition_results = []
        for condition in self.node_data.conditions:
            # 获取变量值
            variable_value = inputs_dict.get(condition.variable_name, "")

            # 执行单个条件判断
            result = self._evaluate_single_condition(
                variable_value,
                condition.operator,
                condition.compare_value
            )
            condition_results.append(result)

        # 根据逻辑运算符合并结果
        if self.node_data.logical_operator == LogicalOperator.AND:
            return all(condition_results)
        else:  # OR
            return any(condition_results)

    def _evaluate_single_condition(
        self,
        variable_value: any,
        operator: ConditionOperator,
        compare_value: str
    ) -> bool:
        """评估单个条件"""
        # 转换为字符串进行比较（除了数值比较）
        var_str = str(variable_value) if variable_value is not None else ""

        # 数值运算符需要转换为数字
        numeric_operators = {
            ConditionOperator.GREATER_THAN,
            ConditionOperator.LESS_THAN,
            ConditionOperator.GREATER_THAN_OR_EQUAL,
            ConditionOperator.LESS_THAN_OR_EQUAL,
        }

        if operator in numeric_operators:
            try:
                var_num = float(var_str) if var_str else 0
                cmp_num = float(compare_value) if compare_value else 0

                if operator == ConditionOperator.GREATER_THAN:
                    return var_num > cmp_num
                elif operator == ConditionOperator.LESS_THAN:
                    return var_num < cmp_num
                elif operator == ConditionOperator.GREATER_THAN_OR_EQUAL:
                    return var_num >= cmp_num
                elif operator == ConditionOperator.LESS_THAN_OR_EQUAL:
                    return var_num <= cmp_num
            except (ValueError, TypeError):
                return False

        # 字符串运算符
        if operator == ConditionOperator.EQUALS:
            return var_str == compare_value
        elif operator == ConditionOperator.NOT_EQUALS:
            return var_str != compare_value
        elif operator == ConditionOperator.CONTAINS:
            return compare_value in var_str
        elif operator == ConditionOperator.NOT_CONTAINS:
            return compare_value not in var_str
        elif operator == ConditionOperator.STARTS_WITH:
            return var_str.startswith(compare_value)
        elif operator == ConditionOperator.ENDS_WITH:
            return var_str.endswith(compare_value)
        elif operator == ConditionOperator.IS_EMPTY:
            return len(var_str.strip()) == 0
        elif operator == ConditionOperator.IS_NOT_EMPTY:
            return len(var_str.strip()) > 0

        return False
