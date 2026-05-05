<script setup lang="ts">
import { computed } from 'vue'
import CodeHighLight from '@/components/CodeHighLight.vue'
import {
  blockApiOutput,
  getBlockApiShell,
  streamApiOutput,
  getStreamApiShell,
  getContinueConversationShell,
  continueConversationOutput,
  getContinueConversationStreamShell,
  continueConversationStreamOutput,
} from '@/views/openapi/quick-start'

// 动态获取当前域名
const currentOrigin = computed(() => {
  return globalThis.location?.origin || 'http://localhost'
})

// 动态生成 API 端点
const apiEndpoint = computed(() => {
  return `${currentOrigin.value}/api/openapi/chat`
})

// 动态生成示例 URL
const exampleAppUrl = computed(() => {
  return `${currentOrigin.value}/space/apps/`
})

// 动态生成 Shell 命令
const blockApiShell = computed(() => getBlockApiShell(apiEndpoint.value))
const streamApiShell = computed(() => getStreamApiShell(apiEndpoint.value))
const continueConversationShell = computed(() => getContinueConversationShell(apiEndpoint.value))
const continueConversationStreamShell = computed(() => getContinueConversationStreamShell(apiEndpoint.value))
</script>

<template>
  <div class="pb-6">
    <div class="bg-white p-6 rounded-lg h-[calc(100vh-160px)] overflow-scroll scrollbar-w-none">
      <h2 class="text-xl text-gray-900 font-bold mb-4">概览</h2>
      <p class="text-gray-700 mb-6 leading-relaxed">
        OpenAgent API 是 OpenAgent 平台面向开发者提供的专业技术交互能力，致力于通过 API
        实现开发者更高效更全面的述求。OpenAgent API
        将提供更加灵活的和高精度的模型、工作流、知识库和扩展插件等能力的扩展，让定制化 Agent
        更加的精确、高效和智能。
      </p>

      <h2 class="text-xl text-gray-900 font-bold mb-4">准备工作</h2>
      <div class="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
        <p class="text-gray-700 mb-2">在开始之前，您需要完成以下准备：</p>
        <ol class="list-decimal list-inside text-gray-700 space-y-1 ml-2">
          <li>创建个人访问令牌（API Key）</li>
          <li>在 OpenAgent 平台上创建并发布 AI 应用</li>
          <li>获取应用的 app_id（从应用 URL 中获取）</li>
        </ol>
      </div>

      <h3 class="text-lg text-gray-900 font-semibold mb-3">如何获取 app_id？</h3>
      <div class="bg-gray-50 p-4 rounded-lg mb-6">
        <p class="text-gray-700 mb-2">app_id 是应用的唯一标识符，可以从Agent应用的 URL 中获取：</p>
        <div class="bg-white p-3 rounded border border-gray-200 mb-2">
          <code class="text-sm text-blue-600">{{ exampleAppUrl }}<span class="bg-yellow-200 font-semibold">f7826c92-c7b3-4dde-9fc2-a89788fb4936</span></code>
        </div>
        <p class="text-gray-600 text-sm">
          <span class="inline-block w-2 h-2 bg-yellow-400 rounded-full mr-1"></span>
          高亮部分即为 app_id（UUID 格式）
        </p>
      </div>

      <h2 class="text-xl text-gray-900 font-bold mb-4">API 端点</h2>
      <div class="bg-gray-50 p-4 rounded-lg mb-6">
        <p class="text-sm text-gray-600 mb-2">POST</p>
        <code class="text-base font-mono text-gray-900">{{ apiEndpoint }}</code>
      </div>

      <h2 class="text-xl text-gray-900 font-bold mb-4">请求参数</h2>
      <div class="overflow-x-auto mb-6">
        <table class="min-w-full border border-gray-200 rounded-lg">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b">参数名</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b">类型</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b">必填</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b">说明</th>
            </tr>
          </thead>
          <tbody class="bg-white">
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">app_id</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">必填</span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-700">应用的唯一标识符，从应用 URL 中获取</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">query</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">必填</span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-700">用户的问题或输入内容</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">stream</td>
              <td class="px-4 py-3 text-sm text-gray-700">boolean</td>
              <td class="px-4 py-3 text-sm">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">可选</span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-700">是否使用流式响应，默认 false</td>
            </tr>
            <tr class="border-b bg-blue-50">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">end_user_id</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">自动生成</span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-700">终端用户 ID，首次请求时自动生成，后续对话需传入</td>
            </tr>
            <tr class="border-b bg-blue-50">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">conversation_id</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">自动生成</span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-700">对话 ID，首次请求时自动生成，后续对话需传入以保持上下文</td>
            </tr>
            <tr class="border-b bg-blue-50">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">message_id</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">自动生成</span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-700">消息 ID，每次请求自动生成</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="bg-amber-50 border-l-4 border-amber-500 p-4 mb-6">
        <p class="text-sm text-gray-700">
          <span class="font-semibold">提示：</span>
          首次对话时，只需传入 <code class="bg-white px-1 py-0.5 rounded text-sm">app_id</code> 和 <code class="bg-white px-1 py-0.5 rounded text-sm">query</code>。
          后端会自动生成 <code class="bg-white px-1 py-0.5 rounded text-sm">end_user_id</code>、<code class="bg-white px-1 py-0.5 rounded text-sm">conversation_id</code> 和 <code class="bg-white px-1 py-0.5 rounded text-sm">message_id</code>。
          如需连续对话，请在后续请求中传入首次响应返回的 <code class="bg-white px-1 py-0.5 rounded text-sm">end_user_id</code> 和 <code class="bg-white px-1 py-0.5 rounded text-sm">conversation_id</code>。
        </p>
      </div>

      <h2 class="text-xl text-gray-900 font-bold mb-4">使用示例</h2>

      <a-tabs type="text" default-active-key="block">
        <a-tab-pane key="block" title="非流式对话">
          <div class="mb-4">
            <p class="text-gray-700 mb-2 font-medium">适用场景</p>
            <p class="text-gray-600 text-sm mb-4">适合需要一次性获取完整响应的场景，如批量处理、后台任务等。</p>
          </div>

          <p class="text-gray-700 mb-2 font-semibold">请求示例</p>
          <code-high-light language="shell">{{ blockApiShell }}</code-high-light>

          <p class="text-gray-700 mb-2 font-semibold">响应示例</p>
          <code-high-light language="json">{{ blockApiOutput }}</code-high-light>
        </a-tab-pane>

        <a-tab-pane key="stream" title="流式对话">
          <div class="mb-4">
            <p class="text-gray-700 mb-2 font-medium">适用场景</p>
            <p class="text-gray-600 text-sm mb-4">适合需要实时展示响应内容的场景，如聊天界面、实时问答等，提供更好的用户体验。</p>
          </div>

          <p class="text-gray-700 mb-2 font-semibold">请求示例</p>
          <code-high-light language="shell">{{ streamApiShell }}</code-high-light>

          <p class="text-gray-700 mb-2 font-semibold">响应示例（SSE 格式）</p>
          <code-high-light language="json">{{ streamApiOutput }}</code-high-light>
        </a-tab-pane>

        <a-tab-pane key="continue" title="连续对话">
          <div class="mb-4">
            <p class="text-gray-700 mb-2 font-medium">适用场景</p>
            <p class="text-gray-600 text-sm mb-4">需要保持对话上下文的多轮对话场景。通过传入 end_user_id 和 conversation_id 来维持对话历史。</p>
          </div>

          <div class="bg-green-50 border-l-4 border-green-500 p-4 mb-4">
            <p class="text-sm text-gray-700 mb-2">
              <span class="font-semibold">使用步骤：</span>
            </p>
            <ol class="list-decimal list-inside text-gray-700 text-sm space-y-1 ml-2">
              <li>首次请求时，只传入 app_id 和 query</li>
              <li>从响应中获取 end_user_id 和 conversation_id</li>
              <li>后续请求中带上这两个参数，即可实现连续对话</li>
            </ol>
          </div>

          <a-tabs type="text" default-active-key="continue-block">
            <a-tab-pane key="continue-block" title="非流式连续对话">
              <p class="text-gray-700 mb-2 font-semibold">请求示例</p>
              <code-high-light language="shell">{{ continueConversationShell }}</code-high-light>

              <p class="text-gray-700 mb-2 font-semibold mt-4">响应示例</p>
              <code-high-light language="json">{{ continueConversationOutput }}</code-high-light>

              <div class="bg-amber-50 border-l-4 border-amber-500 p-4 mt-4">
                <p class="text-sm text-gray-700">
                  <span class="font-semibold">关键点：</span>
                  AI 能够记住之前的对话内容（"你好"），并在回答中引用历史上下文。这就是连续对话的核心价值。
                </p>
              </div>
            </a-tab-pane>

            <a-tab-pane key="continue-stream" title="流式连续对话">
              <p class="text-gray-700 mb-2 font-semibold">请求示例</p>
              <code-high-light language="shell">{{ continueConversationStreamShell }}</code-high-light>

              <p class="text-gray-700 mb-2 font-semibold mt-4">响应示例（SSE 格式）</p>
              <code-high-light language="json">{{ continueConversationStreamOutput }}</code-high-light>

              <div class="bg-amber-50 border-l-4 border-amber-500 p-4 mt-4">
                <p class="text-sm text-gray-700">
                  <span class="font-semibold">关键点：</span>
                  流式输出会逐字推送响应内容，同时保持对话上下文。适合需要实时展示的聊天界面。
                </p>
              </div>
            </a-tab-pane>
          </a-tabs>

          <p class="text-gray-600 text-sm mt-4">
            <span class="inline-block w-2 h-2 bg-green-500 rounded-full mr-1"></span>
            注意：end_user_id 和 conversation_id 需要从首次对话的响应中获取
          </p>
        </a-tab-pane>
      </a-tabs>

      <h2 class="text-xl text-gray-900 font-bold mb-4 mt-8">响应字段说明</h2>
      <div class="overflow-x-auto mb-6">
        <table class="min-w-full border border-gray-200 rounded-lg">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b">字段名</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b">类型</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-gray-900 border-b">说明</th>
            </tr>
          </thead>
          <tbody class="bg-white">
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">answer</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm text-gray-700">AI 的完整回答内容</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">conversation_id</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm text-gray-700">对话 ID，用于后续连续对话</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">end_user_id</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm text-gray-700">终端用户 ID，用于后续连续对话</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">id</td>
              <td class="px-4 py-3 text-sm text-gray-700">string</td>
              <td class="px-4 py-3 text-sm text-gray-700">消息 ID</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">agent_thoughts</td>
              <td class="px-4 py-3 text-sm text-gray-700">array</td>
              <td class="px-4 py-3 text-sm text-gray-700">Agent 的思考过程，包含工具调用、推理等详细信息</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">latency</td>
              <td class="px-4 py-3 text-sm text-gray-700">number</td>
              <td class="px-4 py-3 text-sm text-gray-700">响应延迟（秒）</td>
            </tr>
            <tr class="border-b">
              <td class="px-4 py-3 text-sm font-mono text-gray-900">total_token_count</td>
              <td class="px-4 py-3 text-sm text-gray-700">number</td>
              <td class="px-4 py-3 text-sm text-gray-700">总 Token 消耗数</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2 class="text-xl text-gray-900 font-bold mb-4">常见问题</h2>
      <div class="space-y-4 mb-6">
        <div class="border border-gray-200 rounded-lg p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-2">Q: 如何实现连续对话？</h3>
          <p class="text-sm text-gray-700">
            A: 首次请求后，从响应中获取 <code class="bg-gray-100 px-1 py-0.5 rounded">end_user_id</code> 和 <code class="bg-gray-100 px-1 py-0.5 rounded">conversation_id</code>，
            在后续请求中带上这两个参数即可实现连续对话，系统会自动维护对话历史。
          </p>
        </div>

        <div class="border border-gray-200 rounded-lg p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-2">Q: 流式和非流式有什么区别？</h3>
          <p class="text-sm text-gray-700">
            A: 非流式会等待完整响应后一次性返回；流式会实时推送响应内容（SSE 格式），适合需要实时展示的场景，用户体验更好。
          </p>
        </div>

        <div class="border border-gray-200 rounded-lg p-4">
          <h3 class="text-base font-semibold text-gray-900 mb-2">Q: 为什么我的请求返回 401 错误？</h3>
          <p class="text-sm text-gray-700">
            A: 请检查 Authorization header 中的 API Key 是否正确，格式为 <code class="bg-gray-100 px-1 py-0.5 rounded">Bearer YOUR_API_KEY</code>。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped></style>
