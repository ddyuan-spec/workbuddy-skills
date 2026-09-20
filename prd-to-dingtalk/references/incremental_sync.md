# 增量同步（Incremental Sync）设计

> 解决痛点：全量 overwrite 每轮把全部图片重新 `media insert` 上传一遍，耗 OSS/时间，大文档必踩 verify 坑。
> 实测 dws v1.0.61 已支持块级编辑 + 媒体库（见 `dws_doc_notes.md` 末节），故可改为「只动改动」。
> 本文件是 skill 改法设计；落地执行脚本（`scripts/dingtalk_incremental.py`）为后续实现项，未含在本文件。

## 已实测确认的能力（dws v1.0.61，2026-09-08 探针，临时文档测完即删）
- `media insert --node --file --index`：上传+插入，返回 `blockId`/`resourceId`/`resourceUrl`，`verified:true`。
- `media upload --node --file --yes`：仅上传，返回稳定 `resourceId`+`resourceUrl`，**不插入正文**；资源绑定该 nodeId，不可跨 node 复用（PRD 永远覆盖同一篇 → 契合）。
- `block list --content-format jsonml`：枚举块，返回稳定 `blockId`；图片块真身是 `p` 内嵌 `img`，`img.src` = resourceUrl。
- `block insert --content-format jsonml --element '<jsonml>'`：**可用预上传(media upload)的 resourceUrl 直接插出图片块，不二次 OSS 上传（已实测成功）**。
- `block update --block-id --content/--element`、`block delete --block-id`：原地改/删。
- ⚠️ resourceUrl **不是内容定存的**：同图 `media insert` 与 `media upload` 返回的 URL 后缀不同 → 必须把首次 URL 存进 manifest 复用，不能指望重传拿同 URL。

## manifest 结构（`_dingtalk_sync/<prd_basename>.json`，随 PRD 走，可提交）
```json
{
  "nodeId": "b9Y4gmKWrdzEGPdkIe3yqpElJGXn6lpz",
  "version": "V0.1.1",
  "githubSha": "<上次已推 raw HTML 的 blob sha>",
  "blocks": [
    { "anchor": "h1:一、项目背景", "blockId": "mts9...", "hash": "sha256..." }
  ],
  "images": [
    { "key": "svg:fig_flow | url:https://.../x.png | alt:流程图",
      "hash": "sha256 of 源字节/SVG 源",
      "resourceUrl": "/core/api/resources/img/...",
      "blockId": "mts9..." }
  ]
}
```
- `images.key`：SVG 图用 `<svg>…</svg>` 源片段哈希；位图用 源字节哈希 或 `GitHub URL + ETag`。
- `hash` 用于判定「图是否变化」，是增量的判据。

## 模式 A：图片增量 + 文本全量（默认，低风险，覆盖 90% 场景）
1. 脚本转 MD。
2. 抽图逐张算源哈希：命中 manifest 同 hash → **复用旧 resourceUrl（不传）**；变化/新增 → `media upload`（或 `media insert`）拿新 URL，写回 manifest。
3. 拼零外链 MD（图 src = 复用 URL / 新 URL）。
4. `doc update --mode overwrite --content-file <md>`（文本全量，但图片已增量）→ 回读验证（github=0 / core/api/resources>0）。
5. 若本轮**文字零改动且仅有图片变化**：可跳过 overwrite，直接对变化图做 `block insert/update`（见模式 B 图片部分），避免无谓重传整篇文本。
- 收益：每轮只传「变化/新增」图；文本 overwrite 确定性、便宜、表格等复杂块零风险。

## 模式 B：块级真增量（进阶，规避 overwrite 超时）
前置：manifest 已有基线 blockIds（首推/重置后建立；**一旦某轮用 overwrite，blockId 全重置，须重建基线**）。
1. `block list --content-format jsonml` 取当前块（blockId + hash）。
2. 比对新源块序列 vs manifest：
   - 文本块 hash 变 → `block update --block-id <stored> --content/--element`。
   - 新增块 → `block insert --ref-block <邻块 blockId> --where after --content/--element`（锚点防漂移）。
   - 删除块 → `block delete --block-id`。
3. 图片块：
   - 复用 URL 的不变图 → 不动。
   - 变化/新图 → `media upload` 拿 URL → `block insert/update` 用 jsonml `<p><img src=URL>></p>` 放置（**不重传**）。
4. 更新 manifest（新 blockIds、新 hash、新 resourceUrl）。
5. 验证：`block list` / `doc read` 结构完整 + 图片 src 零外链。
- 风险：表格/复杂块需拼 JSONML（`block update --element`）；中段插入靠 blockId 锚点；基线被 overwrite 破坏须重建。

