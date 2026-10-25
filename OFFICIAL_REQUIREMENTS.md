# 官方参赛要求逐项对照

> 核对日期：2026-10-25。来源为 WaytoAGI 官方赛道/规则页与麦当劳官方 GitHub 仓库。赛事规则可能变更，正式提交前请重新打开下列官方页面确认。本表不替代参赛者本人对原创性、合规性和声明的确认。

## 总结

- **WaytoAGI 用餐赛道**需要“能用的作品”以及“使用说明或录屏”；使用 WorkBuddy 的作品需要提供 `workbuddy.md`。
- **麦当劳程序员创意开发大赛**要求公开 GitHub 仓库，包含标准文件名的 README、原版声明、MCP 集成说明、脱敏配置示例和源代码；参与 WorkBuddy 专项奖励时，`workbuddy.md` 也必须提交。
- 本材料包已经准备所有可由本地内容生成的文件；创建公开仓库、最终录屏、正式提交页面与报名 Issue 仍由参赛者本人操作。

## 一、WaytoAGI 1024 用餐赛道

| 项目 | 官方要求或原文要点 | 本材料包状态 / 下一步 | 官方来源 |
|---|---|---|---|
| 作品能力 | “用麦当劳 MCP 做一个 AI 作品，形式不限，Skill、Agent、网页、小程序、机器人都行。” | 已提供可导入 Skill 包与源码；其他宿主的实际兼容性需在目标环境验证。 | [用餐赛道](https://1024.waytoagi.com/tracks/dine) |
| 使用 WorkBuddy 的资格 | 赛道页写明“建议用 WorkBuddy 开发……用 WorkBuddy 做的才评赛道前三”。 | 项目使用 WorkBuddy 开发；`workbuddy.md` 已从真实本地会话导出后脱敏生成。 | [用餐赛道](https://1024.waytoagi.com/tracks/dine) |
| 必交作品 | “能用的作品（链接、GitHub 仓库或安装包都行）＋一段使用说明或录屏”。 | `dist/mai-ji-v1.2.0.zip`、`USAGE_GUIDE.md`、`DEMO_SCRIPT.md` 已准备；录屏可按脚本另行录制。 | [用餐赛道](https://1024.waytoagi.com/tracks/dine) |
| WorkBuddy 开发记录 | “用 WorkBuddy 做的，再附一份 workbuddy.md（开发对话记录）。” | 根目录 `workbuddy.md` 已准备，约 132 KB；其中仅保留真实可见对话并做隐私脱敏。 | [用餐赛道](https://1024.waytoagi.com/tracks/dine) |
| 提交页字段 | 通用规则要求作品名称、一句话介绍、作品链接或文件、赛道、使用工具；讲解录屏、社媒链接、体验账号为选填。 | 可直接复制 `SUBMISSION_COPY.md`；没有可安全提供的体验账号或录屏链接时不要虚构。 | [通用规则·提交内容与规格](https://1024.waytoagi.com/rules) |
| 用餐赛道补充 | “用餐赛道需提交使用说明或录屏（文件或链接）；同步参加麦当劳大赛时可填写 GitHub 仓库与报名 Issue 链接。” | 使用说明已准备；GitHub URL 与 Issue URL 在实际创建后填写。 | [通用规则·提交内容与规格](https://1024.waytoagi.com/rules) |
| workbuddy.md 提交方式 | “使用 WorkBuddy 开发的作品需提供 workbuddy.md：放在 GitHub 仓库中并填写仓库链接，或上传开发对话记录。” | 可将根目录文件随仓库公开，或按提交页要求直接上传。 | [通用规则·提交内容与规格](https://1024.waytoagi.com/rules) |
| 文件大小 | 开发对话记录 `.md` 不超过 5 MB；HTML/ZIP 作品文件不超过 200 MB；录屏不超过 500 MB。 | `workbuddy.md` 约 132 KB；Skill 包与完整材料包均远低于 200 MB。 | [通用规则·上传规格](https://1024.waytoagi.com/rules) |
| 截止时间 | 作品提交截止为 2026-10-25 16:00（北京时间）；截止前可以修改并重新提交。 | 提交前再确认当前页面和时区。 | [通用规则·报名与提交作品](https://1024.waytoagi.com/rules) |
| 评分 | 完成度与可用性 30%、创意 25%、场景价值 25%、展示 20%。 | 演示重点已写入 `DEMO_SCRIPT.md` 和 `SUBMISSION_COPY.md`。 | [通用规则·评分标准](https://1024.waytoagi.com/rules) |
| 版权与开源 | 通用规则写明版权归作者、授权主办方/赞助方展示与宣发、“不要求开源”。 | 主赛不要求开源；若同步参加麦当劳活动，则后者的公开 GitHub 条件另行适用。 | [通用规则·提交内容与规格](https://1024.waytoagi.com/rules) |

## 二、麦当劳程序员创意开发大赛

| 项目 | 官方要求或原文要点 | 本材料包状态 / 下一步 | 官方来源 |
|---|---|---|---|
| 真实使用 MCP | 参赛项目“须真实使用麦当劳 MCP 能力”。 | `MCP_INTEGRATION.md` 记录实际 Server、工具、调用流程、证据与限制。 | [活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md) |
| 公开仓库 | 项目须发布在参赛者 GitHub 账户下且“可公开访问”；报名条件要求 Public 仓库。 | 本轮未创建或推送仓库；参赛者需自行创建公开仓库并上传材料。 | [活动 README](https://github.com/M-China/mcd-developer-innovation-challenge) |
| README | `README.md`：项目介绍、安装方法、使用示例和目标用户；文件名不可改。 | 已准备根目录 `README.md`。 | [活动 README·开发 Skill](https://github.com/M-China/mcd-developer-innovation-challenge) |
| 官方声明 | `CONTEST_DECLARATION.md` 必须存在，且“文件名及内容均不可改动”。 | 已原样复制官方文本；已按 GitHub 官方文件 SHA `136e76f3160317049f19f5ba03f4d0fedd70fc3c` 核对。本人确认声明后再发布。 | [官方声明](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/CONTEST_DECLARATION.md) |
| MCP 集成说明 | `MCP_INTEGRATION.md`：说明实际 MCP Server、Tool、调用流程和业务价值；文件名不可改。 | 已准备根目录 `MCP_INTEGRATION.md`。 | [活动 README·开发 Skill](https://github.com/M-China/mcd-developer-innovation-challenge) |
| 配置示例 | 完整活动规则要求 `mcp-config.example.json`，并规定配置文件只允许环境变量占位符。 | 已准备；只含 `${MCD_MCP_TOKEN}`，不含真实 Token。 | [活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md) |
| 源代码/可运行内容 | 项目主体代码或可运行内容必须存在，形式不限。 | `mai-ji/` 为源码；`dist/mai-ji-v1.2.0.zip` 为可导入 Skill 包。 | [活动 README·开发 Skill](https://github.com/M-China/mcd-developer-innovation-challenge) |
| WorkBuddy 记录 | 参加 WorkBuddy 专项奖励时 `workbuddy.md` 必须提交，且文件名不可改。 | 已准备脱敏的真实会话导出；它没有假称为逐字节原始导出。 | [活动 README·开发 Skill](https://github.com/M-China/mcd-developer-innovation-challenge) |
| 项目创建时间 | 官方报名条件：2025-12-25 00:00 至 2026-10-25 23:59（北京时间）。 | 创建公开仓库时由参赛者确认时间窗口。 | [活动 README·报名条件](https://github.com/M-China/mcd-developer-innovation-challenge) |
| 报名方式 | 在活动仓库按指定 Issue 格式发布，包含项目名称、项目地址、项目简介。 | 直接使用 `REGISTRATION_ISSUE_TEMPLATE.md`；替换公开 URL 后再发布。 | [活动 README·通过 Issue 报名](https://github.com/M-China/mcd-developer-innovation-challenge) |
| 报名截止/排名 | 报名及排名截至 2026-10-25 23:59；最终 Star 数据按 2026-10-26 00:00 采集。 | 本轮不代发 Issue、不发布仓库、不进行 Star 操作。 | [活动 README·赛事时间](https://github.com/M-China/mcd-developer-innovation-challenge) |
| 合规与公平 | 官方禁止违法违规、侵权、隐私泄露、恶意代码、虚假信息与不正当操纵 Star 等行为。 | 已做文档与非测试源码扫描；仍须参赛者在发布前人工确认其 GitHub 账号资料、录屏和最终提交内容。 | [活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md) |

## 三、提交前操作顺序

1. 阅读 `README.md`、`USAGE_GUIDE.md`、`VALIDATION_REPORT.md`，确认功能承诺与证据边界准确。
2. 由参赛者本人阅读并确认根目录原版 `CONTEST_DECLARATION.md` 与两场活动规则。
3. 决定公开仓库名称、Owner、许可证与公开简介；创建 Public GitHub 仓库并上传完整材料包内容。
4. 录制或核对使用说明/录屏；画面和日志中不出现 Token、地址、支付链接、手机号、真实订单号或未核实承诺。
5. 用 `SUBMISSION_COPY.md` 填 WaytoAGI 提交页，并上传/链接 `workbuddy.md` 与使用说明或录屏。
6. 如同步参加麦当劳活动，用 `REGISTRATION_ISSUE_TEMPLATE.md` 发布报名 Issue，等待官方系统回复。
7. 最后按 `SUBMISSION_CHECKLIST.md` 做 90 秒检查，重新打开官方页面确认时限与规则。

## 四、本轮没有执行的对外动作

本材料包的生成不等于已公开发布、报名成功、正式提交、获得奖项资格或完成声明确认。本轮没有创建 GitHub 仓库、推送代码、创建 Issue、上传录屏、填写赛事页面、操作真实订单或自动支付。
