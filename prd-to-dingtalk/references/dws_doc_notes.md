# dws doc 常用命令速查

## 创建文档

```bash
# 从 Markdown 文件创建（长文自动分片）
dws doc create --name "文档标题" --content-file prd.md --format json
```

返回字段：`nodeId`、`docUrl`、`chunksWritten`。

## 读取文档

```bash
# 读取 Markdown 投影（有损，不含图片 resourceId）
dws doc read --node <nodeId> --format json

# 读取大纲（轻量，验证结构）
dws doc read --node <nodeId> --format json --content-format jsonml --scope outline

# 读取完整块结构（用于定位图片占位/合并块）
dws doc read --node <nodeId> --format json --content-format jsonml
```

`--node` 支持 nodeId 或完整 alidocs URL。

## 插入/修正图片

```bash
# 插入本地图片到指定块位置
# --index 为块序号，从 0 开始；可在 read 返回的 jsonml 中数段落定位
dws doc media insert --node <nodeId> --file ./local-image.png --index <N> --format json

# 删除错误合并的块
dws doc block delete --node <nodeId> --index <N> --format json
```

## 错误处理

| 错误 | 排查 |
|---|---|
| `WinError 193` | 不要从 Python subprocess 调 dws，改用 Bash |
| `--scope/--tags requires --content-format jsonml` | outline 读取必须加 `--content-format jsonml` |
| `CreateFile` / 文件解析失败 | 中间文件含 CRLF，改 `newline='\n'` |
| 图片块合并/图注丢失 | 用 `doc media insert` 按 index 重插，并用 `doc block delete` 清错 |

## 最佳实践

1. 创建后务必 `doc read` 回读验证。
2. 图片使用线上 URL，本地图片仅在 `media insert` 时临时下载。
3. 长文档分片写入可能超时，可重试同一 `doc create` 命令继续写入。

## 致命坑（2026-08-31 实测，已踩并修复）

- **`doc create --content-file` 建出空文档（无报错）**：文档 nodeId 正常返回、success:true，但 `doc block list` 只有 1 个空 paragraph。根因二选一，任一命中都静默写空：
  1. 内容文件含 CRLF：Windows 下 Python `write_text` 默认把 `\n` 写成 `\r\n`，dws 读 content-file 时因 CRLF 解析失败→静默写空。**必须保证文件是 LF**。
  2. 未显式指定 `--content-format markdown`：本应默认 markdown，但实测默认不生效，必须显式带 `--content-format markdown`，否则长文自动分片后内容落空。
  - 正确姿势：`dws doc create --name "<标题>" --content-file prd.md --content-format markdown --timeout 120 --format json`（>10KB 自动分片，回显 `chunksWritten=2` 即成功；serverResponse.mode 显示 append 是误导，回读有内容才为真成功）。
  - 小文内联 `--content "# 标题"` 也务必带 `--content-format markdown`，否则同样空文档。
- **Python 规范化换行千万别“开写即读”**：`open(f,'w').write(open(f).read())` 会先把 f 截断为空，再读到空→文件被清空。必须 `d=open(f).read(); open(f,'w',newline='\n').write(d)`（先读进内存再开写）。
- **`doc update --mode overwrite --content-file` 可用（长文覆盖首选）**：实测 `dws doc update --mode overwrite --content-file <md>` 对 400 块 + 16 图文档成功（2026-09-07）。**仅**不带 `--mode overwrite` 的普通 `doc update` 才只接受内联 `--content`（<2KB）。覆盖同一篇用 `update --mode overwrite --content-file`，不要退回 `doc create` 重建。
- **删除文档**：`dws doc delete` 已 deprecated，改用 `dws drive delete --node <id> --yes`（进回收站，30 天可恢复）。
- **`doc read --format json` 的 markdown 字段可能为空**：那是投影延迟/有损，以 `dws doc block list`（totalCount 与段落 text）或 `--content-format jsonml` 为准判断内容是否真写入。
- **绝对路径带 `C:/` 冒号会破坏 dws 参数解析**：`doc update --content-file C:/...` 报“必须提供内容”。content-file 一律用相对路径（当前工作目录）。
- **`doc update --mode append` 读回滞后 → 盲重试双写（2026-09-03 反复中招）**：`doc update --mode append` 返回 `TIMEOUT_ERROR`/`business_error` 时，**内容实际可能已写入**。若在返回错误后立刻 `doc read` 读回校验、看到哨兵 MISSING 就重试 → 会把同一片再写一遍，造成文档重复（vNG4、Amq4 两篇都被写乱成双份/多份）。
  - **根因**：钉钉读回有最终一致性滞后（秒级），append 成功后紧跟的 read 经常读不到新内容 → 假阴性 MISSING。
  - **根治写法**：① 每个分片**只 append 一次，绝不因读回 MISSING 而重试**；② 全部 append 完末尾 `sleep 30` 等收敛，再读回**只对确缺失的分片补缺**（此时读回已稳定，缺失=真缺失，补一次不会重复）；③ 若必须验证，读回后比对用**标题标签（h2/h3/h4）的 leaf 文本**，不要 substring 匹配——文档顶部「目录」里的「五、…」等纯文本会让 substring 哨兵误判为重复。
  - 经验阈值：分片 >~7.7KB 仍偶发 TIMEOUT，切成 ~3.3KB/片稳定；长文 create 一次性 >~9.8KB 也会 TIMEOUT，同样切小片。

