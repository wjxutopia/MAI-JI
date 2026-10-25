# 参赛提交清单

> 本清单按 2026-10-25 核对到的官方页面整理。规则可能更新，正式提交前应再次打开官方页面确认。本文不代替参赛者对资格、原创性、合规性或声明内容的自行确认。

## 一、WaytoAGI 1024 用餐赛道

**官方页面：** https://1024.waytoagi.com/tracks/dine  
**通用规则：** https://1024.waytoagi.com/rules  
**作品提交截止：** 2026-10-25 16:00（北京时间）

### 提交页面需要填写/上传

- [ ] 作品名称：`麦记（Mai-Ji）`
- [ ] 一句话介绍：`爱吃的就那几样，怎么点更省？麦记用麦当劳 MCP 重新核价：老样子一句话复购，付款前也能检查这单。`
- [ ] 赛道：`用餐`
- [ ] 使用工具：选择 `WorkBuddy`，并按实际情况选择其他工具。
- [ ] 作品链接或文件：GitHub 仓库链接、可导入 Skill 包，或可上传的文件。
- [ ] 用餐赛道使用说明或录屏：提交文件或链接；建议按 [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md) 录制。
- [ ] `workbuddy.md`：使用 WorkBuddy 开发时，提供仓库中的文件并填仓库链接，或直接上传开发对话记录。
- [ ] 讲解录屏、社媒链接、评委体验账号：官方规则标为选填；没有真实可安全提供的体验账号时不要虚构。
- [ ] 提交前勾选《作品展示与使用须知》：版权归作者，授权主办方及赞助方展示和宣发；规则明确不要求开源。

### 文件大小提醒

- [ ] 开发对话记录 `.md`：单文件不超过 5 MB。
- [ ] 作品文件 `.html/.htm/.zip`：单文件不超过 200 MB。
- [ ] 讲解录屏：`mp4/mov/m4v/webm`，单文件不超过 500 MB。
- [ ] 若上传 ZIP，确认其中没有数据库、缓存、Token、完整地址、支付链接或测试订单数据。

### 评审展示重点

| 维度 | 权重 | 麦记应强调的内容 |
|---|---:|---|
| 完成度与可用性 | 30% | 可导入 Skill、编号授权、一次派发、防重与异常停止 |
| 创意 | 25% | 原生选购 + 支付前复核，而不是重复做聊天购物车 |
| 场景价值 | 25% | 同需求实时核价、低摩擦复购、额外商品显式选择 |
| 展示 | 20% | 三分钟讲清问题、流程、边界和下一步 |

## 二、麦当劳程序员创意开发大赛

**官方仓库：** https://github.com/M-China/mcd-developer-innovation-challenge  
**官方规则：** https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md  
**报名及排名截止：** 2026-10-25 23:59（北京时间）  
**最终 Star 采集：** 2026-10-26 00:00（北京时间）

### 公开 GitHub 仓库要求

- [ ] 使用公开可访问的 Public GitHub 仓库。
- [ ] 仓库创建时间在官方规定范围内：2025-12-25 00:00 至 2026-10-25 23:59（北京时间）。
- [ ] 根目录保留以下标准文件名：
  - [ ] `README.md`：项目介绍、安装方法、使用示例、目标用户。
  - [ ] `CONTEST_DECLARATION.md`：**官方原版，文件名和内容均不可修改。**
  - [ ] `MCP_INTEGRATION.md`：实际 MCP Server、Tool、调用流程和业务价值。
  - [ ] `mcp-config.example.json`：脱敏配置示例，只用环境变量占位符。
  - [ ] `workbuddy.md`：参加 WorkBuddy 专项奖励时必须提交。
  - [ ] 源代码或可运行内容：本材料包中的 `mai-ji/` 与 `dist/mai-ji-v1.2.0.zip`。
