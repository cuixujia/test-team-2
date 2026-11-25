/**
 * 程序入口:只负责组装与启动
 * MCP 能力定义见 server.ts,HTTP 传输与会话管理见 http/app.ts
 */
import { buildApp } from "./http/app.js";

const PORT = Number(process.env.PORT ?? 18080);

buildApp().listen(PORT, () => {
  console.log(`[requirement-mcp-server] listening on http://0.0.0.0:${PORT}/mcp`);
});
