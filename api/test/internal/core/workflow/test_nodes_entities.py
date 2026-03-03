from uuid import uuid4

import pytest
from pydantic import ValidationError

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import (
    VARIABLE_DESCRIPTION_MAX_LENGTH,
    VariableEntity,
)
from internal.core.workflow.nodes.dataset_retrieval.dataset_retrieval_entity import (
    DatasetRetrievalNodeData,
)
from internal.core.workflow.nodes.http_request.http_request_entity import (
    HttpRequestInputType,
    HttpRequestNodeData,
)
from internal.core.workflow.nodes.llm.llm_entity import LLMNodeData
from internal.core.workflow.nodes.parameter_extractor.parameter_extractor_entity import (
    ParameterExtractorNodeData,
)
from internal.core.workflow.nodes.template_transform.template_transform_entity import (
    TemplateTransformNodeData,
)
from internal.core.workflow.nodes.text_processor.text_processor_entity import TextProcessorNodeData
from internal.core.workflow.nodes.tool.tool_entity import ToolNodeData
from internal.core.workflow.nodes.variable_assigner.variable_assigner_entity import (
    VariableAssignerNodeData,
)
from internal.exception import FailException, ValidateErrorException


def test_base_node_data_should_raise_for_invalid_node_type():
    with pytest.raises(ValidationError, match="Invalid node type"):
        BaseNodeData(id=uuid4(), node_type="bad_type", title="node")


def test_variable_entity_should_normalize_empty_ref_node_id_and_truncate_description():
    entity = VariableEntity(
        name="query",
        description="x" * (VARIABLE_DESCRIPTION_MAX_LENGTH + 20),
        value={"type": "ref", "content": {"ref_node_id": "", "ref_var_name": "q"}},
    )

    assert entity.value.content.ref_node_id is None
    assert len(entity.description) == VARIABLE_DESCRIPTION_MAX_LENGTH


def test_variable_entity_should_raise_for_invalid_name():
    with pytest.raises(ValidateErrorException, match="变量名字仅支持"):
        VariableEntity(name="1-invalid", value={"type": "literal", "content": "x"})


def test_dataset_retrieval_node_data_should_validate_inputs_and_outputs():
    node_data = DatasetRetrievalNodeData(
        id=uuid4(),
        node_type="dataset_retrieval",
        title="retrieval",
        dataset_ids=[uuid4()],
        inputs=[VariableEntity(name="query", type="string", required=True)],
        outputs=[VariableEntity(name="custom", value={"type": "generated"})],
    )
    # 目前实现下 outputs 会保留调用方传入值，这里覆盖“自定义输出字段”分支。
    assert node_data.outputs[0].name == "custom"

    raw_validate_outputs = DatasetRetrievalNodeData.__dict__["validate_outputs"].__func__.wrapped.__func__
    assert raw_validate_outputs(DatasetRetrievalNodeData, [VariableEntity(name="x")])[0].name == "combine_documents"

    raw_validate_inputs = DatasetRetrievalNodeData.__dict__["validate_inputs"].__func__.wrapped.__func__
    with pytest.raises(FailException, match="输入变量信息出错"):
        raw_validate_inputs(DatasetRetrievalNodeData, [])

    with pytest.raises(FailException, match="变量名字/变量类型/必填属性出错"):
        raw_validate_inputs(
            DatasetRetrievalNodeData,
            [VariableEntity(name="q", type="int", required=False)],
        )
    valid_inputs = [VariableEntity(name="query", type="string", required=True)]
    assert raw_validate_inputs(DatasetRetrievalNodeData, valid_inputs) == valid_inputs


def test_http_request_node_data_should_normalize_url_outputs_and_validate_inputs():
    node_data = HttpRequestNodeData(
        id=uuid4(),
        node_type="http_request",
        title="http",
        url="",
        inputs=[
            VariableEntity(
                name="q",
                value={"type": "literal", "content": "x"},
                meta={"type": HttpRequestInputType.PARAMS},
            )
        ],
        outputs=[VariableEntity(name="x", value={"type": "generated"})],
    )
    assert node_data.url is None
    assert [item.name for item in node_data.outputs] == ["status_code", "text"]

    with pytest.raises(ValidateErrorException, match="Http请求参数结构出错"):
        HttpRequestNodeData(
            id=uuid4(),
            node_type="http_request",
            title="http",
            url="https://api.example.com",
            inputs=[
                VariableEntity(
                    name="q",
                    value={"type": "literal", "content": "x"},
                    meta={"type": "invalid-type"},
                )
            ],
        )


