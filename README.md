<p align="center">
  <img src="https://img.shields.io/badge/Agent%20Skill-v1.0-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/AI-Doubao%20%7C%20ChatGPT%20%7C%20DeepSeek%20%7C%20Gemini-orange?style=flat-square" alt="AI">
</p>

<h1 align="center">🤖 AI Chat Record Exporter</h1>

<p align="center">
  <b>批量导出 AI 聊天记录到 Obsidian</b> — 支持豆包、ChatGPT、DeepSeek、Gemini、通义千问等主流 AI 平台。<br>
  两步自动化流程：发现会话 → 批量提取，一键输出结构化 Markdown。
</p>

<p align="center">
  <i>Requires <a href="https://github.com/kimi-webbridge">Kimi WebBridge</a> browser automation daemon.</i>
</p>

---

## 📊 为什么需要这个工具

| 对比 | AI Chat Exporter | 手动复制粘贴 |
|------|-----------------|-------------|
| 单次导出量 | **全部会话** | 一个对话 |
| 提取内容 | 消息 + 思考过程 + 图片 | 纯文本 |
| 输出格式 | **结构化 Markdown**（Obsidian 就绪） | 散乱文本 |
| 恢复支持 | ✅ 断电续传 | ❌ |
| 去重处理 | ✅ 自动处理重名 | ❌ |
| 耗时 (100条) | **~5分钟** | 数小时 |

---

## ✨ 功能特性

- **多平台支持** — 豆包、ChatGPT、DeepSeek、Gemini、通义千问等
- **两阶段架构** — 发现（收集 URL）→ 提取（导出对话），职责分离
- **浏览器自动化** — 基于 Kimi WebBridge，真实浏览器渲染，无需 API Key
- **智能角色识别** — 自动区分用户消息和 AI 回复
- **思考过程捕获** — 支持提取 AI 推理链 / thinking box 内容
- **图片下载** — 通过 PerformanceObserver 捕获签名 URL，解决防盗链
- **懒加载处理** — 逐条滚动触发图片延迟加载，确保完整采集
- **断点续传** — 进度文件记录，中断后可继续
- **文件名去重** — 自动处理同名对话，避免覆盖
- **单一标签页** — 全程复用同一个浏览器标签页，无内存爆炸

---

## 🚀 快速开始

### 前置条件

```bash
# 1. 安装 Kimi WebBridge
# 详见 https://github.com/kimi-webbridge

# 2. 确认 daemon 运行中
~/.kimi-webbridge/bin/kimi-webbridge status
# 输出: running: true, extension_connected: true

# 3. API 端点
# http://127.0.0.1:10086/command
```

### WorkBuddy 用户（推荐）

在 WorkBuddy 中加载该技能后，直接触发：

```
/ai-chat-export                 # 开始导出（将引导你完成两阶段）
/导出聊天记录                    # 同上，中文触发
"导出豆包聊天记录"                # 自然语言触发
```

### 手动运行

```bash
# Phase 1: 发现会话
python scripts/discover_template.py

# Phase 2: 批量提取
python scripts/extract_template.py

# 输出目录结构
# ./output/
# ├── conversations.json        # 会话 URL 列表
# ├── progress.json             # 进度文件
# ├── 对话标题1.md              # 导出结果
# ├── 对话标题2.md
# └── images/
#     ├── 对话标题1_0.png
#     └── 对话标题1_1.png
```

---

## 🏗️ 两阶段架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Phase 1: Discovery                       │
│                                                              │
│  ┌──────────────┐    ┌─────────────────┐    ┌────────────┐  │
│  │ Open sidebar  │ →  │ Scroll to bottom │ →  │ Collect    │  │
│  │ of chat list  │    │ (detect new      │    │ all URLs   │  │
│  │               │    │  links in loop)  │    │ → json    │  │
│  └──────────────┘    └─────────────────┘    └────────────┘  │
│                           ↻ until no new links               │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Phase 2: Extraction                        │
│                                                              │
│  ┌──────────────┐    ┌─────────────────┐    ┌────────────┐  │
│  │ For each URL  │ →  │ Scroll messages  │ →  │ Extract     │  │
│  │ navigate      │    │ trigger images   │    │ text + img  │  │
│  │               │    │ detect roles     │    │ → Markdown │  │
│  └──────────────┘    └─────────────────┘    └────────────┘  │
│                           ↻ batch loop                        │
└─────────────────────────────────────────────────────────────┘
```

### Phase 1: 发现（Discovery）

自动滚动侧边栏，收集全部对话链接：

| 参数 | 说明 | 豆包示例 |
|------|------|---------|
| `CHAT_LIST_URL` | 会话列表页 URL | `https://www.doubao.com/chat/` |
| `SIDEBAR_SCROLL_SELECTOR` | 可滚动的侧边栏容器 | `[class*=flow-scrollbar]` |
| `LINK_MATCH_PATTERN` | 对话 URL 匹配正则 | `/\/chat/\d+/` |

输出：`conversations.json` — 包含所有 `{title, href}` 的完整列表。

### Phase 2: 提取（Extraction）

逐条处理每个对话，提取完整内容：

| 参数 | 说明 | 豆包示例 |
|------|------|---------|
| `MESSAGE_LIST_SELECTOR` | 消息列表滚动容器 | `[class*=v_list_scroller]` |
| `MESSAGE_ITEM_SELECTOR` | 单条消息容器 | `[class*=inner-item]` |
| `THINKING_SELECTOR` | 思考过程框 | `[class*=thinking-box]` |
| `IMAGE_DOMAIN` | 图片 CDN 域名 | `byteimg.com` |

---

## 📄 输出格式

每个对话导出为独立 Markdown 文件，Obsidian 原生支持：

```markdown
# 对话标题

> 来源: https://platform.com/chat/12345

---

### **[用户]**
用户消息内容...

---

### **[豆包AI]**
> [!NOTE]- 思考过程
> AI 推理过程内容...

AI 回复内容...

![image](images/对话标题_0.png)
```

---

## 🔧 适配新平台

支持添加任意 AI 平台的导出能力。填写以下对照表后，修改配置即可：

| 待填项 | 查找方式 |
|--------|---------|
| 侧边栏 CSS 选择器 | 浏览器 F12 → Elements |
| 消息容器 CSS 选择器 | 检查 2-3 条消息的公共父级 |
| 用户/AI 角色区分逻辑 | 对比用户消息和 AI 消息的 HTML 差异 |
| 图片 CDN 域名 | 查看图片 URL 中的域名 |
| 思考过程容器 | 检查 AI 回复中的特殊折叠区域 |

---

## 🧩 项目结构

```
📁 doubao-chat-export/
├── SKILL.md                          # WorkBuddy 技能定义
├── scripts/
│   ├── discover_template.py          # 发现阶段脚本模板
│   └── extract_template.py           # 提取阶段脚本模板
└── .gitignore
```

---

## 📋 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 找不到滚动容器 | CSS 选择器不匹配 | 用 F12 重新检查 DOM |
| 图片下载为 403 | 签名 URL 过期 | 使用 PerformanceObserver 捕获最新签名 |
| 所有消息标记为 AI | 角色检测逻辑错误 | 检查用户/AI 消息 HTML 差异 |
| 同名文件覆盖 | 相同标题的对话 | 自动追加 URL ID 后缀（已内置） |
| 超时失败 | 对话过长 | 已内置 try/catch 处理，不会阻塞后续 |

---

## 📜 许可证

MIT
