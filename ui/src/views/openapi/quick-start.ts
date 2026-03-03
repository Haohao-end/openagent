// 动态生成 API Shell 命令
export const getBlockApiShell = (apiEndpoint: string) => `curl --location --request POST '${apiEndpoint}' \\
--header 'Authorization: Bearer YOUR_API_KEY' \\
--header 'Content-Type: application/json' \\
--data-raw '{
    "app_id": "f7826c92-c7b3-4dde-9fc2-a89788fb4936",
    "query": "你好",
    "stream": false
}'`

export const blockApiOutput = `{
  "code": "success",
  "data": {
    "agent_thoughts": [
      {
        "created_at": 0,
        "event": "agent_message",
        "id": "7afcd92b-e6db-43f0-a0ec-ced1a3ff44ff",
        "latency": 4.287119945976883,
        "observation": "",
        "thought": "你好！我是你的智能助手，随时准备为你提供帮助。无论是内容生成、问题解答，还是其他任务，我都会尽力为你提供准确、高效的服务。请告诉我你需要什么帮助吧！",
        "tool": "",
        "tool_input": {}
      },
      {
        "created_at": 0,
        "event": "agent_end",
        "id": "528277dd-e42f-490b-a789-503b3d8d4c1d",
        "latency": 0,
        "observation": "",
        "thought": "",
        "tool": "",
        "tool_input": {}
      }
    ],
    "answer": "你好！我是你的智能助手，随时准备为你提供帮助。无论是内容生成、问题解答，还是其他任务，我都会尽力为你提供准确、高效的服务。请告诉我你需要什么帮助吧！",
    "conversation_id": "8bc76677-9096-4e77-b46f-4e45cfbb6bd6",
    "end_user_id": "294eec6a-761f-4192-a0e7-71cf3defa7e8",
    "id": "c7f1868a-fe08-48a5-adef-a5e3dfbbca79",
    "image_urls": [],
    "latency": 4.287119945976883,
    "query": "你好",
    "total_token_count": 0
  },
  "message": ""
}`

export const getStreamApiShell = (apiEndpoint: string) => `curl --location --request POST '${apiEndpoint}' \\
--header 'Authorization: Bearer YOUR_API_KEY' \\
--header 'Content-Type: application/json' \\
--data-raw '{
    "app_id": "f7826c92-c7b3-4dde-9fc2-a89788fb4936",
    "query": "你好",
    "stream": true
}'`

// 连续对话 - 非流式
export const getContinueConversationShell = (apiEndpoint: string) => `curl --location --request POST '${apiEndpoint}' \\
--header 'Authorization: Bearer YOUR_API_KEY' \\
--header 'Content-Type: application/json' \\
--data-raw '{
    "app_id": "f7826c92-c7b3-4dde-9fc2-a89788fb4936",
    "query": "我上次说了什么",
    "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14",
    "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f",
    "stream": false
}'`

// 连续对话 - 非流式响应示例
export const continueConversationOutput = `{
  "code": "success",
  "data": {
    "agent_thoughts": [
      {
        "created_at": 0,
        "event": "agent_message",
        "id": "6aab9a7f-3d80-4c9b-97ea-b8be8e7b3b07",
        "latency": 2.0619137420435436,
        "observation": "",
        "thought": "根据当前的对话记录，你上次说的是"你好"。如果你有其他问题或需要进一步的帮助，请随时告诉我！",
        "tool": "",
        "tool_input": {}
      },
      {
        "created_at": 0,
        "event": "agent_end",
        "id": "34fd0861-73a2-420e-8411-2eb68bb73ab6",
        "latency": 0,
        "observation": "",
        "thought": "",
        "tool": "",
        "tool_input": {}
      }
    ],
    "answer": "根据当前的对话记录，你上次说的是"你好"。如果你有其他问题或需要进一步的帮助，请随时告诉我！",
    "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f",
    "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14",
    "id": "bb732c00-0c7c-4541-be0a-52139d624425",
    "image_urls": [],
    "latency": 2.0619137420435436,
    "query": "我上次说了什么",
    "total_token_count": 0
  },
  "message": ""
}`

// 连续对话 - 流式
export const getContinueConversationStreamShell = (apiEndpoint: string) => `curl --location --request POST '${apiEndpoint}' \\
--header 'Authorization: Bearer YOUR_API_KEY' \\
--header 'Content-Type: application/json' \\
--data-raw '{
    "app_id": "f7826c92-c7b3-4dde-9fc2-a89788fb4936",
    "query": "我上次说了什么",
    "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14",
    "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f",
    "stream": true
}'`

