/**
 * MCP server 工厂:负责创建实例并注册全部能力(tools / resources / prompts)
 * 与传输方式无关,stdio 或 HTTP 模式都复用这里
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerRequirementTools } from "./tools/requirement.js";

export function createMcpServer(): McpServer {
  const server = new McpServer({
    name: "requirement-mcp-server",
    version: "0.2.0",
  });

  // 注册工具(新增工具时在此挂载对应 register 函数)
  registerRequirementTools(server);

  // 注册资源:服务基本信息,供接入方查看
  server.registerResource(
    "server-info",
    "demo://info",
    {
      title: "服务器信息",
      description: "当前 MCP server 的基本信息",
      mimeType: "application/json",
    },
    async (uri) => ({
      contents: [
        {
          uri: uri.href,
          text: JSON.stringify(
            { name: "requirement-mcp-server", version: "0.2.0" },
            null,
            2
          ),
        },
      ],
    })
  );

  return server;
}
