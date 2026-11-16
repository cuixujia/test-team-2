import { tool } from "@opencode-ai/plugin"
import { statSync } from "node:fs"
import { resolve } from "node:path"

export default tool({
  description:
    "展示一份 markdown 文件供用户查看。入参必须是已存在文件的绝对路径，返回其路径信息。只读、无副作用，不校验文件内容。",
  args: {
    path: tool.schema
      .string()
      .describe("markdown 文件的绝对路径，必须以 / 开头且已存在，扩展名为 .md"),
  },
  async execute(args) {
    const p = resolve(args.path)
    if (!p.endsWith(".md")) {
      throw new Error(`仅支持 .md 文件：${args.path}`)
    }
    let st: import("node:fs").Stats
    try {
      st = statSync(p)
    } catch {
      throw new Error(`文件不存在：${args.path}`)
    }
    if (!st.isFile()) {
      throw new Error(`不是文件：${p}`)
    }
    return `已就绪待查看：${p}`
  },
})
