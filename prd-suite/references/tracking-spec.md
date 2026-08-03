# 泰小虎埋点规范（友盟+ 事件表 v2.3）— PRD 埋点需求权威引用

> 本文件是《泰小虎埋点表v2.3》的**结构化摘要**，供 AI 写 PRD §五【埋点需求】时作为权威参考（含完整 30 事件目录与属性）。
> 权威源文件：`D:/梯子/泰小虎埋点表v2.3 (5).xlsx`（埋点事件表 117 行 + 页面分析表）。
> 在线方案（事件树）：https://ddyuan-spec.github.io/taixiaohu/taixiaohu-tracking-plan.html
> **PRD 读者可点开的独立在线全文（完整 30 事件 / 属性 / 页面枚举 / 友盟约束）**：https://ddyuan-spec.github.io/taixiaohu/taixiaohu-tracking-spec.html
> ⚠️ **PRD §五 禁止把本规范整表内嵌进文档**（会极难看且臃肿）。只允许：① 一句说明 + ② 插入上方「独立在线全文」链接 + ③ 一张「本期涉及事件清单」精简表（见 §0 第 5 条）。

## 0. 使用红线（写 PRD 埋点需求必须遵守）
- **禁止凭空编造事件英文名 / 属性变量名**。只能从下方【§5 事件目录】选取既有事件，或明确标注「⚠️ 待确认 @数据/研发」后由埋点负责人补充。
- 一个功能在 PRD 里涉及的埋点，必须对应 §5 中已存在的事件英文名；新事件须走埋点评审，不在 PRD 内新增定义。
- 引用埋点参数时，**友盟后台用中文名**（如「步骤序号」而非 step_index），与后台配置一致。
- 平台/模块/层(L1-L3)字段直接取自 §5，不得改写。
- **PRD §五 内嵌禁令（关键）**：PRD 文档里**不得复制本规范整表**（30 事件 × 属性）。§五 埋点需求只允许呈现三件套：
  1. 一句说明：「本需求埋点事件与属性严格遵循《泰小虎埋点规范 v2.3》」；
  2. 插入链接：`[泰小虎埋点规范 v2.3（在线查阅）](https://ddyuan-spec.github.io/taixiaohu/taixiaohu-tracking-spec.html)`；
  3. **本期涉及事件清单**（精简表，仅列本期用到的事件）：列 = `事件英文名 | 事件显示名 | 所属层 | 平台 | 触发时机 | 必含上报参数(友盟中文名) | 备注`。不展开全部属性列、不列未涉及事件。

## 1. 埋点规范字段 schema（事件表列说明）
| 列 | 含义 |
| --- | --- |
| 事件编号 | 同一事件的多行属性共用同一编号 |
| 项目 | 泰小虎 |
| 所属层 | L1 启动/浏览/基础交互；L2 业务核心（建档/对话/识别/推荐）；L3 转化/留存/反馈 |
| 平台 | Android/iOS / H5 / H5-Server / Server |
| 模块 | common/navigation/popup/scan/dialogue/profile/recommend/product/purchase/feedback/retention/order/share_poster |
| 事件英文名 | snake_case，友盟事件 ID，全局唯一，创建后不可改名 |
| 事件显示名 | 中文展示名 |
| 事件类型 | 启动/浏览/点击/曝光/提交/发送/接口返回结果/服务端派生 |
| 属性英文变量名 | snake_case，友盟自定义属性 ID，创建后不可删/改名/改类型，只能新增 |
| 属性显示名 | 友盟后台中文名 |
| 数据类型 | string/number |
| 属性说明 | 取值范围/枚举/口径 |
| 触发时机 | 前端/服务端触发条件 |
| 必填性 | 必填/条件必填/选填 |
| 示例值 | 样例 |
| 关联指标 | DAU/PV/转化等 |
| 上报时机 | 上报节点 |
| 去重规则 | 去重口径 |
| 校验规则 | 取值校验（如枚举∈{...}） |
| 状态 | 已完成/无需处理等 |