## 大文档嵌图 / 本地图渲染嵌入（2026-09-07 补充）

- **大文档(>~380块)内嵌图片：组合技可行**：先 `dws doc media insert --file <png> --ref-block <blockId> --where after` 单独插图拿钉钉内部路径 `/core/api/resources/img/<hash>`，再把该内部路径替换进 markdown 外链，最后 `dws doc update --mode overwrite --content-file <md>` 覆盖整篇。单篇 400 块 + 16 图实测成功。
- **`media insert` 落库校验坑（关键，勿重试）**：大文档上 `media insert --file` 返回 `verify=false` / `+media-list count:0` 是**瞬时验证窗口假象，不可信**。真落库信号：回读该节 `doc read --content-format jsonml --scope range` 后，**块数 +1 且 img tag 计数 +1**（新块内嵌 `src=/core/api/resources/img/...`）。不要因 verify=false 就重试——重试会双写。
- **源 SVG/HTML 流程图 → 钉钉 四步法**（本地 PRD 里的 SVG 在 markdown 投影中会被丢，只留文字）：
  1. 从源 HTML 用 `indexOf`/正则锚定目标 `<svg>…</svg>` 片段；
  2. 包最小 HTML（白底 `<body style="margin:0;background:#fff">` + `<style>svg{width:1000px}</style>`）整体载入；
  3. Playwright headless Chromium `deviceScaleFactor=2` 截该 svg 元素 → 高清 PNG（约 2000px 宽）；
  4. 走上面「media insert 组合技」插入钉钉。脚本模板见项目 `_render_flow_v051.js`（改锚点即可复用）。
- **插入位置**：`--ref-block <标题块uuid> --where after`；插完若标题与下节间夹了原空段落，用 `dws doc block delete --block-id <id> --yes` 清掉。

## v1.0.61 真实命令树（2026-09-08 探针确认，覆盖旧 notes）

> 本机 `dws version` = v1.0.61（build 2026-08-31）。旧 notes 仅记了 `block delete` + `media insert`，已过时。以下为实测可用能力，增量同步（见 `references/incremental_sync.md`）依赖它们。

- **`dws doc block list [--content-format jsonml]`**：枚举一级块，返回稳定 `blockId`（UUID）。`--block-type heading` / `--start-index/--end-index` 过滤。**图片块真身 = `p` 段落内嵌 `img` 子节点**，`img.src` 即 resourceUrl（默认 element 视图会把图片块显示成空 `paragraph`，须用 `--content-format jsonml` 才看得到 `img`）。
- **`dws doc block insert`**：插块。`--content "段落"` / `--heading "标题" --level N` 快捷；`--element '<jsonml|element JSON>'` 高级；`--ref-block <BLOCK_ID> --where before|after` 锚点定位（**不怕索引漂移**）；`--index N` 备选。块类型：paragraph/heading/blockquote/callout/columns/orderedList/unorderedList/table/sheet/attachment/slot。
- **`dws doc block update`**：`--block-id <ID> --content "新内容"` 或 `--element '<jsonml>'` 原地改块。
- **`dws doc block delete`**：`--block-id <ID>` 删块。
- **`dws doc media upload --node <id> --file <png> --yes`**：**仅上传、不插入**，返回稳定 `resourceId` + `resourceUrl`（绑定该 nodeId，不可跨 node 复用；PRD 永远覆盖同一篇，契合）。这是「媒体库/可复用资产」。
- **`dws doc media insert --node --file --index`**：上传+插入一步，返回 `blockId`/`resourceId`/`resourceUrl` + `verified`。
- ⚠️ **resourceUrl 不是内容定存的**：同一张图 `media insert` 与 `media upload` 返回的 resourceUrl 后缀不同。故**必须首次拿到后存进 manifest 复用**，不能指望重传拿同 URL。
- ✅ **预上传资产可直接引用进图片块（不二次 OSS 上传，已实测）**：`dws doc block insert --node <id> --content-format jsonml --element '["p",{},["span",{"data-type":"text"},["span",{"data-type":"leaf"},""]],["img",{"src":"/core/api/resources/img/<hash>"}],["span",{"data-type":"text"},["span",{"data-type":"leaf"},""]]]'` → 用 `media upload` 拿到的 resourceUrl 插出图片块，零重传。
- 改名文档用 `dws drive rename`（非 `doc update`）。
