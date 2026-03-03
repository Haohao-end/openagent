import os
import time
import json
import requests
from typing import Optional, ClassVar
from langchain_core.runnables import RunnableConfig
from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException
from .code_entity import CodeNodeData


class CodeNode(BaseNode):
    """Python代码运行节点"""
    node_data: CodeNodeData
    
    # 腾讯云函数沙箱地址
    Sandbox_URL: ClassVar[str] = os.getenv("SANDBOX_URL").rstrip("/")

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """Python代码运行节点，执行的代码函数名字必须为main，并且参数名为params，有且只有一个参数，通过腾讯云函数沙箱执行"""
        # 1.从状态中提取输入数据
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2.通过腾讯云函数沙箱执行Python代码
        result = self._execute_function(self.node_data.code, params=inputs_dict)

        # 3.检测函数的返回值是否为字典
        if not isinstance(result, dict):
            raise FailException("main函数的返回值必须是一个字典")

        # 4.提取输出数据
        outputs_dict = {}
        outputs = self.node_data.outputs
        for output in outputs:
            # 5.提取输出数据(非严格校验)
            outputs_dict[output.name] = result.get(
                output.name,
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output.type),
            )

        # 6.构建状态数据并返回
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED.value,
                    inputs=inputs_dict,
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }

    @classmethod
    def _execute_function(cls, code: str, *args, **kwargs):
        """通过腾讯云函数沙箱执行Python代码"""
        try:
            # 1.检查沙箱URL是否配置
            if not cls.Sandbox_URL:
                raise FailException("SANDBOX_URL环境变量未配置")

            # 2.构建请求参数
            # 优先支持传入 params=... 的场景（你的 invoke 会传 params=inputs_dict）
            payload_args = []
            payload_kwargs = {}

            # 如果调用时显式传入 params（常用约定），把它作为第一个位置参数传递
            if "params" in kwargs:
                payload_args = [kwargs.pop("params")]
            else:
                # 如果调用时传了位置参数，就直接传这些位置参数
                if args:
                    # args 可能是元组，转换为 list
                    payload_args = list(args)

            # 其余剩下的 kwargs 一并透传（若为空，则传空对象）
            payload_kwargs = kwargs or {}

            payload = {
                "code": code,
                "func_name": "main",   # 强制要求 main
                "args": payload_args,
                "kwargs": payload_kwargs,
            }

            # 3.发送POST请求到腾讯云函数
            response = requests.post(
                cls.Sandbox_URL.rstrip("/"),
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            # 4.检查HTTP响应状态
            # 若非 200，尝试解析 body 中的错误信息并返回更友好的异常
            if response.status_code != 200:
                # 尝试解析 json body（若能解析）
                try:
                    resp_json = response.json()
                except Exception:
                    resp_json = {"raw_text": response.text}
                raise FailException(f"云函数执行失败，状态码: {response.status_code}，响应: {resp_json}")

            # 5.解析响应结果
            try:
                response_data = response.json()
            except Exception as e:
                raise FailException(f"云函数返回非JSON内容: {str(e)}，原文: {response.text}")

            # 6.检查是否有错误信息
            if "error" in response_data:
                # 如果 trace 可用也带上
                tb = response_data.get("traceback")
                if tb:
                    raise FailException(f"代码执行出错: {response_data['error']}\n{tb}")
                else:
                    raise FailException(f"代码执行出错: {response_data['error']}")

            # 7.返回执行结果（期望 cloud 返回 {"result": ...}）
            if "result" in response_data:
                return response_data["result"]
            else:
                raise FailException(f"云函数返回数据格式错误: {response_data}")

        except FailException:
            raise
        except requests.exceptions.Timeout:
            raise FailException("云函数执行超时")
        except requests.exceptions.RequestException as e:
            raise FailException(f"网络请求失败: {str(e)}")
        except Exception as e:
            raise FailException(f"Python代码执行出错: {str(e)}")
