# 本地运行与 JSON 操作协议

## 前提与数据归属

使用宿主已有 Python 3.10+，优先托管运行时，不安装依赖；脚本仅用标准库。开发测试实际使用 Python 3.13.12。先确认当前环境的可用绝对路径，不能在其他机器照搬开发机路径。

以实际技能根目录替代 SKILL_ROOT，以同一系统用户、同一麦当劳账号稳定复用的数据路径替代 DB_PATH：

```text
ABS_PYTHON -B SKILL_ROOT/scripts/guard.py --db ABS_DATA_DIR/guard.sqlite3
```

通过标准输入发送一个 UTF-8 JSON 对象，标准输出返回 `{"ok":true,"result":...}` 或 `{"ok":false,"error":"错误码"}`；协议失败退出码2。只解析 JSON，不把任意响应当执行许可。输入上限200000字节；拒绝所有层级的重复键、NaN和Infinity，过深结构、极端时间、无效Unicode文本和存储错误返回受控错误，不回显输入。无参数时可用 `--help`。输入可直接由宿主发送，或使用只含脱敏规范化数据的临时 JSON 文件重定向；不得落盘地址、电话、凭证、支付链接或完整创建请求。命令参数和日志也不能夹带这些信息。

运行数据必须位于技能包之外，脚本拒绝技能目录及其子目录中的数据库。可在用户明确的数据目录建立 `mai-ji-data/guard.sqlite3`，不要每个会话另建库。源码内不保存 DB，不把状态文件打包或公开。代码升级不能删除状态库解除未知订单阻塞。

`scope` 是本地账户隔离别名，仅限字母数字、下划线、点、连字符，不是 token 或真实账户ID；同一麦当劳账号必须始终使用同一 scope 和同一 DB。无法确认账号归属时停止写操作，不能随手换 scope 绕过阻塞。首次可询问一个短本地别名，不要求个人信息。账号切换后重新绑定；别名不是认证手段。

`session` 是宿主稳定会话ID；若没有可取得的ID，在该会话首次建立一个随机标识并保留于会话上下文，之后复用。不能每次收到编号重建session。新会话可只读 status 恢复旧执行状态，但不能将旧卡的裸编号绑定到新session执行。

## 本地启动、升级与首轮检查

当前源码包不表示已安装/启用。本轮不自动覆盖已安装技能。使用本机宿主实际支持的导入/技能目录方式；未核对当前版本入口时，不编造菜单名称。安装后只保留一个启用的mai-ji版本，避免两份指令同时触发。

1. 确认包内有SKILL.md、references、scripts与tests，以及Python 3.10+。以实际技能路径运行 `ABS_PYTHON -B -m unittest discover -s SKILL_ROOT/tests -v`，不要把开发机路径写死到其他机器。
2. 选定包外稳定数据路径、同账号scope与当前会话session。首次运行先告知最小本地防重记录；用money做纯计算，用status查看状态。不能每会话换DB，或临时换scope绕开旧执行。
3. 更新代码前保留旧代码包；不移动、清空或打包运行库。1.2.0继续保留旧执行状态；缺终态字段时自动添加。旧模板兼容规则见memory.md。已有未解决执行时先只读查状态；不为了升级先删库。
4. 在新会话分别验证“老样子无模板”“检查刚才这单无单”和同DB/scope模板读取。首用没有需求时一次引导原生选餐、提交待支付暂不付款、回来检查；不为验收自动建测试单。
5. 宿主触发/只读检查和真实编号写操作是不同验收。没有具体真实测试授权时止于只读；不要把离线测试通过当真实下单许可。

## 不使用 DB 的纯计算操作

```json
{"op":"money","value":"- ¥1","unit":"yuan"}
```

unit 为 yuan / cents；value 只接受字符串或整数，拒绝 float / bool / NaN / 非整数分和多余精度。绝对金额上限为10^12分；卡片总额仅接受0至10^12的整数分。返回 cents 和两位元字符串。金额计算链只使用分，不用浮点。食品数量为1—1000。可选notes仅收用户明确提出的短备注，最多10条、每条120字符；普通标准单不需要该字段。