## 2. 分层与规模
- L1 基础层：**16** 事件（启动/页面浏览/Tab/按钮/弹窗/识别入口/开屏问题曝光）
- L2 业务层：**9** 事件（建档提交/更新、开屏点击、发起对话、产品详情、推荐曝光、报告上传、识别完成、对话反馈）
- L3 转化/留存层：**5** 事件（商品点击/下单、完整建档、差评、复访、订单/海报相关）
- 合计：**30** 事件。

## 3. 命名规范与枚举
- 事件英文名：snake_case（如 `app_launch`、`page_view`、`dialogue_send`）。
- 属性英文变量名：snake_case（如 `launch_type`、`page_name`、`source_page`）。
- page_name 枚举（页面分析表）：
  - `tai_chat` = 泰小虎首页/智能对话页（app://tai-chat）
  - `health` = 健康Tab内容页/健康档案页（app://health）
  - `service` = 服务Tab内容页（app://service）
  - `profile_onboarding` = 首次建档/新手引导页（app://profile/onboarding）
  - `product_detail_h5` = 商品详情页（h5://product/detail）

## 4. 友盟+ 平台约束
- 自定义事件属性一旦创建**不能删/改名/改类型，只能新增** → 采用「整体重导」策略。
- 引用埋点参数用友盟后台**中文名**。
- 事件树（事件树替代线性漏斗）口径见在线方案。

## 5. 事件目录（按层，含属性）

### L1 层

**app_launch** — App启动 ｜ 平台:Android/iOS ｜ 模块:common ｜ 类型:启动 ｜ 状态:已完成
- 触发时机：App冷启动或热启动（从后台恢复）
- 去重：同一自然日内同一device_id不限制次数；新增用户按首次app_launch的is_first_day=true标记。
- 属性（2）：
  - `launch_type` 启动类型（string，必填）：启动类型：cold(冷启动) / hot(热启动)
  - `launch_duration` 冷启动耗时（number，条件必填）：冷启动耗时（毫秒）。起点：进程入口；终点：首页首帧完成且主线程可交互。仅launch_type=cold上报

**page_view** — 页面浏览 ｜ 平台:Android/iOS ｜ 模块:common ｜ 类型:浏览 ｜ 状态:已完成
- 触发时机：页面加载完成时触发
- 去重：同一session内同一页面可重复上报，每次进入都算一次PV。
- 属性（4）：
  - `page_name` 页面名称（string，必填）：页面名称（统一命名规范）
  - `page_path` 页面路径（string，必填）：页面路径（路由地址）
  - `source_page` 来源页面（string，选填）：来源页面（上一页page_name）
  - `stay_duration` 停留时长（number，选填）：页面停留时长（毫秒）；SDK在页面离开时完成本次页面记录并上报，异常终止时可缺失

**tab_switch** — Tab切换 ｜ 平台:Android/iOS ｜ 模块:navigation ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：点击首页顶部“健康/泰小虎/服务”Tab切换内容
- 去重：同一session内可重复，连续点击同一Tab仅首次上报。
- 属性（2）：
  - `from_tab` 来源Tab（string，必填）：来源Tab名称
  - `to_tab` 目标Tab（string，必填）：目标Tab名称

**button_click** — 按钮点击 ｜ 平台:Android/iOS ｜ 模块:common ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：点击页面内的可交互按钮
- 去重：不限制，每次有效点击均上报。
- 属性（3）：
  - `page_name` 页面名称（string，必填）：按钮所在页面
  - `button_name` 按钮名称（string，必填）：按钮名称（统一命名规范）
  - `button_type` 按钮类型（string，选填）：按钮类型

**popup_view** — 弹窗曝光 ｜ 平台:Android/iOS ｜ 模块:popup ｜ 类型:曝光 ｜ 状态:已完成
- 触发时机：弹窗/浮层展示时触发
- 去重：同一popup_name在同一session内连续展示需多次上报；弹窗关闭后重新打开视为新曝光。
- 属性（4）：
  - `popup_instance_id` 弹窗实例ID（string，必填）：单次弹窗实例ID，用于与popup_close精确配对
  - `popup_name` 弹窗名称（string，必填）：弹窗名称
  - `popup_type` 弹窗类型（string，必填）：弹窗类型
  - `trigger_source` 触发来源（string，选填）：弹窗触发来源