## 何时用哪种
- 绝大多数 PRD 小改 → **模式 A**（图片增量已省主要成本）。
- 文档极大、overwrite 频繁超时 → **模式 B**。

## 落地状态（2026-09-08 已实现并验证）
- **`scripts/dingtalk_incremental.py` 已实现（模式 A）并离线+在线双验证通过**：
  - 抽图算指纹、读/写 manifest、比对基线、判定 REUSE/CHANGED/NEW。
  - 指纹优先用线上 ETag（HEAD 比对，命中则跳过下载）；无 ETag 或本地模式退回 sha256。
  - `--dry-run`：只分析+报告+写基线指纹（不传、不写 resourceUrl）。
  - `--apply`：产出零外链 MD（REUSE 图已填旧 URL）+ `dws` apply 脚本（`media upload` 仅变化图 → 填 URL → `doc update --mode overwrite` → 回读门禁）。dws 调用全部在 Bash 里执行，遵守 skill 红线。
  - 验证结果：图生视频 PRD（13 图）→ 首轮 13 NEW；同图二次 13 REUSE/0 上传；改 1 图 12 REUSE+1 CHANGED（8% 上传）。在线 Run2 仅发 HEAD、0 下载。
- **模式 B（块级真增量）仍为 TODO**：需 `block list` 建立基线 blockId 映射 + 块级 diff/apply（含表格 JSONML、中段插入锚点），待有「大文档 overwrite 频繁超时」的真实需求再实现。

## 真实首推记录（图生视频 PRD，2026-09-08）
- 用 `lvyunjia-video-prd.html`（V0.1.1 确认版，本地含全部确认标记）作源，nodeId `b9Y4gmKWrdzEGPdkIe3yqpElJGXn6lpz`。
- **流程图坑（已解决）**：转换脚本会剥离内联 `<svg>`，而线上文档有 2 张 SVG 流程图（业务流程图 / 单条作品状态机，上次手工渲染 PNG 插入）。直接 `overwrite` 13 张 `<img>` 会丢这 2 张图。处理：从线上 `block list` 抽出 2 张流程图 resourceUrl，注入 zeroext MD 的对应标题下（`### 3.2 业务流程图` / `#### 3.4.1 单条作品状态`），再 overwrite。回读验证 15 图全内部、0 外链、流程图与关键正文（再次生成×5 / 生成状态通知 / V0.1.1×7）全在，文档零退化。
- **apply 脚本 bug（已修）**：原替换步骤用内联 `python -c "…def f(mt):…"`（`def` 不能跟 `;` 同行）→ SyntaxError；改为生成独立 `_substitute.py` 文件调用。`RESULTS` 路径也由 `mktemp`(/tmp 在 Windows 无效) 改为 out-dir 绝对路径。
- 首轮基线：13 张资产全部 `media upload`（首次必传，建立 baseline），2 张流程图复用旧 URL。基线 manifest 已落 `_dingtalk_sync/lvyunjia-video-prd.json`（13 资产含 GitHub ETag + 2 流程图含 anchor）。
- **验证收益**：用该 baseline 对未改动 PRD 再跑 → 13 REUSE / 0 上传 / 0 下载（在线 HEAD etag 命中即跳过下载）。即下轮真实改图生视频 PRD 推送，只有变化的图才上传。
- 回读验证命令（能数图的范围）：`dws doc read --node <node> --content-format jsonml --scope tags --tags img`（outline 范围不含图片块，勿用其判图数）。

## 用法（模式 A）
```bash
# 离线校验（不碰钉钉）：用本地资源目录算指纹，建立/比对基线
python scripts/dingtalk_incremental.py <prd.html> --mode A --dry-run \
    --manifest _dingtalk_sync/<base>.json --local-assets-dir _prd_imgs_xxx --offline

# 真实应用：生成 apply 脚本（由 Bash 跑 dws，仅传变化图）
python scripts/dingtalk_incremental.py <prd.html> --node <nodeId> --mode A \
    --manifest _dingtalk_sync/<base>.json --apply
bash _dingtalk_sync/_dingtalk_apply_<nodeId>.sh
```
- manifest 字段已落地：`images: { <key>: { identity, etag?, resourceUrl? } }`；`identity` 在线为 `etag:<etag>`，本地/无 etag 为裸 sha256。
- ⚠️ 首次对某 PRD 跑（manifest 为空）仍会全量上传建基线；收益从第二次起体现。
- ⚠️ 内联 SVG 流程图：转换脚本会剥离，本脚本只追踪 `<img>` 资产；SVG 渲染→PNG 仍走既有手工流程，不在增量脚本内。
