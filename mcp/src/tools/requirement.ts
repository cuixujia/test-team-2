/**
 * 工具:根据需求 ID 查询需求详情
 * 约定:每个工具一个文件,mock 数据就近放置;
 * 接真实需求系统时,把取数逻辑抽到独立的 api/ 模块,本文件只改调用处
 */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

// 需求详情结构
interface RequirementDetail {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  assignee: string;
  createdAt: string;
  dueDate: string;
}

// mock 数据表
const MOCK_REQUIREMENTS: Record<string, RequirementDetail> = {
  "REQ-1001": {
    id: "REQ-1001",
    title: "登录页支持手机验证码登录",
    description: "在现有账号密码登录基础上,增加手机号 + 短信验证码登录方式,验证码 5 分钟有效。",
    status: "开发中",
    priority: "P1",
    assignee: "张三",
    createdAt: "2026-11-10",
    dueDate: "2026-12-05",
  },
  "REQ-1002": {
    id: "REQ-1002",
    title: "订单列表分页性能优化",
    description: "订单量超 10 万后列表加载缓慢,需优化查询 SQL 并引入游标分页。",
    status: "待测试",
    priority: "P2",
    assignee: "李四",
    createdAt: "2026-11-15",
    dueDate: "2026-12-15",
  },
};

export function registerRequirementTools(server: McpServer): void {
  server.registerTool(
    "get_requirement_detail",
    {
      title: "查询需求详情",
      description:
        "根据需求 ID 查询需求详情,返回标题、描述、状态、优先级、负责人、创建时间与截止时间。需求 ID 形如 REQ-1001。",
      inputSchema: {
        requirementId: z.string().describe("需求 ID,例如 REQ-1001"),
      },
    },
    async ({ requirementId }) => {
      const detail = MOCK_REQUIREMENTS[requirementId];
      // 未命中时返回错误内容,便于模型理解并纠正参数
      if (!detail) {
        return {
          content: [{ type: "text", text: `未找到需求:${requirementId}` }],
          isError: true,
        };
      }
      return {
        content: [{ type: "text", text: JSON.stringify(detail, null, 2) }],
      };
    }
  );
}