**popup_close** — 弹窗关闭 ｜ 平台:Android/iOS ｜ 模块:popup ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：弹窗关闭时触发（点击关闭按钮/遮罩/返回键）
- 去重：每个popup_instance_id最多上报一次关闭；与popup_view按实例ID一一配对。
- 属性（5）：
  - `popup_instance_id` 弹窗实例ID（string，必填）：单次弹窗实例ID，必须与popup_view一致
  - `popup_name` 弹窗名称（string，必填）：弹窗名称（同 popup_view）
  - `close_method` 关闭方式（string，必填）：关闭方式
  - `stay_duration` 停留时长（number，选填）：弹窗停留时长（毫秒）
  - `user_choice` 用户选择（string，选填）：用户选择（仅选择类弹窗）

**scan_entry** — 智能识别入口 ｜ 平台:Android/iOS ｜ 模块:scan ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：点击智能识别入口（对话页卡片/悬浮球）
- 去重：不限制。
- 属性（3）：
  - `scan_id，改为message_id` 信息ID（string，必填）：单次识别任务的信息ID，用于关联scan_complete
  - `entry_source` 入口来源（string，必填）：入口来源
  - `scan_type` 识别类型（string，必填）：识别类型

**quick_question_view** — 开屏问题曝光 ｜ 平台:Android/iOS ｜ 模块:dialogue ｜ 类型:曝光 ｜ 状态:无需处理
- 触发时机：对话页顶部开屏问题列表渲染完成并可见时触发
- 去重：每次进入对话页重新展示时上报；同一session内问题列表刷新时重新上报。
- 属性（3）：
  - `exposure_id` 曝光ID（string，必填）：本次问题列表曝光ID，用于与点击精确归因
  - `question_ids` 问题ID列表（string，必填）：本次展示的问题ID列表（分号分隔，后台随机选取）
  - `display_count` 展示数量（number，必填）：本次展示的问题数量

**closed_order_delete_click** — 已关闭订单删除按钮点击 ｜ 平台:H5/Server ｜ 模块:order ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：用户点击「删除订单」按钮
- 去重：同一订单同一按钮操作防抖后仅记一次；重新进入页面可再次上报。
- 属性（1）：
  - `order_id` 订单ID（string，必填）：已关闭订单唯一ID

**closed_order_add_cart_click** — 已关闭订单加购按钮点击 ｜ 平台:H5/Server ｜ 模块:order ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：用户点击「再次购买」按钮
- 去重：同一订单同一按钮操作防抖后仅记一次；重新进入页面可再次上报。
- 属性（1）：
  - `order_id` 订单ID（string，必填）：已关闭订单唯一ID

**closed_order_add_cart_result** — 已关闭订单加购结果 ｜ 平台:H5/Server ｜ 模块:order ｜ 类型:接口返回结果 ｜ 状态:无需处理
- 触发时机：加购接口返回结果
- 去重：同一order_id同一加购操作仅上报一次。
- 属性（3）：
  - `order_id` 订单ID（string，必填）：已关闭订单唯一ID
  - `operation_result` 操作结果（string，必填）：加购结果：成功/部分成功/失败
  - `fail_reason` 失败原因（string，选填）：失败原因描述（仅失败时填写）

**poster_more_entry_click** — 更多海报入口点击 ｜ 平台:H5/Server ｜ 模块:share_poster ｜ 类型:点击 ｜ 状态:
- 触发时机：白名单用户点击分享弹窗「更多海报」按钮
- 去重：同一用户同一会话内可重复上报。
- 属性（1）：
  - `user_id` 用户ID（string，必填）：白名单用户ID

**poster_template_enable_click** — 通用海报启用点击 ｜ 平台:H5/Server ｜ 模块:share_poster ｜ 类型:点击 ｜ 状态:
- 触发时机：用户点击通用海报「启用」按钮
- 去重：同一模板同一会话内可重复上报。
- 属性（1）：
  - `template_id` 模板ID（string，必填）：通用海报模板ID

**custom_poster_upload_success** — 自定义海报上传成功 ｜ 平台:H5/Server ｜ 模块:share_poster ｜ 类型:接口返回结果 ｜ 状态:
- 触发时机：用户上传自定义图片成功
- 去重：同一图片上传任务仅上报一次。
- 属性（1）：
  - `user_id` 用户ID（string，必填）：上传海报的用户ID