`selection` 纯解析回复，不需要DB，也不产生授权：

```json
{"op":"selection","reply":"2","current_card_id":"aaaaaaaaaaaaaaaa","require_card_id":false}
```

`current_card_id` 必须来自本会话当前已展示卡的完整16位十六进制ID。上下文可证明归属时接受纯编号1—99；归属不明则 `require_card_id=true`，只接受 `卡 aaaaaaaaaaaaaaaa 2`、`aaaaaaaaaaaaaaaa 2` 或 `aaaaaaaaaaaaaaaa:2` 等完整卡号加编号格式。示例ID只是合成演示，不能用于真实选择。旧卡号、含糊同意、数字加支付指令均拒绝。输出规范化的card_id与choice后仍须重验并claim；解析成功不证明卡有效、已展示或有业务权限。

```json
{"op":"digest","value":{"stable":"经规范化的完整摘要"}}
```

使用键排序 JSON 和 SHA256。原始数据只参与本次内存计算，不存入 DB；输出哈希并不等于可公开，仍按私人元数据处理。

compare 输入见 solver.md。必填 op、required、candidate；双方 fulfillment 缺任何必要字段时返回 classification=unknown。每个食品叶子必填 identity、name、spec、quantity、complete=true；可选notes仅为用户明确备注。普通标准单不需modifications或notes。旧modifications=[]可兼容并在规范化输出移除；非空或非法值不能静默丢弃，返回unknown，需核对该旧要求。对比键为identity、spec、notes，notes按短文本排序，缺省与空数组相同；脚本不理解近义备注，调用方须用同一已核对文字，不擅自推定语义等价。父子数量须先由调用方正确展开。脚本不自动推断套餐、对齐跨SKU、解读配料编码或确认备注传递。输出 equivalent / extra / different / unknown。可同时传 baseline_cents、candidate_cents，只有确定等价或保留全部目标的额外项才计算差额。extra 更贵时 optional_gain=false，不能作同价低价增益。

## 卡片与执行操作

所有持久化操作必填 op 和 scope。卡片操作另需 session；有执行 receipt 后用 receipt 替代 card_id。字段严格 allowlist，多余字段报错。以下是字段协议，不是给用户看的表单。

| op | 额外字段 | 返回/限制 |
|---|---|---|
| offer | session、expires_at、options | 卡号；有效期必须未来且不超过300秒；同会话旧offered卡作废，scope有claimed执行则拒绝 |
| claim | session、card_id、choice、fingerprint | 单次receipt；同scope其他未领取卡同时失效 |
| begin | session、receipt、stage；cancel另需old_pending=true | allow_dispatch=true才可派发一次；重复begin拒绝 |
| record | session、receipt、stage、outcome；create成功另需new_order_id | 只记录已begin阶段；success / failed / unknown；不接受原始响应 |
| verify | session、receipt、new_order_id、matched、pending | 两个布尔都true才确认新单核对通过 |
| reconcile | session、receipt、stage、outcome及证据字段 | 原会话只读回查后补证；不派发业务请求 |
| observe | session、receipt、target、order_id、terminal、evidence；可选close或complete | 原会话记录绑定订单终态；不派发 |
| recover | 同observe；session为当前新会话ID | 按scope/receipt补证旧执行，不改绑原session，不获得派发权 |
| finish | session、receipt及本次终态布尔/枚举 | 标完成；永不返回支付链接 |
| abort | session、receipt | 仅允许create/cancel都未begin的claimed卡安全结束 |
| invalidate | session、card_id | 只废弃offered卡，不能清除未知执行 |
| status | 可选session | 当前scope最近30条；未解决优先；返回最小订单绑定与所选方案摘要，不自动派发 |

options为1—3项，每项严格结构：

```json
{
  "number":"1", "action":"replace",
  "label":"脱敏食品摘要及动作",
  "total_cents":2890,
  "fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "old_order_id":"2001"
}
```

