---
name: ai-chat-exporter
description: |
  AI 聊天记录批量导出到 Obsidian。支持豆包、DeepSeek、ChatGPT、Gemini、通义千问等主流 AI 平台。
  两步流程：(1) 发现阶段：滚动侧边栏抓取全部对话 URL；(2) 提取阶段：逐条抓取消息、思考过程、图片，转 Markdown。
  触发方式：/ai-chat-export、/导出聊天记录、"导出豆包/ChatGPT 聊天记录"、"批量下载 AI 对话"
  前置依赖：Kimi WebBridge 浏览器助手必须已就绪（/kimi-webbridge status）。
---

# AI Chat Record Exporter

Two-phase browser automation for bulk exporting AI chat records to Obsidian.

## Prerequisites

Kimi WebBridge daemon + extension must be running. Check:

```bash
~/.kimi-webbridge/bin/kimi-webbridge status
# requires: running: true, extension_connected: true
```

API endpoint: `http://127.0.0.1:10086/command`

## Two-Phase Workflow

```
Phase 1: DISCOVERY          Phase 2: EXTRACTION
┌─────────────────┐         ┌──────────────────┐
│ Scroll sidebar   │  ──→    │ For each URL:     │
│ Collect all URLs │         │  Navigate         │
│ → urls.json      │         │  Scroll messages  │
└─────────────────┘         │  Extract text/img │
                             │  Convert to .md   │
                             └──────────────────┘
```

## Phase 1: Discovery

The agent must write and run a discovery script specific to the target platform.

### Generic discovery script template

Use `scripts/discover_template.py` as starting point. The agent MUST adapt these per platform:

| Parameter | How to find | Example (Doubao) |
|-----------|-------------|-------------------|
| `CHAT_LIST_URL` | Platform's main chat page | `https://www.doubao.com/chat/` |
| `SIDEBAR_SCROLL_SELECTOR` | Scrollable sidebar container | `[class*=flow-scrollbar]` |
| `LINK_MATCH_PATTERN` | Regex to match conversation URLs | `/\/chat\/\d+/` |
| `SESSION_NAME` | Unique WebBridge session | `"doubao-discover"` |

### The agent must follow this protocol:

1. Navigate to `CHAT_LIST_URL` with `newTab:true`
2. Wait 6s for page load
3. Run JS via `evaluate` that:
   - Finds `SIDEBAR_SCROLL_SELECTOR`
   - Loops: scroll to bottom → wait 1.2s → collect new links matched by `LINK_MATCH_PATTERN`
   - Breaks after 5 consecutive iterations with no new links
   - Returns JSON `{total, items: [{title, href}]}`
4. Save to `conversations.json` in the output directory

### Agent checklist for discovery:
- [ ] WebBridge healthy
- [ ] Navigate to chat list page
- [ ] Use `snapshot` to inspect DOM, identify sidebar scroller and link pattern
- [ ] Write platform-specific discovery script
- [ ] Run it, verify count matches expectation
- [ ] Save complete URL list

## Phase 2: Extraction

### Core extraction script

Use `scripts/extract_template.py` as starting point. The agent MUST adapt these per platform:

| Parameter | How to find | Example (Doubao) |
|-----------|-------------|-------------------|
| `MESSAGE_LIST_SELECTOR` | Scrollable message container | `[class*=v_list_scroller]` |
| `MESSAGE_ITEM_SELECTOR` | Individual message wrapper | `[class*=inner-item]` |
| `ROLE_DETECTION_LOGIC` | JS logic to detect user vs AI | See Doubao example below |
| `THINKING_SELECTOR` | Thinking/reasoning box (optional) | `[class*=thinking-box]` |
| `IMAGE_DOMAIN` | Image CDN domain for URL capture | `byteimg.com` |
| `IMAGE_LAZY_SELECTOR` | Lazy-loaded image wrappers | `[class*=image-wrapper]` |