**custom_poster_enable_click** — 自定义海报启用点击 ｜ 平台:H5/Server ｜ 模块:share_poster ｜ 类型:点击 ｜ 状态:
- 触发时机：用户点击自定义海报「启用」按钮
- 去重：同一用户同一会话内可重复上报。
- 属性（1）：
  - `user_id` 用户ID（string，必填）：启用自定义海报的用户ID

**poster_switch_success** — 海报切换成功 ｜ 平台:H5/Server ｜ 模块:share_poster ｜ 类型:接口返回结果 ｜ 状态:
- 触发时机：启用操作接口返回成功
- 去重：同一海报同一会话内可重复上报。
- 属性（2）：
  - `poster_type` 海报类型（string，必填）：切换后的海报类型
  - `poster_id` 海报ID（string，必填）：切换后的海报ID

### L2 层

**profile_submit** — 提交健康档案（首次建档） ｜ 平台:Android/iOS ｜ 模块:profile ｜ 类型:提交 ｜ 状态:已完成
- 触发时机：仅首次建档 ：用户完成6步引导式健康档案的某一步并提交
- 去重：不限制。
- 属性（4）：
  - `step_index` 步骤序号（number，必填）：步骤序号（1-6）
  - `step_name` 步骤名称（string，必填）：步骤名称
  - `profile_fields` 档案字段列表（string，选填）：本步骤已填字段名列表（分号分隔；只传字段名，不传健康数据值）
  - `completion_rate` 完成度（number，必填）：档案整体完成度（百分比）

**profile_update** — 更新健康档案（编辑/补填） ｜ 平台:Android/iOS ｜ 模块:profile ｜ 类型:提交 ｜ 状态:无需处理
- 触发时机：用户 非首次 编辑/补填健康档案时提交（手动修改、AI引导补填、对话中补充、识别结果录入、记忆补充）
- 去重：不限制，每次有效更新均上报。
- 属性（7）：
  - `edit_section` 编辑区域（string，必填）：编辑区域（对应档案分区，非步骤）
  - `member_ids` 记忆画像ID（string，—）：本次编辑的字段涉及多昵称档案更新（多member id时，使用‖进行分割）
  - `edited_fields` 编辑字段列表（string，必填）：本次编辑的字段名列表（分号分隔；不得传字段值）,如果存在多个menber_id时，需要使用||进行分割
  - `record_id` 更新字段（string，—）：本次编辑的字段名列表（分号分隔；不得传字段值）
  - `update_source` 更新来源（string，必填）：档案更新来源
  - `new_field_count` 新增字段数（number，必填）：本次由空值变为有值的字段数量
  - `field_count_after` 更新后已填字段数（number，必填）：编辑后该 member_id 的已填字段总数（用于追踪档案完整度变化曲线）

**quick_question_click** — 开屏问题点击 ｜ 平台:Android/iOS ｜ 模块:dialogue ｜ 类型:点击 ｜ 状态:无需处理
- 触发时机：用户点击对话页顶部的某个开屏问题
- 去重：不限制。
- 属性（4）：
  - `exposure_id` 曝光ID（string，必填）：对应quick_question_view的曝光ID
  - `question_id` 问题ID（string，必填）：用户点击的问题ID
  - `question_text` 问题文案（string，必填）：问题文案（用于后台对照）
  - `click_position` 点击位置（number，必填）：问题在本次展示列表中的位置（1/2/3）

**dialogue_send** — 发起AI对话 ｜ 平台:Android/iOS ｜ 模块:dialogue ｜ 类型:发送 ｜ 状态:已完成
- 触发时机：用户在对话页发送一条消息
- 去重：不限制，每条消息均上报。
- 属性（7）：
  - `dialogue_id` 对话ID（string，必填）：对话ID，唯一标识一次对话会话
  - `message_id` 消息ID（string，必填）：用户消息ID，用于与Coze单条消息日志关联
  - `message_type` 消息类型（string，必填）：消息类型
  - `is_first_message` 是否首条消息（boolean，必填）：是否本次对话的首条消息
  - `help_type` 帮助类型（string，选填）：用户选择的帮助类型
  - `quick_question_id` 快捷问题ID（string，选填）：若本次对话由开屏问题触发，传问题ID；手动输入为空
  - `trigger_type` 触发类型（string，必填）：对话触发方式

