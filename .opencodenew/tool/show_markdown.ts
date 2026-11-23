import { tool } from "@opencode-ai/plugin"
import { readdirSync, statSync } from "node:fs"
import { isAbsolute, resolve } from "node:path"

// 仅收集可展示的文档文件，忽略其他杂项
const isDoc = (name: string) => name.endsWith(".md") || name.endsWith(".json")

export default tool({
  description:
    "展示 markdown 或 JSON 文件供用户查看，也支持传目录（列出目录内全部文档）。入参必须是已存在的绝对路径。只读、无副作用，不校验文件内容。",
  args: {
    path: tool.schema
      .string()
      .describe("文件或目录的绝对路径；文件须为 .md 或 .json，目录则展示其下全部 .md/.json 文件"),
  },
  async execute(args) {
    if (!isAbsolute(args.path)) {
      throw new Error(`需要绝对路径：${args.path}`)
    }
    const p = resolve(args.path)
    let st: import("node:fs").Stats
    try {
      st = statSync(p)
    } catch {
      throw new Error(`路径不存在：${args.path}`)
    }
    if (st.isDirectory()) {
      const files = readdirSync(p).filter(isDoc).sort()
      if (!files.length) {
        throw new Error(`目录下无 .md 或 .json 文件：${p}`)
      }
      return `已就绪待查看：${p}（${files.length} 个文件：${files.join("、")}）`
    }
    if (!st.isFile()) {
      throw new Error(`既不是文件也不是目录：${p}`)
    }
    if (!isDoc(p)) {
      throw new Error(`仅支持 .md 或 .json 文件：${args.path}`)
    }
    return `已就绪待查看：${p}`
  },
})
