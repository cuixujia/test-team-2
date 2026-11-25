/**
 * 验证脚本:通过 Streamable HTTP 连接本机的 MCP server
 * 运行方式(两个终端):
 *   1. npm run start
 *   2. npm run test:client
 */
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const url = new URL(process.env.MCP_URL ?? "http://127.0.0.1:18080/mcp");
const client = new Client({ name: "test-client", version: "0.0.2" });
await client.connect(new StreamableHTTPClientTransport(url));

// 列出能力
const { tools } = await client.listTools();
const { resources } = await client.listResources();
console.log("tools:", tools.map((t) => t.name).join(", "));
console.log("resources:", resources.map((r) => r.uri).join(", "));

// 命中 mock 数据
const hit = await client.callTool({
  name: "get_requirement_detail",
  arguments: { requirementId: "REQ-1001" },
});
console.log("REQ-1001 ->\n" + hit.content[0].text);

// 未命中场景
const miss = await client.callTool({
  name: "get_requirement_detail",
  arguments: { requirementId: "REQ-9999" },
});
console.log("REQ-9999 ->", miss.content[0].text, "| isError:", miss.isError === true);

await client.close();
console.log("OK: HTTP 链路验证通过");