@pytest.mark.parametrize("outputs_value", [None, [], "invalid"])
def test_tool_node_data_should_fallback_default_outputs(outputs_value):
    node_data = ToolNodeData(
        id=uuid4(),
        node_type="tool",
        title="tool",
        type="builtin_tool",
        provider_id="provider",
        tool_id="tool",
        outputs=outputs_value,
    )
    assert len(node_data.outputs) == 1
    assert node_data.outputs[0].name == "text"


def test_llm_and_template_node_data_should_force_default_output():
    llm_data = LLMNodeData(
        id=uuid4(),
        node_type="llm",
        title="llm",
        prompt="Hello",
        outputs=[VariableEntity(name="x", value={"type": "generated"})],
    )
    template_data = TemplateTransformNodeData(
        id=uuid4(),
        node_type="template_transform",
        title="tpl",
        template="{{x}}",
        outputs=[VariableEntity(name="x", value={"type": "generated"})],
    )

    assert llm_data.outputs[0].name == "output"
    assert template_data.outputs[0].name == "output"


def test_text_processor_node_data_should_force_default_outputs_and_validate_inputs():
    node_data = TextProcessorNodeData(
        id=uuid4(),
        node_type="text_processor",
        title="text",
        outputs=[VariableEntity(name="x", value={"type": "generated"})],
    )
    assert [item.name for item in node_data.outputs] == ["output", "length"]

    with pytest.raises(ValidateErrorException, match="至少需要1个输入变量"):
        TextProcessorNodeData(id=uuid4(), node_type="text_processor", title="text", inputs=[])

    with pytest.raises(ValidateErrorException, match="仅支持STRING"):
        TextProcessorNodeData(
            id=uuid4(),
            node_type="text_processor",
            title="text",
            inputs=[VariableEntity(name="text", type="int", value={"type": "literal", "content": 1})],
        )


def test_variable_assigner_node_data_should_generate_outputs_from_inputs():
    node_data = VariableAssignerNodeData(
        id=uuid4(),
        node_type="variable_assigner",
        title="assigner",
        inputs=[
            VariableEntity(name="name", type="string", value={"type": "literal", "content": "alice"}),
            VariableEntity(name="age", type="int", value={"type": "literal", "content": 18}),
        ],
    )

    assert [item.name for item in node_data.outputs] == ["name", "age"]
    assert [item.type for item in node_data.outputs] == ["string", "int"]
    assert all(item.value.type == "generated" for item in node_data.outputs)

    with pytest.raises(ValidateErrorException, match="至少需要1个输入变量"):
        VariableAssignerNodeData(id=uuid4(), node_type="variable_assigner", title="assigner", inputs=[])

    with pytest.raises(ValidateErrorException, match="名字不能重复"):
        VariableAssignerNodeData(
            id=uuid4(),
            node_type="variable_assigner",
            title="assigner",
            inputs=[
                VariableEntity(name="dup", type="string", value={"type": "literal", "content": "a"}),
                VariableEntity(name="dup", type="int", value={"type": "literal", "content": 1}),
            ],
        )


def test_parameter_extractor_node_data_should_validate_inputs_and_outputs():
    node_data = ParameterExtractorNodeData(
        id=uuid4(),
        node_type="parameter_extractor",
        title="extractor",
        outputs=[
            {"name": "name", "type": "string", "required": True},
            {"name": "age", "type": "int", "required": False},
        ],
    )

    assert [item.name for item in node_data.outputs] == ["name", "age"]
    assert all(item.value.type == "generated" for item in node_data.outputs)

    with pytest.raises(ValidateErrorException, match="至少需要1个输入变量"):
        ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            inputs=[],
            outputs=[{"name": "name", "type": "string"}],
        )

    with pytest.raises(ValidateErrorException, match="仅支持STRING"):
        ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            inputs=[VariableEntity(name="text", type="int", value={"type": "literal", "content": 1})],
            outputs=[{"name": "name", "type": "string"}],
        )

    with pytest.raises(ValidateErrorException, match="至少需要1个输出变量"):
        ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            outputs=[],
        )

    with pytest.raises(ValidateErrorException, match="名字不能重复"):
        ParameterExtractorNodeData(
            id=uuid4(),
            node_type="parameter_extractor",
            title="extractor",
            outputs=[
                {"name": "dup", "type": "string"},
                {"name": "dup", "type": "int"},
            ],
        )
