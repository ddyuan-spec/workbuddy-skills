#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRD 结构排查脚本
扫描一份 PRD 文档（.md/.txt/.docx/.html），对照必含板块清单，
分四阶段输出报告：
  阶段1（结构存在性）：一~九 必含板块是否出现（缺失即不通过）。
  阶段2（§D 内容深度）：功能需求详情是否达到"模板式详清"门槛
        （逐页原型截图 / 字段明细表 / 按钮权限表 / 逐步操作逻辑 /
         查询条件规格 / 数据来源标注 / 计算公式 / 显示位置等）。
  阶段3（待确认项扫描）：检测全文"待确认/需确认/@X确认/TBD/待补充"等
        标记，提醒向用户澄清或保留占位，禁止臆测填充。
  阶段4（红线与图文一致性）：扫描越界红线词（用户裁定不纳入的端口/能力）、
        待确认项悬空（引用字段正文未定义）、埋点表是否符合《泰小虎埋点表v2.3》
        双表规范或已链接引用、以及图文一致性人工核对清单。
缺失板块、深度单薄项或待确认项，交由调用方（WorkBuddy）向用户反问补充。

用法：
    python check_prd.py <prd文件.md|docx|html|txt>
"""

import sys
import os
import re
import zipfile
from xml.etree import ElementTree as ET

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
def q(t): return '{%s}%s' % (NS['w'], t)


# ---------------------------------------------------------------------------
# 文本抽取
# ---------------------------------------------------------------------------
def extract_docx(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read('word/document.xml'))
    out = []
    for p in root.iter(q('p')):
        for t in p.iter(q('t')):
            out.append(t.text or '')
    return '\n'.join(out)


def extract_html(path):
    with open(path, encoding='utf-8', errors='ignore') as f:
        html = f.read()
    html = re.sub(r'<script.*?</script>', ' ', html, flags=re.S | re.I)
    html = re.sub(r'<style.*?</style>', ' ', html, flags=re.S | re.I)
    heads = re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', html, flags=re.S | re.I)
    heads = [re.sub(r'<[^>]+>', '', h) for h in heads]
    plain = re.sub(r'<[^>]+>', ' ', html)
    return '\n'.join(heads) + '\n' + plain


def get_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        return extract_docx(path)
    if ext in ('.html', '.htm'):
        return extract_html(path)
    with open(path, encoding='utf-8', errors='ignore') as f:
        return f.read()


# ---------------------------------------------------------------------------
# 阶段1：一~九 板块存在性（对齐《PRD输出规范与标准示例(260715)》）
# ---------------------------------------------------------------------------
# 四、功能需求详情 存在性只看"功能需求详情/页面："标题，不再把 需求影响范围/涉及终端 当作命中词
REQUIRED = [
    ("一、文档基本信息", ["文档基本信息", "历史修订记录", "修订记录"]),
    ("二、项目背景与目标", ["项目背景", "业务背景", "项目目标", "衡量指标", "kpi"]),
    ("三、业务流程与架构", ["业务流程图", "信息架构", "状态机", "状态流转", "状态流转规则"]),
    ("四、功能需求详情", ["功能需求详情", "页面：", "页面原型与交互示意", "详细逻辑规则"]),
    ("五、非功能性需求", ["非功能性需求", "非功能需求", "埋点需求", "埋点表", "事件名称", "上报参数"]),
    ("六、验收标准", ["验收标准", "关键场景", "given", "when", "then"]),
    ("七、关键边界设计检查清单", ["边界设计检查清单", "关键边界", "自检表", "检查清单"]),
    ("八、文档维护与变更规范", ["文档维护", "维护与变更", "变更规范", "变更周知", "版本号规范"]),
    ("九、待确认项汇总", ["待确认项汇总", "待确认"]),
]


# ---------------------------------------------------------------------------
# 阶段2：§D 内容深度子项（模板式详清门槛）
# ---------------------------------------------------------------------------
# §四 页面式深度子项（对齐 260715：每个页面含 X.1 原型与交互 + X.2 详细逻辑→界面与展示规则/业务逻辑与边界条件）
DEPTH_ITEMS = [
    ("页面原型与交互示意(逐页截图)", ["页面原型与交互示意", "原型", "截图", "线框图",
                                   "仿真原型", "figure", "<img", "figcaption"]),
    ("界面与展示规则(字段表/按钮权限/显示位置)", ["界面与展示规则", "展示规则",
                                              "字段名称", "权限", "显示位置", "按钮"]),
    ("业务逻辑与边界条件(操作逻辑/数据来源/边界)", ["业务逻辑与边界条件", "边界条件",
                                                 "操作逻辑", "逐步", "前置条件",
                                                 "数据来源", "来自前端", "来自后端",
                                                 "第三方接口", "取《", "调", "接口"]),
    ("交互说明", ["交互说明", "手势", "动态反馈", "弹窗", "滑动", "点击"]),
    ("计算公式/数据演练", ["计算公式", "演练", "计算规则", "逻辑"]),
    ("涉及终端明细", ["涉及终端", "终端明细", "涉及终端明细"]),
    ("需求影响范围", ["需求影响范围", "冲击老版本", "影响范围"]),
]
# 缺失超过该阈值 → 判为"深度单薄"
DEPTH_WARN_THRESHOLD = 3


# ---------------------------------------------------------------------------
# 阶段4：红线词 / 待确认溯源 / 埋点v2.3规范 / 图文一致性 扫描
# 沉淀自「直播挂车与时长发券」需求评审踩坑：图文臆造、范围外误入、埋点不规范
# ---------------------------------------------------------------------------
# 红线词：用户已裁定不纳入本项目的端口/能力（出现即须有明确"不涉及"豁免声明）
RED_LINE_TERMS = ["商家端后台", "商家端", "回放", "火山SaaS", "火山 SaaS",
                  "SaaS配置", "SaaS 配置", "火山引擎直播配置", "火山直播配置"]
RED_LINE_EXEMPT = ["不涉及", "不涵盖", "不在范围", "排除", "本期不含",
                   "本需求不含", "不含", "未涉及", "明确范围外", "不配置",
                   "不开放", "不新增", "不支持"]
# 《泰小虎埋点表 v2.3》双表规范核心列（命中≥阈值视为符合）
V23_CORE_COLS = ["事件编号", "项目", "所属层", "平台", "模块", "事件英文名",
                 "事件显示名", "事件类型", "属性英文名", "属性显示名",
                 "数据类型", "属性说明", "触发时机", "必填性", "示例值",
                 "上报时机", "去重规则", "校验规则", "状态", "测试进度"]
V23_MIN_HIT = 12
# 简化版埋点表特征列（5列版，禁止）
SIMPLIFIED_TRACKING_COLS = ["所属终端", "所在页面", "事件名称", "触发时机", "上报参数"]
# 图文一致性：图说关键词
DIAGRAM_KW = ["流程图", "架构图", "范围图", "状态机", "时序图", "信息架构图"]


# ---------------------------------------------------------------------------
# 阶段4 扫描函数
# ---------------------------------------------------------------------------
def scan_red_line(text):
    """红线词：用户裁定不纳入的端口/能力，出现须有明确'不涉及'豁免声明。"""
    warns = []
    for term in RED_LINE_TERMS:
        for m in re.finditer(term, text):
            ctx = text[max(0, m.start() - 30): m.start() + 30]
            if not any(ex in ctx for ex in RED_LINE_EXEMPT):
                warns.append(
                    f"红线词「{term}」出现且附近无豁免声明（不涉及/不在范围等）；"
                    f"若为范围外请明确写「本需求不涉及{term}」，禁止作为功能实现描述")
                break
    return warns


def scan_uncertain_traceability(text):
    """待确认溯源：待确认项引用的字段/概念须在正文其他位置有定义，悬空则告警。"""
    warns = []
    pat = re.compile(r'待确认\s*@[\u4e00-\u9fa5A-Za-z]+[：:]\s*([^\n。；;]{2,60})')
    for m in pat.finditer(text):
        item = m.group(1)
        fields = re.findall(r'[「""]([^」""]+?)[」""]', item)
        for f in fields:
            cnt = len(re.findall(re.escape(f), text))
            if cnt <= 1:
                warns.append(
                    f"待确认项疑似悬空：引用字段「{f}」全文仅出现 {cnt} 次"
                    f"（仅在待确认处），正文未定义；请确认属正文已定义字段，否则删除该待确认")
    return warns


def scan_tracking_v23(text, norm):
    """埋点规范：须符合 v2.3 双表或链接引用独立文档，禁止 5 列简化版。"""
    warns = []
    has_tracking = ('埋点' in norm) or ('事件名称' in norm) or ('上报参数' in norm)
    if not has_tracking:
        return warns
    linked = ('埋点规范 v2.3' in text) or ('taixiaohu-tracking' in norm) or \
             ('live-tracking' in norm) or ('独立文档' in text and '埋点' in text)
    if linked:
        return warns
    hit_cols = [c for c in V23_CORE_COLS if c in text]
    if len(hit_cols) < V23_MIN_HIT:
        simp = [c for c in SIMPLIFIED_TRACKING_COLS if c in text]
        if simp:
            warns.append(
                "埋点表为简化版（含 " + "/".join(simp) + "），不符合《泰小虎埋点表v2.3》"
                "双表规范；须改为 v2.3 双表或改为链接引用独立文档")
        else:
            warns.append(
                f"埋点表仅命中 v2.3 核心列 {len(hit_cols)}/{len(V23_CORE_COLS)}，"
                "不符合双表规范（须含事件编号/项目/所属层/平台/模块/事件英文名…/校验规则/状态等）")
    return warns


def scan_diagram_consistency(text):
    """图文一致性：检出图说关键词后输出人工核对清单（图内文字不可直接解析）。"""
    found = [k for k in DIAGRAM_KW if k in text]
    if not found:
        return [], []
    checklist = [
        "流程图节点须与正文主流程逐条对应，不含正文未定义的功能（如仅'同步'却画'创建直播间'）",
        "影响范围图依赖系统须与正文'数据层/第三方依赖'逐条对应，不含正文未列出的依赖"
        "（如'用户账号/画像''商城订单''优惠券模块'若正文未列为依赖则违规）",
        "状态枚举须对接真实接口文档枚举值，禁止假设（如'违规下播'若接口无此值则须删除）",
        "图中出现的字段/概念须在正文有定义",
    ]
    return found, checklist


def main():
    if len(sys.argv) < 2:
        print("用法：python check_prd.py <prd文件>")
        sys.exit(2)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"文件不存在：{path}")
        sys.exit(2)

    text = get_text(path)
    norm = text.lower()

    print("# PRD 结构排查报告")
    print()
    print(f"文件：`{os.path.basename(path)}`")
    print()

    # ---------- 阶段1 ----------
    print("## 阶段1：一~九 必含板块存在性")
    print()
    print("| 必含板块 | 状态 | 命中关键词 |")
    print("| --- | --- | --- |")
    missing = []
    for name, aliases in REQUIRED:
        hit = [a for a in aliases if a.lower() in norm]
        if hit:
            print(f"| {name} | ✅ 存在 | {', '.join(hit)} |")
        else:
            print(f"| {name} | ❌ 缺失 | — |")
            missing.append(name)

    # ---------- 阶段2 ----------
    # 深度扫描作用于「整篇文档」：只要 D 板块存在，便检查全文是否含有
    # 模板式详清子项（需求影响范围/涉及终端/界面设计/字段表/权限表/操作逻辑…
    # 可能分布在 §4.5、§7、§8 等不同章节，故不做章节边界切割，避免漏判。
    # 仅当 D 板块本身缺失时，深度扫描无意义（阶段1 已判不通过）。
    print()
    print("## 阶段2：§D 功能需求详情 — 内容深度检查（模板式详清）")
    print()
    if "四、功能需求详情" in missing:
        print("⚠️ 阶段1 已判定 四 板块缺失，深度扫描跳过（请先补齐 四 板块）。")
        depth_missing = [name for name, _ in DEPTH_ITEMS]
    else:
        print("| 深度子项 | 状态 | 命中关键词 |")
        print("| --- | --- | --- |")
        depth_missing = []
        for name, kws in DEPTH_ITEMS:
            hit = [k for k in kws if k.lower() in norm]
            if hit:
                print(f"| {name} | ✅ | {', '.join(hit)} |")
            else:
                print(f"| {name} | ❌ 缺失 | — |")
                depth_missing.append(name)

    # ---------- 阶段3：待确认项 / 臆测风险扫描 ----------
    # 扫描全文「待确认 / 需确认 / @X确认 / TBD / 待补充 / 待定 / 暂定」等标记，
    # 这些是写作者留下的不确定占位，须提醒向用户澄清或保留占位，禁止编造填充。
    print()
    print("## 阶段3：待确认项 / 臆测风险扫描")
    print()
    UNCERTAIN_PAT = re.compile(
        r'待确认|需确认|待定|暂定|待补充|待完善|待明确|TBD|不确定|'
        r'@[\u4e00-\u9fa5A-Za-z]+确认|具体逻辑需',
        re.IGNORECASE)
    uncertain_hits = [(m.start(), m.group(0)) for m in UNCERTAIN_PAT.finditer(text)]
    if uncertain_hits:
        print(f"⚠️ 检测到 **{len(uncertain_hits)} 处**待确认/不确定标记，须向用户澄清或保留占位：")
        print()
        # 取每个标记的上下文片段（含前后若干字），便于定位
        for pos, kw in uncertain_hits:
            snippet = text[max(0, pos - 18): pos + len(kw) + 18].replace('\n', ' ')
            print(f"- …{snippet}…  （命中「{kw}」）")
        print()
        print("处理要求：逐项反问用户获取确切信息后据实书写；若用户坚持先占位，")
        print("只允许保留「⚠️ 待确认 @干系人」标记，**禁止编造数值/逻辑填进去**。")
    else:
        print("✅ 未发现待确认/不确定标记。")

    # ---------- 阶段4：红线词 / 待确认溯源 / 埋点v2.3 / 图文一致性 ----------
    print()
    print("## 阶段4：红线与图文一致性扫描（沉淀自评审踩坑）")
    print()
    rl = scan_red_line(text)
    ut = scan_uncertain_traceability(text)
    tv = scan_tracking_v23(text, norm)
    dg_found, dg_check = scan_diagram_consistency(text)

    if rl:
        print(f"### 🚫 红线词告警（{len(rl)} 处）")
        for w in rl:
            print(f"- ⚠️ {w}")
        print()
    else:
        print("✅ 未发现越界红线词。")

    if ut:
        print(f"### 🔗 待确认溯源告警（{len(ut)} 处）")
        for w in ut:
            print(f"- ⚠️ {w}")
        print()
    else:
        print("✅ 待确认项均有正文锚点（或无可提取引用字段）。")

    if tv:
        print(f"### 📊 埋点规范告警（{len(tv)} 处）")
        for w in tv:
            print(f"- ⚠️ {w}")
        print()
    else:
        print("✅ 埋点表符合 v2.3 双表规范或已链接引用独立文档。")

    if dg_found:
        print(f"### 🖼️ 图文一致性人工核对（检测到图：{', '.join(dg_found)}）")
        for c in dg_check:
            print(f"- ⚠️ {c}")
        print()
    else:
        print("（未检测到图说关键词，跳过图文一致性核对）")

    # ---------- 结论 ----------
    print()
    print("## 结论")
    print()
    if missing:
        print(f"**结构不通过**（缺失 {len(missing)} 个必含板块）：" + "、".join(missing))
        print()
        print("请向用户反问补充以下板块后再定稿（不得由模型臆造）：")
        for m in missing:
            print(f"- {m}")
    else:
        print("**结构通过**（一~九 必含板块均已出现）。")
    print()
    if depth_missing:
        if len(depth_missing) > DEPTH_WARN_THRESHOLD:
            print(f"⚠️ **§D 深度单薄**（缺失 {len(depth_missing)} 项深度子项，超过阈值 {DEPTH_WARN_THRESHOLD}）：")
        else:
            print(f"ℹ️ **§D 深度提示**（缺失 {len(depth_missing)} 项深度子项，未超阈值但建议补全）：")
        print()
        print("请向用户反问补充以下 §D 详清内容（禁止臆造）：")
        for m in depth_missing:
            print(f"- {m}")
    else:
        print("✅ **§D 深度达标**：功能需求详情已达到模板式详清门槛。")
    print()
    if uncertain_hits:
        print(f"⚠️ **存在 {len(uncertain_hits)} 处待确认项**：须向用户澄清或保留「⚠️ 待确认 @干系人」占位，"
              "不得臆测填充。")
    red_total = len(rl) + len(ut) + len(tv)
    if red_total:
        print(f"⚠️ **阶段4 发现 {red_total} 处红线/一致性风险**（红线词 {len(rl)} / 待确认悬空 {len(ut)} / 埋点规范 {len(tv)}）："
              "须逐项确认或修正后再定稿。")
    print()


if __name__ == '__main__':
    main()