**product_detail_view** — 查看产品详情 ｜ 平台:H5 ｜ 模块:product ｜ 类型:浏览 ｜ 状态:无需处理
- 触发时机：图2所示H5商品详情页核心内容加载成功并可见
- 去重：同一session内同一product_id可重复上报。
- 属性（5）：
  - `click_id` 点击ID（string，必填）：来源purchase_link_click的点击ID，从App透传到H5
  - `product_id` 产品ID（string，必填）：产品ID
  - `product_name` 产品名称（string，必填）：产品名称
  - `source` 来源（string，必填）：来源
  - `recommend_id` 推荐批次ID（string，选填）：推荐批次ID（来源为recommend时填写）

**recommend_view** — 推荐结果曝光 ｜ 平台:Android/iOS ｜ 模块:recommend ｜ 类型:曝光 ｜ 状态:已完成
- 触发时机：AI推荐结果展示给用户
- 去重：同一对话轮次中同一message_id仅上报一次。
- 属性（5）：
  - `message_id` 推荐批次ID（string，必填）：推荐批次ID
  - `recommend_source` 推荐来源（string，必填）：推荐来源
  - `dialogue_id` 对话ID（string，条件必填）：来源对话ID；recommend_source=dialogue时必填
  - `recommend_count` 推荐产品数（number，必填）：推荐产品数量
  - `product_ids` 产品ID列表（string，必填）：推荐产品ID列表（分号分隔）

**report_upload** — 上传体检报告 ｜ 平台:Android/iOS ｜ 模块:profile ｜ 类型:接口返回结果 ｜ 状态:无需处理
- 触发时机：用户发起上传后，单次上传任务返回成功或失败结果
- 去重：每个upload_id只上报一次最终结果。
- 属性（7）：
  - `upload_id` 上传任务ID（string，必填）：单次上传任务ID
  - `report_type` 报告类型（string，必填）：报告类型
  - `upload_source` 上传来源（string，必填）：上传入口来源
  - `file_type` 文件类型（string，必填）：文件类型
  - `file_size` 文件大小（number，选填）：文件大小（KB）
  - `upload_result` 上传结果（string，必填）：上传结果
  - `fail_reason` 失败原因（string，选填）：失败原因（仅fail时填写）

**scan_complete** — 完成图片识别 ｜ 平台:Android/iOS ｜ 模块:scan ｜ 类型:接口返回结果 ｜ 状态:无需处理
- 触发时机：相机/相册识别流程进入终态：成功、失败、超时、用户取消或相机权限被拒绝
- 去重：每个scan_id只上报一次最终结果。
- 属性（7）：
  - `scan_id` 识别任务ID（string，必填）：单次识别任务ID，必须与scan_entry一致
  - `scan_type` 识别类型（string，必填）：识别类型
  - `scan_result` 识别结果（string，必填）：识别结果
  - `result_count` 结果数量（number，选填）：识别结果数量（成功时）
  - `scan_duration` 识别耗时（number，必填）：从scan_entry到流程终态的耗时（毫秒）
  - `error_code` 错误码（string，条件必填）：失败或超时时的错误码
  - `failure_stage` 失败阶段（string，条件必填）：未成功时所处阶段；cancel可选，其他失败结果必填

**feedback_click** — 点击对话反馈 ｜ 平台:Android/iOS ｜ 模块:feedback ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：用户点击AI回复下方的反馈按钮
- 去重：不去重，每次状态变化均上报；分析时按message_id取最新事件。
- 属性（4）：
  - `dialogue_id` 对话ID（string，必填）：对话ID
  - `message_id` 消息ID（string，必填）：消息ID（AI回复的消息标识）
  - `feedback_type` 反馈类型（string，必填）：反馈类型
  - `feedback_action` 反馈动作（string，必填）：本次操作：select(选择) / cancel(取消)

### L3 层