// 连续对话 - 流式响应示例
export const continueConversationStreamOutput = `event: agent_message
data:{"event": "agent_message", "thought": "根据", "observation": "", "tool": "", "tool_input": {}, "answer": "根据", "latency": 1.1744193939957768, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "当前", "observation": "", "tool": "", "tool_input": {}, "answer": "当前", "latency": 1.2800063659669831, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "的", "observation": "", "tool": "", "tool_input": {}, "answer": "的", "latency": 1.338575433997903, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "对话", "observation": "", "tool": "", "tool_input": {}, "answer": "对话", "latency": 1.4027361299959011, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "记录", "observation": "", "tool": "", "tool_input": {}, "answer": "记录", "latency": 1.4029896580032073, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "，", "observation": "", "tool": "", "tool_input": {}, "answer": "，", "latency": 1.4648058619932272, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "你", "observation": "", "tool": "", "tool_input": {}, "answer": "你", "latency": 1.4651480480097234, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "上次", "observation": "", "tool": "", "tool_input": {}, "answer": "上次", "latency": 1.549662350967992, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "说的", "observation": "", "tool": "", "tool_input": {}, "answer": "说的", "latency": 1.6466968989698216, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "是", "observation": "", "tool": "", "tool_input": {}, "answer": "是", "latency": 1.6470485519967042, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": """, "observation": "", "tool": "", "tool_input": {}, "answer": """, "latency": 1.656074781960342, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "你好", "observation": "", "tool": "", "tool_input": {}, "answer": "你好", "latency": 1.6563922339701094, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": """, "observation": "", "tool": "", "tool_input": {}, "answer": """, "latency": 1.7168029099702835, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_message
data:{"event": "agent_message", "thought": "。", "observation": "", "tool": "", "tool_input": {}, "answer": "。", "latency": 1.717183255997952, "id": "a83b83d7-b612-4578-883e-c50a90b816c8", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

event: agent_end
data:{"event": "agent_end", "thought": "", "observation": "", "tool": "", "tool_input": {}, "answer": "", "latency": 0, "id": "57f6cb90-0d78-4675-a6d3-ef7b51f74c18", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "36c71581-482e-4925-8df7-04017486644e", "task_id": "8bd7125e-8d59-4094-b636-17672ecdd73c"}

`

export const streamApiOutput = `event: agent_message
data:{"event": "agent_message", "thought": "你好", "observation": "", "tool": "", "tool_input": {}, "answer": "你好", "latency": 1.9211417119950056, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "！", "observation": "", "tool": "", "tool_input": {}, "answer": "！", "latency": 2.118086097005289, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "有什么", "observation": "", "tool": "", "tool_input": {}, "answer": "有什么", "latency": 2.2029259899863973, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "我可以", "observation": "", "tool": "", "tool_input": {}, "answer": "我可以", "latency": 2.302597103000153, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "帮助", "observation": "", "tool": "", "tool_input": {}, "answer": "帮助", "latency": 2.302920793008525, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "你的", "observation": "", "tool": "", "tool_input": {}, "answer": "你的", "latency": 2.3739777429727837, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "吗", "observation": "", "tool": "", "tool_input": {}, "answer": "吗", "latency": 2.3742488849675283, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "？", "observation": "", "tool": "", "tool_input": {}, "answer": "？", "latency": 2.432640825980343, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "", "observation": "", "tool": "", "tool_input": {}, "answer": "", "latency": 2.4338568289531395, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "", "observation": "", "tool": "", "tool_input": {}, "answer": "", "latency": 2.4353203380014747, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_message
data:{"event": "agent_message", "thought": "", "observation": "", "tool": "", "tool_input": {}, "answer": "", "latency": 2.7925649259705096, "id": "285999ab-bdf4-4521-9fd6-e6f88c7b194f", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

event: agent_end
data:{"event": "agent_end", "thought": "", "observation": "", "tool": "", "tool_input": {}, "answer": "", "latency": 0, "id": "24a15124-2a9f-4fee-b574-a470b6e40ac9", "end_user_id": "d1d619ac-43a3-4c71-82f9-3f2e00f39a14", "conversation_id": "06becaaf-4118-49ee-b2b2-2d87dd84004f", "message_id": "86786759-1fea-4183-ab3b-16597635a1bc", "task_id": "2f498258-9041-4f4c-b8e3-a3a92df6c977"}

`
