from uuid import uuid4

from internal.core.agent.entities.agent_entity import AgentConfig


def test_agent_config_default_review_config_isolated_between_instances():
    first = AgentConfig(user_id=uuid4())
    second = AgentConfig(user_id=uuid4())

    first.review_config["inputs_config"]["enable"] = True

    assert second.review_config["inputs_config"]["enable"] is False
