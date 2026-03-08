---
name: pdf-to-markdown
description: PDF 转 Markdown 原子能力。基于 pdfjs-dist 提取 PDF 文本，通过启发式算法还原段落结构，输出干净的 Markdown。
allowed-tools: Bash
---

将 PDF 文件转换为结构化 Markdown 文本。

## 用法

```bash
bun skills/pdf-to-markdown/pdf-to-markdown.ts <input.pdf> [password]
```

输出文件自动生成在 PDF 同目录，扩展名替换为 `.md`。

## 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `<input.pdf>` | 是 | PDF 文件路径 |
| `[password]` | 否 | 加密 PDF 的密码 |

## 依赖

```bash
bun add pdfjs-dist
```

仅依赖 `pdfjs-dist`（Mozilla PDF.js），无其他外部依赖。

## 转换流程

```
PDF → 提取文本项 → 按 Y 坐标组行 → 启发式段落合并 → Markdown
```

| 步骤 | 函数 | 说明 |
|------|------|------|
| 提取 | `extractPdfText()` | 解析 PDF 页面，过滤页眉页脚、页码 |
| 组行 | `groupTextIntoLines()` | 按 Y 坐标聚合分散文本为视觉行 |
| 组装 | `assembleMarkdown()` | 判断段落边界，输出 Markdown |

## 可调参数

脚本内 `CONFIG` 对象控制启发式行为，按需调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `lineYTolerance` | 2.0 | 同行文本的垂直容差（px） |
| `paraGapMultiplier` | 1.5 | 段落间隙 = 中位行距 × 此倍数 |
| `shortLineRatio` | 0.85 | 行宽 < 最大行宽 × 此值视为短行（段尾） |
| `headerY` | 810 | 高于此 Y 坐标的内容视为页眉 |
| `footerY` | 45 | 低于此 Y 坐标的内容视为页脚 |

## 示例

```bash
# 基础转换
bun skills/pdf-to-markdown/pdf-to-markdown.ts knowledge/notes/report.pdf

# 加密 PDF
bun skills/pdf-to-markdown/pdf-to-markdown.ts secret.pdf mypassword
```

## 移植到其他项目

复制整个 `.gemini/skills/pdf-to-markdown/` 目录到目标项目，然后：

```bash
cd target-project
bun add pdfjs-dist
bun skills/pdf-to-markdown/pdf-to-markdown.ts <file.pdf>
```

## 局限

- 纯文本提取，不处理图片和表格
- 启发式段落检测，复杂排版（多栏、混排）可能需要调 CONFIG
- 中文优化：中文拼接不加空格，英文拼接加空格