### Role detection (platform-specific, must adapt)

Doubao example:
```javascript
var hasBubble = html.indexOf("bg-g-send-msg-bubble-bg") > -1;
var hasCopyTelemetry = html.indexOf("data-copy-telemetry") > -1;
var hasJustifyEnd = html.indexOf("justify-end") > -1;
var role = (hasBubble || (!hasCopyTelemetry && hasJustifyEnd)) ? "user" : "ai";
```

General approach: inspect 2-3 messages in the browser, compare their HTML structure, find a distinguishing attribute or class.

### Per-message scroll protocol (critical for image lazy-loading)

```
For each message:
  1. scrollIntoView({block:"center"})
  2. Wait 1500ms
  3. For each image-wrapper inside message:
     a. scrollIntoView({block:"center"})
     b. Wait 1500ms
  4. Poll for <source>/<img> tags with real URLs (up to 5s, 500ms intervals)
  5. Break when real URLs found, or no images expected
```

### PerformanceObserver for signed URLs (recommended)

Some platforms (Doubao) serve images with signed URLs that only appear in network requests. Use `PerformanceObserver`:

```javascript
var observer = new PerformanceObserver(function(list) {
  list.getEntries().forEach(function(e) {
    if (e.name.indexOf("IMAGE_DOMAIN") > -1) {
      // collect signed URL
    }
  });
});
observer.observe({type: "resource", buffered: true});
```

### HTML to Markdown conversion

The extract script includes `html_to_markdown()`. When adapting: test on 3 diverse messages, check for platform-specific HTML patterns, add rules as needed.

### Batch processing must-haves:

- **Single tab reuse**: First `navigate` uses `newTab:true`, all subsequent use `newTab:false`
- **Resume support**: Save progress to `progress.json` every N conversations
- **Timeout handling**: Wrap `curl_post` in try/catch for `TimeoutExpired`
- **Duplicate filename handling**: Append URL ID suffix when sanitized titles collide
- **Skip existing**: Check `.md` files already in output directory before processing

### Troubleshooting table

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `no scroller` | Wrong CSS selector | Use `snapshot` + browser inspect to find correct selector |
| `no messages` | Empty conversation | Skip, mark as failed |
| 0 images on conversations known to have images | Lazy loading not triggered | Increase per-message wait, check image-wrapper selector |
| `TimeoutExpired` | Very long conversation | Accept failure, move on (marked in progress) |
| 403 on image download | Signed URLs expired | Use PerformanceObserver URLs (fresher signatures) |
| All messages labeled "ai" | Role detection wrong | Inspect HTML of user vs AI messages, fix detection logic |
| Duplicate .md files overwritten | Same title for different conversations | Append chat ID suffix to colliding filenames |

## Output format

Each `.md` file:
```markdown
# Conversation Title

> 来源: https://platform.com/chat/12345

---

### **[用户]**
User message content...

---

### **[豆包AI]**
> [!NOTE]- 思考过程
> AI thinking process...

AI response content...

![image](images/conv_title_0.png)

---
```

## Adapting to a new platform

Complete this worksheet before writing platform-specific scripts:

```
Platform name: _______
Base URL: _______
Chat list URL: _______

=== DOM Selectors (use browser F12 to find) ===
Sidebar scroller class: _______
Conversation link pattern (regex): _______
Message list scroller class: _______
Message item class: _______

=== Role Detection ===
User messages have (class/attribute): _______
AI messages have (class/attribute): _______

=== Images ===
Image CDN domain: _______
Lazy load wrapper class: _______

=== Special Features ===
Has thinking/reasoning sections? _______
Thinking section selector: _______
Any other special content? _______
```

## Reference implementations

- **Doubao**: See `C:\Users\pc\temp_doubao_v8.py` and `C:\Users\pc\temp_doubao_discover.py`
- **Platform worksheet**: Fill out the worksheet above for each new platform