**purchase_link_click** — 点击查看商品 ｜ 平台:Android/iOS ｜ 模块:purchase ｜ 类型:点击 ｜ 状态:已完成
- 触发时机：用户点击对话推荐卡片的“查看”或其他商品入口，准备打开H5商品详情
- 去重：不限制。
- 属性（7）：
  - `click_id改为message_id，用于归因` 点击ID（string，必填）：单次跳转ID，写入H5 URL并贯穿订单归因
  - `source` 来源（string，必填）：入口来源：dialogue_recommend / service_goods / service_live / qui…
  - `product_id` 产品ID（string，必填）：产品ID
  - `product_name` 产品名称（string，必填）：产品名称
  - `purchase_channel` 购买渠道（string，必填）：购买渠道
  - `recommend_id` 推荐批次ID（string，选填）：推荐批次ID（来源推荐时填写）
  - `dialogue_id` 会话ID（string，选填）：关联对话ID（来源对话时填写）

**purchase_confirm** — 订单创建成功 ｜ 平台:H5/Server ｜ 模块:purchase ｜ 类型:接口返回结果 ｜ 状态:已完成
- 触发时机：H5提交订单后，业务服务端返回订单创建成功
- 去重：按order_id幂等去重，每个订单仅上报一次。
- 属性（9）：
  - `order_id` 订单ID（string，必填）：业务订单唯一ID
  - `click_id改为message_id，用于归因` 点击ID（string，必填）：来源purchase_link_click的跳转ID
  - `product_id` 产品ID（string，必填）：产品 ID
  - `product_name` 产品名称（string，必填）：产品名称
  - `product_price` 产品价格（number，必填）：产品价格（元）
  - `quantity` 购买数量（number，必填）：购买数量
  - `source_page` 来源页面（string，必填）：来源页面类型
  - `recommend_id` 推荐批次ID（string，选填）：来源推荐批次 ID（从 App 带入 H5 URL 参数）
  - `dialogue_id` 对话ID（string，选填）：来源对话 ID（从 App 带入 H5 URL 参数）

**profile_complete** — 完整建档完成 ｜ 平台:Android/iOS ｜ 模块:profile ｜ 类型:接口返回结果 ｜ 状态:无需处理
- 触发时机：用户档案完整度 首次 达到100%时触发（无论首次6步建档还是后续补填）
- 去重：每个member_id仅触发一次，无论首次建档还是后续补填。
- 属性（5）：
  - `complete_source` 完成来源（string，必填）：完成来源
  - `guide_duration` 引导总耗时（number，选填）：首次建档引导总耗时（毫秒）。起点：步骤1首次可见；终点：步骤6提交成功并达到100%
  - `completion_rate` 完成度（number，必填）：完成度（完整建档=100）
  - `field_count` 已填字段总数（number，必填）：已填字段总数
  - `has_report` 是否上传报告（boolean，必填）：是否上传体检报告

**feedback_submit** — 提交差评反馈 ｜ 平台:Android/iOS ｜ 模块:feedback ｜ 类型:提交 ｜ 状态:已完成
- 触发时机：用户提交差评反馈表单（选原因+填文字）
- 去重：同一feedback_click后仅上报一次。
- 属性（4）：
  - `dialogue_id` 对话ID（string，必填）：对话ID
  - `message_id` 消息ID（string，必填）：消息ID
  - `feedback_reasons` 反馈原因列表（string，必填）：反馈原因列表（分号分隔）
  - `has_feedback_text` 是否填写文字反馈（boolean，必填）：是否填写文字反馈；原文不得上报友盟，应存入受控业务数据库

**retention_return** — 复访对话 ｜ 平台:Android/iOS ｜ 模块:retention ｜ 类型:服务端派生 ｜ 状态:无需处理
- 触发时机：用户在首次对话日后的第1/7/30个自然日再次发起首条消息，由服务端派生
- 去重：同一user_id+cohort_date+dialogue_id仅一条。
- 属性（4）：
  - `return_typeg改为dialogue_id` 回访类型（string，必填）：回访类型
  - `cohort_date` 队列日期（string，必填）：用户首次发起对话的自然日（队列日期）
  - `return_date` 回访日期（string，必填）：本次回访自然日
  - `return_date` 回访日期（string，必填）：本次回访自然日