上例2001与重复a摘要均为合成占位，禁止用于真实调用；真实fingerprint须用本次规范化摘要计算。number 必须为1—99的无前导零纯数字字符串；action 为 keep/create/replace。keep、replace必填真实绑定old_order_id；create禁止此字段。orderId用字符串保留精度，1—64个数字。卡有效期使用带时区ISO8601，禁止随手估计当前时间。

## 授权指纹：不能只哈希价格

由本次真实读取构建规范化摘要，然后 digest；执行前按相同规则重新构建并比较：

- action；存在原单时包含卡绑定原单orderId、“待支付”状态、原单金额、支付截止和快照完整性，无原单创建则明确无绑定原单；
- 完整食品需求叶子、明确备注、实际父套餐/round/子项/数量和底层默认选配结构，当前选中券编码；
- 当前完整应付、商品与各费用；报价成功状态、真实库存/合法选配状态；
- 完整履约（门店、渠道、地址绑定指纹、取餐、餐具、时间、备注指纹）；
- 用户已明确接受的新增商品及本次明确备注，与创建及后撤旧单的具体关系；
- 使用的模板ID和版本内容摘要，以及已有匹配待支付单的状态。

时间戳只纳入真正的有效期，不纳入每次请求traceId、随机字段或“查询时间”，避免无意义变更；价格/库存/券/状态的实际变化必须改变指纹。所有原始身份信息仅在当前会话处理，持久化只存摘要哈希与允许字段。脚本不能自行联网复核这些证据，也不能证明调用者填入的fingerprint/布尔断言真实，必须由技能按契约读取后如实提交。

## 恢复、失败与状态含义

- `begin` 先事务提交 dispatching 再发出真实工具调用。同次授权最多一次create、一次有条件cancel。模型不能因为没有收到结果而再次调用。
- `record failed` 只用于已确认没有创建成功的明确业务拒绝；网络超时、截断、连接中断及不能确认响应归属都记unknown。create failed关闭本receipt，再试必须重新核价、生成新卡并让用户再次选择。
- begin成功后崩溃，即使可能尚未发送也保守视未知。status会展示dispatching，先查单；不根据列表暂时没单认定不存在。
- reconcile create outcome=success必须给唯一确认的new_order_id；outcome=confirmed_absent必须给evidence=authoritative_absence，只有明确业务拒绝或服务方权威证明不存在才可用。当前工具未提供通用“请求绝未创建”证明，列表为空本身不够；查不清就unknown并保持阻塞。
- reconcile cancel outcome=success必须给confirmed_terminal=cancelled或expired，并持久化为old_terminal；与已知终态冲突时回滚，后续finish必须一致。已支付不是成功取消。该操作不伪造一次取消派发；取消根本未begin时改用observe。finish成功也保留本次最终old_terminal。
- verify matched=false或pending=false保持阻塞，不撤旧单、不自动撤新单，不自动修复。
- finish keep需old_pending=true且旧单无已知终态；create需verified、新单无已知终态、final_new_pending=true；replace另需cancel成功或已observe旧单终态，并传一致的final_old_terminal=cancelled/expired。每次都先重新查询实际状态。
- 任一真实订单仍未知、两笔都待支付、已支付冲突、商品不符则停，不通过abort或删除DB掩盖。旧单已支付时明示不要再付新单，引导原生页核对旧单；需要退款/重复餐处理时联系官方客服，回来只读查两单。当前版本没有“强制解锁未知结果”指令，不承诺退款或自动收口。

### 绑定订单终态观察与跨会话收口

`status` 的每条记录包含id、原session、status、receipt、choice、expires、create_state、cancel_state、new_order_id、verified、old_terminal、new_terminal。已选记录另有selected：number、action、label、total_cents、fingerprint、old_order_id。未选卡不返回整套候选。仅用这些最小绑定信息只读查单，不将原session抄成新会话身份来派发旧授权。

`observe` 限原会话；`recover` 接受当前新session，通过同scope和receipt定位旧执行但不改绑会话。两者只允许已claimed执行，必填：

- target=old/new；order_id必须准确等于已绑定旧/新单，new还需create_state=success。
- terminal=cancelled/expired，且evidence=detail_and_list_confirmed；只有当前详情与列表共同确认才填。paid、unknown、列表缺项或仅用户口述不构成证据。
- 不可将已经记录的终态改成相冲突的另一终态；两者不返回派发许可。

