import { Plugin } from "@opencode/plugin"
import { readdirSync, statSync } from "node:fs"
import type { Stats } from "node:fs"
import { isAbsolute, resolve } from "node:path"

// opencode V2：tool() 助手已移除，V1 的 .opencode/tools/*.ts 不会被加载。
// 工具必须通过插件的 ctx.tool.transform 注册；放在 .opencode/plugins/<名称>/index.ts（目录形式，单 .ts 文件会被跳过）。
// 参数 schema 从 Zod 改为纯 JSON Schema，execute 返回结构化内容 { content }。
export default Plugin.define({
  id: "show_artifact",
  async setup(ctx) {
    // transform 回调必须同步、可重放，故 fs 校验放在 execute 内
    await ctx.tool.transform((editor) => {
      editor.add({
        name: "show_artifact",
        description:
          "展示任意文件或目录产物供用户查看，不限文件类型。入参必须是已存在的绝对路径。只读、无副作用，不校验文件内容。",
        input: {
          type: "object",
          properties: {
            path: {
              type: "string",
              description: "文件或目录的绝对路径；目录展示其下全部文件",
            },
            subject: {
              type: "string",
              description: "文档的简短主题，据主题能看出这是什么文档，如「测试点清单」",
            },
          },
          required: ["path", "subject"],
          additionalProperties: false,
        },
        async execute(raw) {
          const { path, subject } = raw as { path: string; subject: string }
          if (!isAbsolute(path)) {
            throw new Error(`需要绝对路径：${path}`)
          }
          if (!subject.trim()) {
            throw new Error("主题不能为空")
          }
          const p = resolve(path)
          let st: Stats
          try {
            st = statSync(p)
          } catch {
            throw new Error(`路径不存在：${path}`)
          }
          // 目录：列出全部文件名
          if (st.isDirectory()) {
            const files = readdirSync(p).sort()
            if (!files.length) {
              throw new Error(`目录为空：${p}`)
            }
            return { content: `已就绪待查看【${subject}】：${p}（${files.length} 个文件：${files.join("、")}）` }
          }
          if (!st.isFile()) {
            throw new Error(`既不是文件也不是目录：${p}`)
          }
          return { content: `已就绪待查看【${subject}】：${p}` }
        },
      })
    })
  },
})
