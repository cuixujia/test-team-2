import { tool } from "@opencode-ai/plugin"
import { readdirSync, statSync } from "node:fs"
import { isAbsolute, resolve } from "node:path"

export default tool({
  description:
    "展示任意文件或目录产物供用户查看，不限文件类型。入参必须是已存在的绝对路径。只读、无副作用，不校验文件内容。",
  args: {
    path: tool.schema
      .string()
      .describe("文件或目录的绝对路径；目录展示其下全部文件"),
    subject: tool.schema
      .string()
      .describe("文档的简短主题，据主题能看出这是什么文档，如「测试点清单」"),
  },
  async execute(args) {
    if (!isAbsolute(args.path)) {
      throw new Error(`需要绝对路径：${args.path}`)
    }
    if (!args.subject.trim()) {
      throw new Error("主题不能为空")
    }
    const p = resolve(args.path)
    // 不写内联类型注解：工具文件按纯 JS 加载，`import("node:fs").Stats` 会导致解析失败
    let st
    try {
      st = statSync(p)
    } catch {
      throw new Error(`路径不存在：${args.path}`)
    }
    if (st.isDirectory()) {
      const files = readdirSync(p).sort()
      if (!files.length) {
        throw new Error(`目录为空：${p}`)
      }
      return `已就绪待查看【${args.subject}】：${p}（${files.length} 个文件：${files.join("、")}）`
    }
    if (!st.isFile()) {
      throw new Error(`既不是文件也不是目录：${p}`)
    }
    return `已就绪待查看【${args.subject}】：${p}`
  },
})
