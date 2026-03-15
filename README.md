# Feishu Toolkit

<p align="center">
  <strong>飞书/Lark 开放平台 Python 工具包</strong><br>
  单文件、零配置，为 AI Agent 和自动化场景而生
</p>

<p align="center">
  <a href="#features">功能</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#usage">使用指南</a> ·
  <a href="#ai-agent">AI Agent 集成</a> ·
  <a href="#api">API 参考</a>
</p>

---

## Why?

飞书官方提供了 [MCP Server](https://www.npmjs.com/package/@larksuiteoapi/lark-mcp) 用于 AI 工具集成，但存在以下限制：

| 场景 | 官方 MCP | 本工具 |
|------|:--------:|:------:|
| 图片上传/发送 | :x: 不支持 | :white_check_mark: |
| 富文本消息（@用户 + 图片 + 链接混排） | :warning: 格式复杂易出错 | :white_check_mark: Builder API |
| 创建文档并写入结构化内容 | :x: 缺少 Block API | :white_check_mark: |
| 交互卡片消息 | :warning: 需手写 JSON | :white_check_mark: Builder API |
| 多维表格 CRUD | :white_check_mark: | :white_check_mark: |
| 纯文本消息 | :white_check_mark: | :white_check_mark: |

本项目是对官方 MCP 的**补充**，而非替代。推荐两者配合使用。

<h2 id="features">Features</h2>

- **单文件** - 只需 `feishu_toolkit.py`，复制即用
- **零框架依赖** - 仅依赖 `requests`
- **双模式** - 既是 Python 库，也是 CLI 工具
- **Builder API** - 用链式方法构建富文本、卡片、文档，告别手写 JSON
- **Token 自动管理** - `tenant_access_token` 自动获取、缓存、续期
- **AI Agent 友好** - 内置 Cursor / Claude Code Skill 配置

### 支持的能力

| 类别 | 能力 |
|------|------|
| **消息** | 文本、富文本（@用户/图片/链接/表情）、图片、交互卡片 |
| **图片** | 上传图片、获取 image_key |
| **文档** | 创建文档、写入 Block（标题/段落/列表/代码块/引用/分割线） |
| **多维表格** | 创建表格、批量创建记录、搜索记录 |
| **通讯录** | 邮箱/手机号 → open_id 查询 |
| **群组** | 列出机器人已加入的群组 |

<h2 id="quick-start">Quick Start</h2>

### 安装

```bash
# 方式 1: 直接下载单文件
curl -O https://raw.githubusercontent.com/mix9581/feishu-toolkit/main/feishu_toolkit.py

# 方式 2: 克隆仓库
git clone https://github.com/mix9581/feishu-toolkit.git

# 安装依赖
pip install requests
```

### 准备工作

1. 前往 [飞书开放平台](https://open.feishu.cn/app) 创建应用（或使用已有应用）
2. 获取 **App ID** 和 **App Secret**
3. 启用**机器人**能力
4. 根据需要添加 API 权限（消息、文档、多维表格等）
5. 将机器人添加到目标群组

### 设置凭证

```bash
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
```

### 验证连通性

```bash
# 测试认证
python feishu_toolkit.py auth

# 列出群组
python feishu_toolkit.py list-chats
```

<h2 id="usage">Usage</h2>

### 作为 Python 库

```python
from feishu_toolkit import FeishuClient

client = FeishuClient()  # 从环境变量读取凭证
# 或: client = FeishuClient(app_id="cli_xxx", app_secret="xxx")
```

#### 发送文本消息

```python
client.send_text("oc_xxx", "Hello from Feishu Toolkit!")
```

#### 发送富文本消息（含 @用户）

```python
uid = client.get_user_id_by_email("zhangsan@company.com")

client.send_rich_text("oc_xxx", "周报通知", [
    [client.text("Hi "), client.at(uid, "张三"), client.text(" 本周报告已生成")],
    [client.text("播放量环比增长 23.5%，详情: "), client.link("查看报告", "https://example.com")],
])
```

#### 上传图片并发送

```python
image_key = client.upload_image("./chart.png")
client.send_image("oc_xxx", image_key)

client.send_rich_text("oc_xxx", "数据图表", [
    [client.text("本周趋势:")],
    [client.img(image_key)],
])
```

#### 发送交互卡片

```python
card = client.build_card("数据告警", [
    client.card_markdown("**播放量异常下降**"),
    client.card_fields([
        ("**歌曲**: 星晴", True),
        ("**平台**: QQ音乐", True),
        ("**当前值**: 12,345", True),
        ("**基线值**: 45,678", True),
    ]),
    client.card_divider(),
    client.card_button("查看详情", "https://dashboard.example.com"),
], color="red")

client.send_card("oc_xxx", card)
```

#### 创建飞书文档

```python
result = client.create_document_with_content("自动生成的分析报告", [
    client.heading_block("概览", level=1),
    client.text_block("本周各平台数据表现良好，整体播放量环比增长 15%。"),
    client.heading_block("详细数据", level=2),
    client.bullet_block("QQ音乐: 播放量 120万"),
    client.bullet_block("网易云: 播放量 85万"),
    client.divider_block(),
    client.code_block("SELECT song, SUM(plays) FROM metrics GROUP BY 1", language=62),
])
print(f"文档地址: {result['url']}")
```

#### 多维表格操作

```python
bitable = client.create_bitable("数据看板")

client.create_bitable_records(app_token, table_id, [
    {"fields": {"歌曲": "星晴", "播放量": 120000, "平台": "QQ音乐"}},
    {"fields": {"歌曲": "晴天", "播放量": 85000, "平台": "网易云"}},
])

results = client.search_bitable_records(app_token, table_id, filter_={
    "conjunction": "and",
    "conditions": [{"field_name": "平台", "operator": "is", "value": ["QQ音乐"]}]
})
```

### 作为 CLI 工具

```bash
python feishu_toolkit.py auth
python feishu_toolkit.py list-chats
python feishu_toolkit.py send-text oc_xxx '消息内容'
python feishu_toolkit.py upload-image ./image.png
python feishu_toolkit.py send-image oc_xxx ./image.png
python feishu_toolkit.py get-user-id --email user@company.com
python feishu_toolkit.py create-doc '文档标题'
```

<h2 id="ai-agent">AI Agent 集成</h2>

### 配合官方 MCP 使用（推荐）

多维表格 CRUD、文档搜索等场景走官方 MCP，图片/富文本/文档创建走本工具：

```json
{
  "mcpServers": {
    "lark-mcp": {
      "command": "npx",
      "args": ["-y", "@larksuiteoapi/lark-mcp", "mcp", "-a", "<app_id>", "-s", "<app_secret>"]
    }
  }
}
```

### 作为 Cursor Skill

```bash
cp -r skill/ ~/.cursor/skills/feishu-integration/
```

### 作为 Claude Code Skill

```bash
cp -r skill/ ~/.claude/skills/feishu-integration/
```

<h2 id="api">API Reference</h2>

### FeishuClient

| 方法 | 说明 |
|------|------|
| `send_text(id, text)` | 发送纯文本消息 |
| `send_rich_text(id, title, content)` | 发送富文本消息 |
| `send_image(id, image_key)` | 发送图片消息 |
| `send_card(id, card)` | 发送交互卡片 |
| `upload_image(path)` | 上传图片，返回 image_key |
| `get_user_id_by_email(email)` | 邮箱 → open_id |
| `get_user_id_by_mobile(mobile)` | 手机号 → open_id |
| `list_chats()` | 列出已加入的群组 |
| `create_document(title)` | 创建空文档 |
| `create_document_with_content(title, blocks)` | 创建文档并写入内容 |
| `create_bitable(name)` | 创建多维表格 |
| `create_bitable_records(app, table, records)` | 批量创建记录 |
| `search_bitable_records(app, table, filter)` | 搜索记录 |

## 环境要求

- Python >= 3.9
- requests

## License

[MIT](LICENSE)