默认只记录终态、保持阻塞。可选收口二选一：

- `complete=true`：仅replace且target=old；新单必须此前完整verify通过、创建success且无已知终态。重新查询新单仍完整匹配且待支付后，传final_new_pending=true，标completed并返回绑定新单号、allow_dispatch=false。允许旧单在cancel前自然过期、人工取消或取消响应未知后只读收口；不把cancel_state伪写success，不发第二次取消。新会话同样可只读收口；若此前未核验新单则拒绝。脚本不存/生成支付链接；完成后由技能使用本次真实查询的新单入口与截止告知用户，没有入口则引导原生订单页按已核对订单支付，不编造未知截止。allow_dispatch=false只禁止再次创建/取消，用户仍可自行支付。
- `close=true`：keep要求旧单终态；create要求新单终态；replace要求两单均已确认取消/过期。标stopped、completed=false、allow_dispatch=false，只表示这次尝试已结束，无可支付新结果。少一单、订单号未知或创建未知均不能强行关闭。

close与complete不能同时true；final_new_pending只能随complete出现。字段不合要求时整个事务回滚，终态观察也不部分提交。完成或停止后才允许重新核价另发新卡，仍需用户新选择；恢复从不复活旧卡。本版延续1.1.0的旧库迁移，首次打开缺列的库自动添加两个终态列并保留既有派发标记；代码升级不得删除或重建库。

## 模板操作

consent：scope、granted布尔、notice_version="1"。返回granted、reuse_allowed、templates_purged。granted=false停止未来保存和自动复用；只有显式purge=true同时清空模板，默认不删除既有模板，仍可查看/删除。重新明确同意后才可恢复复用。

template-save：scope、template_id、explicit_intent=true、source=user_confirmed_request、data。data仅允许name、scene、items、restrictions；scene仅允许daypart、mode、storeCode、address_label、takeway_label，值均为短标签。items用已核对完整叶子，不保存旧价格、父套餐购买结构、地址ID或支付信息。source不是订单状态，必须表示用户主动确认的需求；不能把取消/失败/未知订单或候选伪标user_confirmed_request。

template-list：scope，供用户查看/管理；撤回后仍可用，但不得把管理读取当自动复用。template-load：scope，供“老样子”自动采用，当前未同意或已撤回时拒绝。两者返回reuse_allowed、templates、review_required，每条包含template_id、data、auto_reuse_allowed；待核对项另有review_reason。load的templates只含结构可用项，非空旧modifications等不能安全规范化的项仅进review_required；list的templates含全部项，待核对项也列于review_required。顶层reuse_allowed只表示同意有效，不覆盖单条auto_reuse_allowed=false；待核对项不能自动采用。加载时完整校验name/scene/items/restrictions、白名单和文本，坏JSON、重复键、缺字段或含私密字段的条目以data=null隔离，不回显原文、不阻断其他模板。结构合法的非空旧modifications可只读查看，但绝不直接执行。只读规范化不覆盖旧存储；仅用户明确更新才template-save。items不存独立特制编码，空旧字段兼容；非空旧值保存时拒绝。template-delete：scope与一个template_id；删除全部需explicit_all=true且不传template_id。不允许脚本自动统计历史生成模板。

## 真实保证范围

SQLite BEGIN IMMEDIATE、事务提交与持久派发标记，保证同机同DB、相同scope、严格遵循本协议的调用具有一次领取/一次派发保护。**不是远端幂等、跨设备互斥、可信执行沙箱或绝对防重保证。** 模型绕过脚本、换DB或scope、其他设备同时下单、远端状态变更都不受本脚本控制。短期有效卡仍存在核价后至创建间竞态，创建后必须核验。

字段allowlist拒绝原始响应、完整地址和支付字段；部分文本另拒绝URL、明显手机号。它不是通用个人信息检测器，不能自动辨认所有自然语言地址，因此写入前必须人工/模型最小化脱敏；不把隐私保护说成百分百自动完成。
