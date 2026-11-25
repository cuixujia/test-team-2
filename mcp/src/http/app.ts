/**
 * HTTP 传输层:Streamable HTTP + 会话管理
 * 每个 MCP 会话(initialize)对应一组 { server, transport },按 mcp-session-id 路由
 */
import { randomUUID } from "node:crypto";
import express, { type Express } from "express";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createMcpServer } from "../server.js";

export function buildApp(): Express {
  const app = express();
  app.use(express.json());

  // 会话表:mcp-session-id -> { server, transport }
  const sessions = new Map<
    string,
    { server: McpServer; transport: StreamableHTTPServerTransport }
  >();

  // POST /mcp:initialize 请求(无会话 ID)或后续 JSON-RPC 消息(带会话 ID)
  app.post("/mcp", async (req, res) => {
    const sessionId = req.headers["mcp-session-id"] as string | undefined;

    if (sessionId && sessions.has(sessionId)) {
      // 已有会话:交给对应 transport 处理
      const { transport } = sessions.get(sessionId)!;
      await transport.handleRequest(req, res, req.body);
      return;
    }

    if (sessionId) {
      // 带了未知/过期会话 ID:视为无效请求
      res.status(400).json({ error: "invalid or expired session id" });
      return;
    }

    // 无会话 ID:应为 initialize 请求,创建新会话
    const server = createMcpServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (sid) => {
        sessions.set(sid, { server, transport });
      },
    });
    // 会话关闭时清理
    transport.onclose = () => {
      if (transport.sessionId) sessions.delete(transport.sessionId);
    };
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  });

  // GET /mcp:服务端主动推送的通知流(SSE),按会话 ID 路由
  app.get("/mcp", async (req, res) => {
    const sessionId = req.headers["mcp-session-id"] as string | undefined;
    if (!sessionId || !sessions.has(sessionId)) {
      res.status(400).end("missing or invalid mcp-session-id");
      return;
    }
    await sessions.get(sessionId)!.transport.handleRequest(req, res);
  });

  // DELETE /mcp:终止会话
  app.delete("/mcp", async (req, res) => {
    const sessionId = req.headers["mcp-session-id"] as string | undefined;
    if (!sessionId || !sessions.has(sessionId)) {
      res.status(400).end("missing or invalid mcp-session-id");
      return;
    }
    await sessions.get(sessionId)!.transport.handleRequest(req, res);
  });

  return app;
}