- [ ] 检查仓库、GitHub 账号资料、README、录屏和 Issue 中不含违法违规、侵权、隐私泄露、恶意代码或误导性声明。
- [ ] 发布前由参赛者自行阅读并确认 `CONTEST_DECLARATION.md` 和活动规则；不要替他人做声明。

### 发布报名 Issue

- [ ] 在官方活动仓库发 Issue，使用 [`REGISTRATION_ISSUE_TEMPLATE.md`](./REGISTRATION_ISSUE_TEMPLATE.md) 的纯文本格式。
- [ ] 替换项目地址为真实公开 GitHub URL；不使用 Markdown 链接格式。
- [ ] 按官方提示，标题与正文之间、字段名与字段内容之间避免不必要换行，防止严格校验失败。
- [ ] 检查官方机器人/系统在 Issue 下的报名结果；如失败，依据明确原因修改后再报名。
- [ ] 不采用刷 Star、批量账号、脚本操纵或其他不正当方式。

## 三、该材料包已准备的内容

| 文件 | 状态 | 说明 |
|---|---|---|
| `README.md` | 已准备 | 项目介绍、目标用户、安装、使用、边界与证据 |
| `MCP_INTEGRATION.md` | 已准备 | 实际 Server、工具、流程、数据与限制 |
| `mcp-config.example.json` | 已准备 | 不含真实 Token，仅环境变量占位符 |
| `CONTEST_DECLARATION.md` | 已复制 | 官方原版；发布前由参赛者本人确认 |
| `workbuddy.md` | 已准备 | 真实会话导出的脱敏可见对话记录，约 140 KB，低于 5 MB 上传上限 |
| `mai-ji/` | 已复制 | 已验证的 1.2.0 源码副本 |
| `dist/mai-ji-v1.2.0.zip` | 已复制 | 最终 Skill 分发包副本 |
| `USAGE_GUIDE.md` | 已准备 | 可作为使用说明的文字材料 |
| `VALIDATION_REPORT.md` | 已准备 | 测试、终审和证据边界摘要 |
| `DEMO_SCRIPT.md` | 已准备 | 约三分钟录屏/路演讲稿 |
| `OFFICIAL_REQUIREMENTS.md` | 已准备 | 两场赛事的必交、选填、来源与待人工动作逐项对照 |
| `REGISTRATION_ISSUE_TEMPLATE.md` | 已准备 | 官方报名 Issue 填写模板 |

## 四、仍需参赛者亲自补齐的事项

- [ ] 决定最终公开仓库名称、Owner、许可证和可公开的项目简介。
- [ ] 创建/确认 Public GitHub 仓库并上传本材料包内容；本轮未替你发布或推送。
- [ ] 本人确认原创性、合规性、信息安全和活动规则后，再保留原版声明并报名。
- [ ] 录制或确认使用说明/录屏；如录制真实演示，先完成脱敏检查。
- [ ] 在 WaytoAGI 提交页填写最终链接/文件并选择用餐赛道和 WorkBuddy。
- [ ] 在麦当劳官方仓库按模板发布报名 Issue。
- [ ] 截止前再次检查官方页面、仓库公开可访问性、必需文件名和无敏感信息状态。

## 五、提交前最后 90 秒检查

```text
[ ] README / MCP_INTEGRATION / CONTEST_DECLARATION / mcp-config.example / workbuddy 均在仓库根目录
[ ] CONTEST_DECLARATION 内容未改动
[ ] mcp-config.example 不含任何真实 Token、密码或账号信息
[ ] 无 *.db、*.sqlite3、.env、缓存、支付链接、完整地址、手机号、真实订单号
[ ] README 中的版本、测试数和限制均为 1.2.0 的真实表述
[ ] GitHub 仓库为 Public，项目链接可在未登录状态打开
[ ] Issue 中项目名称、地址、简介已替换占位符且未用 Markdown 链接
[ ] WaytoAGI 的“使用说明或录屏”与 workbuddy.md 已上传/可访问
```
