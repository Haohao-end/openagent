from uuid import uuid4

from internal.core.workflow.entities.node_entity import NodeType
from internal.core.workflow.nodes.llm.llm_entity import LLMNodeData


def test_llm_node_default_model_config_isolated_between_instances():
    first = LLMNodeData(id=uuid4(), node_type=NodeType.LLM, prompt="")
    second = LLMNodeData(id=uuid4(), node_type=NodeType.LLM, prompt="")

    first.language_model_config["parameters"]["temperature"] = 0.25

    assert second.language_model_config["parameters"]["temperature"] == 1
