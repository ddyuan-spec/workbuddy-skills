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
import glob
import re
import json
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
                   "不开放", "不新增", "不支持",
                   "本期包含", "为范围内", "范围内能力"]
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
def scan_red_line(text, raw_html=""):
    """红线词：用户裁定不纳入的端口/能力，出现须有明确'不涉及'豁免声明。

    豁免方式：单次出现位置 ±30 字内含"不涉及/不在范围/本期不含"等豁免词。
    若某红线词在本需求中属于「范围内」能力（如商家端后台），在首次出现处
    附近写「本期包含XX」或「为范围内」即可命中局部豁免。

    对 HTML 文件，优先用 raw_html 剥标签后的文本扫描（保留文档原始顺序），
    避免 extract_html 先提 heading 导致上下文漂移。
    """
    scan_text = re.sub(r'<[^>]+>', ' ', raw_html) if raw_html else text
    warns = []
    for term in RED_LINE_TERMS:
        matches = list(re.finditer(term, scan_text))
        if not matches:
            continue  # 词未出现在文本中，跳过
        has_exempt = False
        for m in matches:
            ctx = scan_text[max(0, m.start() - 30): m.end() + 30]
            if any(ex in ctx for ex in RED_LINE_EXEMPT):
                has_exempt = True
                break  # 该词任一位置有豁免即可
        if not has_exempt:
            # 找不到任何带豁免的出现 → 告警
            warns.append(
                f"红线词「{term}」出现但全文无豁免声明（不涉及/本期包含/为范围内等）；"
                f"若为范围外请写「本需求不涉及{term}」；"
                f"若为范围内请在任意出现处附近加「本期包含{term}」或「为范围内」")
    return warns


# 冗余声明检测模式（沉淀自评审：PRD 不应出现自证式免责/范围说明块）
REDUNDANT_DECL_PATTERNS = [
    ("红线豁免声明", "红线词显式改判块"),
    ("范围豁免声明", "范围外能力声明块"),
    ("免责声明", "通用免责块"),
    ("本需求仅不涉及.*按用户裁定", "裁定引用式排除声明"),
    ("与「.*」需求相互独立", "跨需求对比声明"),
]


def scan_redundant_declarations(text):
    """扫描 PRD 中的冗余声明/免责/自证式范围说明块。

    原则：PRD 应直接写「做什么、怎么做」，不需要插入一段话解释
    「为什么某个词不是红线 / 为什么包含某端口 / 与其他需求的关系」。
    这类内容属于评审过程产物，不应出现在定稿 PRD 中。

    返回匹配列表 [(模式名, 描述, 摘要片段), ...]。
    """
    hits = []
    for pat_name, desc in REDUNDANT_DECL_PATTERNS:
        for m in re.finditer(pat_name, text):
            snippet = text[max(0, m.start() - 10): m.end() + 60].replace('\n', ' ')
            hits.append((pat_name, desc, snippet))
    return hits


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


# ---------------------------------------------------------------------------
# 阶段4 扩展：业务流程图一致性扫描
# 沉淀自评审踩坑：PRD 内画的流程图与已梳理确认的泳道流程图偏离
# 规则：没有已梳理的业务流程图 → 必须先画出来确认再写 PRD；
#       有已梳理图 → PRD §三 流程图必须与其一致（节点/阶段/泳道不遗漏）
# ---------------------------------------------------------------------------
def scan_flow_diagram_consistency(html_text, plain_text):
    """检测 PRD 业务流程图与已梳理基线流程图的一致性。

    检测项：
      🔴 必须修：
        1) PRD 含「业务流程图」但无「已梳理/基线/横向泳道/全链路」等基线声明
           → 说明 PRD 作者未基于已确认的流程图画图，可能脑补/简化
        2) PRD 无业务流程图但正文有流程相关章节（§三）
           → 缺少流程图，必须补
      🟡 建议查：
        3) 图中提取的关键节点词在正文功能模块列表中覆盖率低

    返回 (warns, info_list)。
    """
    import re
    warns = []
    infos = []

    # 1) 是否有业务流程图（SVG / img + 流程图关键词）
    has_svg = '<svg' in html_text or ('<img' in html_text and '流程图' in html_text)
    flow_section = bool(re.search(r'(业务|数据)?流程[图表]', plain_text))

    if not has_svg and not flow_section:
        return [], []  # 完全无流程图相关内容，不告警（可能本需求不需要）

    # 2) 有流程图章节但无 SVG/img → 缺图
    if flow_section and not has_svg:
        warns.append(
            "PRD 含「流程图」章节标题但未检测到 <svg> 或 <img> 图形内容；"
            "必须补画业务流程图后再定稿")

    # 3) 有图但无基线声明 → 核心告警
    if has_svg:
        baseline_kw = [
            "已梳理", "横向泳道", "泳道图",
            "与.*流程图一致", "依据.*梳理",
            "流程图（横向", "流程图（泳道",
            "本图与", "沿用.*流程图.*一致",
        ]
        # 找到流程图/SVG 在文中的位置，仅在该位置前后 600 字范围内
        # 搜索基线声明（避免全文其他位置的"基线""全链路"等词误命中）
        svg_pos = html_text.find('<svg')
        if svg_pos < 0:
            svg_pos = html_text.find('<img')
        # 也尝试从 plain_text 中找"业务流程图"标题位置
        flow_heading = re.search(r'业务流程[图表]', plain_text)
        heading_pos = flow_heading.start() if flow_heading else -1

        # 取流程图附近的纯文本窗口（取 SVG 位置和标题位置中较前的，往前/后各扩展）
        search_start = max(0, min(
            svg_pos if svg_pos > 0 else len(plain_text),
            heading_pos if heading_pos > 0 else len(plain_text)
        ) - 200)
        search_end = min(len(plain_text), max(
            svg_pos if svg_pos > 0 else 0,
            heading_pos if heading_pos > 0 else 0
        ) + 600)
        nearby_text = plain_text[search_start:search_end]

        has_baseline = any(re.search(kw, nearby_text) for kw in baseline_kw)
        if not has_baseline:
            warns.append(
                "🔴 **业务流程图缺少基线声明**："
                "PRD 中检测到流程图（<svg>），但未找到「已梳理/基线/横向泳道/全链路/"
                "与XX流程图一致」等基线引用说明。"
                "\n   规则：PRD §三 的业务流程图**必须基于已梳理确认的业务流程图绘制**"
                "（如需求梳理阶段产出的横向泳道全链路图），不得自行简化或另画。"
                "\n   修正：① 若已有已梳理的流程图 → 在流程图旁标注"
                "「本图与《XX业务流程图（横向泳道）》一致」并确保节点/阶段/泳道对应；"
                "② 若尚未梳理 → 必须**先停止写 PRD**，先画出业务流程图（推荐横向泳道）"
                "经你确认后，再基于该图画 PRD 流程图。")

        # 4) 提取图中文字节点与正文模块列表做覆盖度检查
        # 从 SVG <text> 标签提取节点文字
        svg_texts = re.findall(r'<text[^>]*>([^<]+)</text>', html_text)
        # 过滤掉太短的和纯数字/符号的
        nodes = [t.strip() for t in svg_texts
                 if len(t.strip()) >= 4 and not re.match(r'^[\d\s·•\-\→↓↑←]+$',
                                                           t.strip())]
        if nodes:
            # 从正文中提取功能模块词（通常在表格 or 列表中）
            module_patterns = r'(优惠券?管理|发券活动|领券活动|券模板|核销|退券|' \
                              r'数据看板|用户券|获券弹窗|发券引擎|配置券|' \
                              r'添加券|编辑券|下架券|支付成功|触发条件|用券|' \
                              r'商品详情|商详)'  # 新增：商品详情/商详
            modules_found = set(re.findall(module_patterns, plain_text))
            # 排除合理不在主流程中的模块（只读查询/辅助功能）
            skip_modules = {'数据看板'}
            modules_relevant = modules_found - skip_modules
            # 节点中能匹配到模块词的数量
            node_plain = ' '.join(nodes)
            matched = sum(1 for m in modules_relevant if m in node_plain)
            coverage = matched / len(modules_relevant) * 100 if modules_relevant else 100
            if coverage < 50:
                infos.append(
                    f"流程图节点对正文功能模块覆盖度偏低（约 {coverage:.0f}%）；"
                    f"建议确认图中是否遗漏关键环节（如制券模板库、发券引擎、"
                    f"核销引擎等后台/服务端环节）")
            else:
                infos.append(f"流程图节点对正文功能模块覆盖度约 {coverage:.0f}% ✅")

        # 5) 🔴 流程图防篡改检测（v1.0.11 沉淀自评审）
        #     规则：PRD 业务流程图必须引用权威来源（coupon-flow.html / 需求梳理图集）
        #     且不得自行简化/重绘。检测：
        #     a) 是否引用了权威来源文件名
        #     b) 是否含多平台泳道关键词（若来源有泳道图但 PRD 无 → 疑似简化）
        #     c) 是否含「禁止自行修改/禁止擅自改动」类约束声明
        auth_sources = ['coupon-flow', '需求梳理图集', '业务流程图（横向',
                         '泳道', '全链路', '时序图']
        has_auth_ref = any(s in nearby_text for s in auth_sources)
        swimlane_kw = ['平台端后台', '商家端后台', '券服务', '火山引擎',
                       '用户端.*三端', '运营.*平台端']
        has_swimlane = any(re.search(kw, html_text) for kw in swimlane_kw)
        anti_tamper_kw = ['禁止.*自行.*修改', '禁止.*擅自.*改动', '禁止.*独立.*重绘',
                          '不得.*自行.*简化', '须先.*修改.*梳理',
                          '报差异.*确认', 'AI.*无权']
        has_anti_tamper = any(re.search(kw, nearby_text) for kw in anti_tamper_kw)

        if has_svg and not has_auth_ref:
            warns.append(
                "🔴 **业务流程图缺少权威来源引用**："
                "检测到 <svg> 流程图，但未引用权威来源文件"
                "（如 `coupon-flow.html` / `需求梳理图集` / 「横向泳道」）。"
                "\n   规则：PRD §三 的业务流程图**必须基于已确认的权威流程图**"
                "（需求梳理阶段产出的泳道图/时序图），不得自行简化或另画。"
                "\n   修正：① 在流程图旁标注「本图引自 XX.html（权威来源）」；"
                "② 若自行画了简化版 → **删除**，改为引用/内嵌权威源完整图。")
        elif has_svg and not has_anti_tamper:
            infos.append(
                "💡 流程图未含「禁止自行修改」约束声明；"
                "建议添加「⚠️ 禁止在 PRD 中自行简化/重绘/修改流程图，"
                "差异须报用户确认」类规则声明，防止后续 AI 自行篡改。")

        if has_svg and not has_swimlane and 'coupon-flow' in plain_text:
            warns.append(
                "🔴 **流程图疑似被简化**：引用了 coupon-flow.html（含多平台泳道+时序图），"
                "但当前 PRD 流程图中未检测到泳道关键词"
                "（平台端后台/商家端后台/券服务/火山引擎/用户端）。"
                "\n   coupon-flow.html 包含：① 整体业务泳道图（6 泳道）+ "
                "② 时序图 A（直播时长发券）+ ③ 时序图 B（商详领券→核销）。"
                "\n   若 PRD 仅展示了简化版（如 6 阶段线性图），**必须回退为完整版**，"
                "不得省略泳道/时序图。")

    return warns, infos


# ---------------------------------------------------------------------------
# 阶段4 扩展：状态机完整性扫描
# 沉淀自评审踩坑：状态机表缺前置条件、原型缺操作按钮、破坏性操作无守卫
# ---------------------------------------------------------------------------
def scan_state_machine(plain_text, html_text):
    """检测 PRD 状态机与状态流转表的完整性。

    检测项：
      🔴 必须修：
        1) 状态转换表中「任意→删除」「任意→下架」等宽泛起始状态
           → 缺少状态守卫（如必须先下架才能删除）
        2) 破坏性操作（删除/作废/回滚）的前置条件为空或仅写
           「确认弹窗」→ 缺业务前置条件（如无已发放券/无关联活动）
        3) 状态转换出现循环或同态转换（如 启用→下架 目标=下架）
        4) 原型中列表操作列缺少状态变更按钮（如只有查看+删除，
           缺下架/启用/编辑）
      🟡 建议修：
        5) 状态枚举未完整列出（仅有转换表，无「完整状态集」定义）
        6) 子实体（发券活动/领券活动/用户券）的状态机仅为文字描述
           无表格

    返回 (warns, info_list)。
    """
    import re
    warns = []
    infos = []

    # 检测是否有状态机相关内容
    has_state = bool(re.search(r'状态[机流转]|状态流[转]|状态机', plain_text))
    if not has_state:
        return [], []

    # ---- 1) 宽泛起始状态检测（任意→破坏性操作）----
    # 优化：限制匹配窗口 ≤80 字符；排除非状态机上下文（如"全部功能模块"/"全部会员"/"全部店铺"）
    loose_start = re.findall(
        r'[^>](任意|所有|全部|无论.*状态)[^<]{0,80}\s*(删除|作废|回滚|下架)',
        plain_text)
    # 排除非状态机上下文的误报
    skip_ctx = ['功能模块', '会员', '店铺', '端口', '字段', '列', '记录',
                '适用', '可选', '涉及', '包含', '覆盖']
    filtered = []
    for start, action in loose_start:
        # 找到原始匹配的完整文本位置
        m = re.search(
            re.escape(start) + r'[^\n]{0,80}' + re.escape(action), plain_text)
        if not m:
            continue
        seg = m.group(0)
        # 如果匹配段内含非状态机上下文关键词 → 跳过
        if any(ctx in seg for ctx in skip_ctx):
            continue
        filtered.append((start, action))
    for start, action in filtered:
        warns.append(
            f"🔴 状态转换表存在宽泛起始状态「{start}→{action}」："
            f"缺少状态守卫。通常「{action}」操作应限制在特定状态下执行"
            f"（如仅「下架」状态可「删除」，或「启用」状态须先「下架」）。"
            f"请补充每个状态的合法转换路径。")

    # ---- 2) 破坏性操作前置条件检测 ----
    destructive_ops = ['删除', '作废', '回滚', '强制结束']
    weak_preconditions = ['确认弹窗', '用户确认', '弹窗确认', '二次确认',
                          '运营操作', '管理员操作', '手动']
    # 找状态转换表中的行模式：触发动作 + 前置条件 + 目标
    for op in destructive_ops:
        # 查找含该操作的行
        rows = re.finditer(
            rf'(?:^|\n)\s*\|[^\|]*{op}[^\|]*\|[^\|]*\|[^\|]*\|',
            plain_text, re.MULTILINE)
        for row in rows:
            cell_text = row.group(0)
            # 检查前置条件列是否过弱
            is_weak = any(wp in cell_text for wp in weak_preconditions)
            # 同时检查是否没有有意义的业务前置
            has_business_guard = any(
                kw in cell_text for kw in [
                    '无已发放', '无关联', '已下架', '未开始',
                    '零发放', '零领取', '无进行中', '先下架',
                    '仅.*可删除', '仅.*可.*'])
            if is_weak and not has_business_guard:
                warns.append(
                    f"🔴 破坏性操作「{op}」的前置条件过弱"
                    f"（当前仅写确认类/运营操作类）："
                    f"需补充**业务前置条件**（如「必须先下架」"
                    f"「无已发放券」「无关联进行中活动」），"
                    f"防止误操作导致数据不一致。")

    # ---- 3) 循环/同态转换检测 ----
    circular = re.findall(
        r'\|(\w+[^\|]*)\|\s*(\w+)\s*\|\s*[^\|]*\s*\|\s*\1\s*\|',
        plain_text)
    if circular:
        for src, action in circular:
            if src != '任意':  # "任意"不算循环
                warns.append(
                    f"🔴 状态转换疑似循环/同态转换：「{src} → {action} → {src}」。"
                    f"若非有意设计（如刷新重试），请检查是否起始/目标状态写反。")

    # ---- 4) 原型操作列按钮检测（对 HTML 原型文件） ----
    if html_text:
        # 提取列表操作列中的按钮文字
        act_buttons = re.findall(
            r'class="(?:btn-link|act-btn)"[^>]*>([^<]+)</a>',
            html_text)
        # 常见状态变更操作关键词
        state_actions = ['下架', '启用', '停用', '编辑', '发布', '撤回', '作废']
        found_state_btns = [b for b in act_buttons if any(s in b for s in state_actions)]
        has_delete = any('删除' in b or 'del' in b.lower() for b in act_buttons)

        # 如果有删除按钮但无下架/启用按钮 → 可能缺失中间状态操作
        if has_delete and not found_state_btns:
            warns.append(
                "🔴 **原型操作列缺状态变更按钮**："
                "检测到列表操作列含「删除」按钮但不含「下架/启用/编辑」等"
                "状态变更按钮。结合状态机规则（如须先下架再删除），"
                "原型可能缺少关键操作入口。请核对原型与状态机是否一一对应。")
        elif not act_buttons:
            infos.append(
                "原型列表未检测到操作列按钮（可能为纯展示页或截图原型）；"
                "请人工确认操作按钮是否完整。")

    # ---- 5) 状态枚举完整性 ----
    has_enum_def = bool(re.search(
        r'(完整状态集|状态枚举|状态定义|所有状态[:：])', plain_text))
    has_table = bool(re.search(r'起始状态.*触发动作.*前置条件.*目标状态', plain_text))
    if has_table and not has_enum_def:
        infos.append(
            "状态转换表存在但未明确定义「完整状态枚举」；"
            "建议在表前列出所有状态值（如：草稿/启用/下架/已删除/已过期），"
            "避免遗漏边界状态。")

    # ---- 6) 子实体状态机格式 ----
    sub_entities = ['发券活动状态', '领券活动状态', '用户券状态', '订单状态']
    for entity in sub_entities:
        m = re.search(rf'{entity}[:：]([^\n]+)', plain_text)
        if m:
            desc = m.group(1).strip()
            # 仅文字描述（含箭头和中文）但无表格
            has_arrows = '→' in desc or '->' in desc
            if has_arrows and len(desc) < 80:
                infos.append(
                    f"「{entity}」仅为简短文字描述（<80字），"
                    f"建议扩展为状态转换表格（起始/触发/前置/目标），"
                    f"与主实体状态机保持一致颗粒度。")

    return warns, infos


# ---------------------------------------------------------------------------
# 阶段4 扩展：功能范围标注扫描（已有 vs 新增/改动）
# 沉淀自优惠券 PRD 评审：平台端已有功能（新增/编辑/下架/删除）被全量展开，
# 用户要求「已有功能不赘述，仅写一句沿用现有功能；只写本期新增/改动」。
# ---------------------------------------------------------------------------
def scan_scope_tagging(plain_text):
    """扫描 §四 功能需求详情下每个功能点（h3/h4 标题）是否标注了范围标签。

    检测项分两级：
      🔴 必须修：功能点标题所在小节附近无任何范围标注关键词
                （已有 / 沿用现有功能 / 本期新增 / 新增 / 改动 / 沿用）
      🟡 建议查：标注「沿用现有功能」却仍展开大段字段表/逻辑（疑似冗余）

    返回 (warns, infos)。
    """
    import re as _re
    # 仅当存在「四、功能需求」章节才激活
    if not _re.search(r'四[、.、]\s*功能需求', plain_text):
        return [], []

    SCOPE_KW = ['已有', '沿用现有功能', '沿用', '本期新增', '本期改动',
                '新增', '改动', '已存在', '存量']

    # 提取 §四 章节正文（从「四、功能需求」到「五、」之前）
    m_start = _re.search(r'四[、.、]\s*功能需求', plain_text)
    m_end = _re.search(r'五[、.、]\s*非功能性|五[、.、]\s*', plain_text)
    sec_start = m_start.start() if m_start else 0
    sec_end = m_end.start() if m_end else len(plain_text)
    section = plain_text[sec_start:sec_end]

    # 切分功能点：以 h3/h4 标题（「N.N」编号）为界
    # 匹配形如 4.1 / 4.1.1 / 4.2 的标题行
    point_pattern = _re.compile(r'\n\s*(\d+\.\d+(?:\.\d+)?)\s*([^\n]+)')
    points = list(point_pattern.finditer(section))

    warns = []
    infos = []

    for i, pm in enumerate(points):
        title = pm.group(2).strip()
        # 当前功能点内容范围：从本标题到下一个标题
        start = pm.end()
        end = points[i + 1].start() if i + 1 < len(points) else sec_end
        block = section[start:end]

        # 跳过纯编号导航（如 "4.1 平台端后台" 这种大节也检查，但允许其下属小节点标注）
        has_scope = any(kw in block[:200] or kw in title for kw in SCOPE_KW)
        if not has_scope:
            warns.append(
                f"🔴 **功能点「{pm.group(1)} {title}」缺少范围标注**："
                f"未标明「已有-沿用 / 本期新增 / 本期改动」。"
                f"请按需求梳理范围补标——已有功能仅写一句「沿用现有功能」，"
                f"本期新增/改动才详写。")
        else:
            # 标注了「沿用」但内容过长（> 400 字且无表格截断）→ 疑似冗余
            if any(kw in block[:200] for kw in ['已有', '沿用现有功能', '沿用', '已存在', '存量']):
                # 粗略判断：沿用块里是否含多行 <tr> 字段表
                tr_count = block.count('<tr')
                if tr_count >= 3:
                    infos.append(
                        f"💡 功能点「{pm.group(1)} {title}」标注为已有/沿用，"
                        f"但仍展开 {tr_count} 行表格，疑似冗余——"
                        f"已有功能建议压缩为一句「沿用现有功能，详见原型」。")

    return warns, infos


# ---------------------------------------------------------------------------
# 阶段4 扩展：待确认项卫生 + 状态机前后矛盾扫描
# 沉淀自优惠券 PRD v1.0.7 评审：
#   - 状态机转换表出现「某状态既声明无编辑/编辑被替换，又保留该状态编辑行」
#     → 前后矛盾（已下架等终态若禁止变相上架，应直接移除编辑行）
#   - 待确认项提出「编辑能否变相上架 / 重新上架 / 重新启用」类提问
#     → 与正文已定的「设计如此」决策冲突，不应作为待确认项
# ---------------------------------------------------------------------------
def scan_pending_hygiene(plain_text, html_text=""):
    """待确认项卫生与状态机前后矛盾扫描。

    检测项：
      🔴 必须修：
        1) 状态机转换表中，某起始状态既存在「编辑」行，又在其它行
           声明「无编辑 / 编辑已替换 / 无…编辑需求」→ 前后矛盾
        2) 同一「起始状态 → 触发动作」映射到不同目标状态 → 重复/写反
        3) 待确认项提出「变相上架 / 重新上架 / 重新启用」类提问，
           与正文已定「设计如此」决策冲突（这类问题不构成待确认项）
      🟡 建议查：
        4) 待确认项提及对已有/沿用功能动作的权限提问（编辑/下架/删除
           + 是否允许/可否），疑似与现有功能冲突，需人工确认归属

    返回 (warns, infos)。
    """
    import re as _re
    warns = []
    infos = []

    def _strip_tags(s):
        return _re.sub(r'<[^>]+>', '', s or '')

    # ---------- A) 状态机转换表前后矛盾 ----------
    if html_text:
        tables = _re.findall(r'<table>.*?</table>', html_text, _re.DOTALL)
        sm_table = None
        for tb in tables:
            if '起始状态' in tb and '触发动作' in tb:
                sm_table = tb
                break
        if sm_table:
            rows = _re.findall(r'<tr>(.*?)</tr>', sm_table, _re.DOTALL)
            parsed = []
            for r in rows:
                cells = _re.findall(r'<td[^>]*>(.*?)</td>', r, _re.DOTALL)
                cells = [_strip_tags(c) for c in cells]
                if len(cells) >= 5:
                    parsed.append({
                        'from': cells[0].strip(),
                        'action': cells[1].strip(),
                        'to': cells[4].strip(),
                        'btn': cells[-1].strip() if len(cells) > 5 else '',
                    })
            state_edit_rows = {}
            state_noedit_claim = {}
            for p in parsed:
                s = p['from']
                if s in ('—', '-', '', '任意'):
                    continue
                if p['action'] == '编辑':
                    state_edit_rows.setdefault(s, p)
                if _re.search(r'无编辑|编辑.*替换|无.*编辑需求|不提供.*编辑|编辑.*已替换',
                              p['btn'] + ' ' + p['to']):
                    state_noedit_claim.setdefault(s, p)
            for s, er in state_edit_rows.items():
                if s in state_noedit_claim:
                    nc = state_noedit_claim[s]
                    warns.append(
                        f"🔴 状态机前后矛盾：状态「{s}」转换表既存在「编辑」行"
                        f"（{er['from']}→{er['action']}→{er['to']}），"
                        f"又在其它行声明「无编辑 / 编辑已替换」"
                        f"（如：「{nc['btn'][:40]}」）。两者冲突——"
                        f"终态若禁止变相上架，应直接移除编辑行，"
                        f"而非同时保留编辑行与「无编辑」声明。")
            # 同 (from, action) 不同 to
            seen = {}
            for p in parsed:
                if p['from'] in ('—', '-', '', '任意') or p['action'] in ('—', '-', ''):
                    continue
                key = (p['from'], p['action'])
                if key in seen and seen[key] != p['to']:
                    warns.append(
                        f"🔴 状态机前后矛盾：同一「{key[0]} → {key[1]}」"
                        f"映射到不同目标状态（{seen[key]} 与 {p['to']}），"
                        f"请核对是否写反或重复。")
                else:
                    seen[key] = p['to']

    # ---------- B) 待确认项卫生 ----------
    # B1) 与「设计如此」决策冲突：提出「变相上架 / 重新上架」类提问。
    #     判定：relist 词附近同时含疑问词（？/是否/可否/能否/允许），
    #           且不在否定语境（设计如此/非待确认/不构成待确认项/已裁定）。
    #     否定说明句（如「结构上杜绝变相上架，故不构成待确认项」）会被排除。
    relist_kw = _re.compile(r'变相上架|重新上架|重新启用|恢复上架')
    interr = _re.compile(r'[？?]|是否|可否|能否|允许')
    neg_ctx = _re.compile(r'不构成待确认项|非待确认|设计如此|已裁定|既定设计|为既定|不是待确认项')
    for m in relist_kw.finditer(plain_text):
        seg = plain_text[max(0, m.start() - 50): m.end() + 50]
        if interr.search(seg) and not neg_ctx.search(seg):
            warns.append(
                f"🔴 待确认项与「设计如此」决策冲突（「…{seg.strip()}…」）："
                f"若正文已裁定无「重新上架/启用」路径（下架即终态），"
                f"则「变相上架/重新上架」类问题不构成待确认项，"
                f"应写为既定设计说明，而非待确认项。")
    # B2) 疑似与现有功能冲突（仅对真正的待确认项标记做宽松提示）
    gen_markers = _re.findall(
        r'⚠️\s*待确认[^<\n]{0,60}|待确认项[:：][^<\n]{0,60}|待确认：[^<\n]{0,60}',
        plain_text)
    conflict_kw = _re.compile(
        r'(编辑|下架|删除|新增|上架|启用|停用).{0,10}(是否|能否|允许|可否|限制|禁止)')
    for seg in gen_markers:
        if conflict_kw.search(seg):
            infos.append(
                f"💡 待确认项疑似与现有功能冲突：「{seg.strip()}…」。"
                f"若所问动作（编辑/下架/删除等）属已标「已有/沿用」功能，"
                f"其是否允许应由既有实现决定；若属本期新增/改动，"
                f"请标注「本期新增」并写清规则，而非含糊待确认。")

    return warns, infos


def scan_resolved_warn_boxes(html_text):
    """扫描冗余 meta 框（v1.0.12→v1.0.13 扩展）。

    覆盖两类：
      A) <div class="warn"> 警告框：内容全为「✅ 已解决/设计如此/已确认」等已闭环项
      B) <div class="note"> 或其他 meta 说明框：含「📎 权威来源/禁止修改/AI无权/
         报差异给用户确认」等面向 AI/评审过程的元说明——PRD 不应出现此类噪声

    返回 (warns, auto_fix_actions)。
    """
    warns = []
    auto_fixes = []

    # ========== 类型 A：已闭环警告框 ==========
    warn_pattern = re.compile(
        r'<div\s+class="warn"[^>]*>(.*?)</div>',
        re.DOTALL | re.IGNORECASE
    )

    for m in warn_pattern.finditer(html_text):
        content = m.group(1)
        plain = re.sub(r'<[^>]+>', '', content).strip()

        resolved_markers = [
            r'✅\s*已解决', r'已解决',
            r'设计如此', r'既定设计',
            r'已确认方案', r'已确认',
            r'非待确认', r'不构成待确认',
        ]
        unresolved_markers = [
            r'待确认', r'待评审', r'TODO', r'待定',
            r'待补充', r'待讨论', r'需确认',
            r'⚠️.*待', r' pending ', r' TBD ',
        ]

        resolved_count = sum(1 for pat in resolved_markers
                            if re.search(pat, plain, re.IGNORECASE))
        unresolved_count = sum(1 for pat in unresolved_markers
                              if re.search(pat, plain, re.IGNORECASE))

        if resolved_count > 0 and unresolved_count == 0:
            title_match = re.search(r'【[^】]+】|（[^）]+）|<b>([^<]+)</b>',
                                    content, re.IGNORECASE)
            title = title_match.group(1) or title_match.group(2) or \
                title_match.group(3) or '无标题'
            title = title.strip()[:60]
            li_count = len(re.findall(r'<li[^>]*>', content))

            warns.append(
                f"🔴 **冗余警告框**：「{title}」包含 {li_count} 条项，"
                f"全部为「✅ 已解决 / 设计如此 / 已确认」等已闭环内容——"
                f"该警告框是冗余噪声，应直接删除。"
                f"\n   触发规则 §4.14-A RESOLVED_WARN_BOX。")
            auto_fixes.append({
                'type': 'delete_warn_div',
                'title': title,
                'match_start': m.start(),
                'match_end': m.end(),
                'reason': f'全部 {li_count} 项均已闭环',
            })

    # ========== 类型 B：面向 AI/评审的 meta 说明框（v1.0.13 扩展） ==========
    # 匹配 <div class="note"> 以及任何含 meta 关键词的说明块
    meta_patterns = [
        (r'<div\s+class="note"[^>]*>(.*?)</div>', 'div.note'),
        (r'<div\s+[^>]*style="[^"]*background:#f0f5ff[^"]*"[^>]*>(.*?)</div>',
         '蓝色背景说明框'),
    ]

    meta_keywords = [
        r'📎\s*权威来源', r'权威来源',
        r'禁止在 PRD 中自行', r'禁止.*重绘', r'禁止.*修改', r'禁止.*改动',
        r'AI\s*无权', r'AI 无权',
        r'报差异给用户确认', r'must报差异',
        r'为需求梳理阶段确认', r'引用自.*梳理',
        r'本图引自', r'本节.*引自',
    ]

    for pat_regex, label in meta_patterns:
        for m in re.finditer(pat_regex, html_text, re.DOTALL | re.IGNORECASE):
            content = m.group(1)
            plain = re.sub(r'<[^>]+>', '', content).strip()

            # 检测是否命中 meta 关键词
            hit_keywords = [kw for kw in meta_keywords
                           if re.search(kw, plain, re.IGNORECASE)]

            if len(hit_keywords) >= 2:  # 至少命中 2 个 meta 关键词才判定（防误报）
                # 取首行作为标识
                first_line = plain.split('\n')[0].strip()[:60] if plain else '无标题'

                warns.append(
                    f"🔴 **冗余 Meta 说明框**（{label}）：「{first_line}…」"
                    f"命中 {len(hit_keywords)} 个面向 AI/评审的 meta 关键词"
                    f"（{', '.join([k.replace(r'\s*', ' ')[:15] for k in hit_keywords[:3]])}…）——"
                    f"PRD 不应包含「来源说明/禁止修改声明/AI操作约束」等元信息。"
                    f"\n   触发规则 §4.14-B META_NOTE：直接删除整个说明框。")
                auto_fixes.append({
                    'type': 'delete_meta_note',
                    'title': first_line,
                    'match_start': m.start(),
                    'match_end': m.end(),
                    'reason': f'meta 关键词命中={len(hit_keywords)}',
                })

    return warns, auto_fixes


def scan_prototype_link_instead_of_image(html_text):
    """扫描「原型示意」是否为链接而非截图（v1.0.14 沉淀自评审）。

    规则：PRD §四 功能需求详情中，每个端/模块的「原型示意」
    必须嵌入 <img> 截图，不得使用 <a href> 文字链接跳转。
    链接形式 = 读者需要额外点击才能看到原型 → 不符合 PRD 自包含原则。

    返回 (warns, ) —— 单元组（与其它 scan 函数签名一致）。
    """
    warns = []

    # 匹配"原型示意"段落：可能格式为：
    #   <p>原型示意：<a href="...">xxx.html</a></p>
    #   <p>原型示意：<a ... target="_blank">xxx</a></p>
    #   原型示意：<a href="...">...</a>
    proto_patterns = [
        # 格式1: <p>原型示意：</p><a href>
        (r'<p>\s*原型示意\s*[:：]\s*</p>\s*<a\s+[^>]*href=',
         '原型示意后紧跟<a>链接'),
        # 格式2: <p>原型示意：<a href="...">
        (r'<p>\s*原型示意\s*[:：]\s*<a\s+[^>]*href=',
         '原型示意内嵌<a>链接'),
        # 格式3: 原型示意.*<a.*href（宽松匹配）
        (r'原型示意[^<]{0,30}<a\s+[^>]*href=',
         '原型示意附近出现<a>链接'),
    ]

    for pat, label in proto_patterns:
        matches = list(re.finditer(pat, html_text, re.IGNORECASE))
        for m in matches:
            # 确认同一上下文中没有 <img> 标签（允许的例外）
            context_start = max(0, m.start() - 50)
            context_end = min(len(html_text), m.end() + 300)
            context = html_text[context_start:context_end]

            has_img = bool(re.search(r'<img\b', context, re.IGNORECASE))

            if not has_img:
                # 提取链接目标作为标识
                href_match = re.search(r'href=["\']([^"\']+)["\']',
                                       html_text[m.start():m.end()+200],
                                       re.IGNORECASE)
                link_target = href_match.group(1) if href_match else '(未知)'
                if len(link_target) > 60:
                    link_target = link_target[:57] + '...'

                warns.append(
                    f"🔴 **原型示意应为截图**（{label}）："
                    f"检测到 `<a href=\"{link_target}\">` 文字链接——"
                    f"PRD 中「原型示意」必须嵌入 <img> 截图图片，"
                    f"不应使用文字链接让读者额外点击跳转。"
                    f"\n   触发规则 §4.15 PROTOTYPE_LINK_NOT_IMAGE："
                    f"将 `<a href>` 替换为 `<img src=\"原型截图/xxx.png\">` "
                    f"(用 Edge headless 或 Playwright 对原型 HTML 截图)。")

    return (warns,)


def scan_prototype_image_valid(html_text, prd_path=None):
    """扫描「原型示意」<img> 截图是否有效可显示（v1.0.16 沉淀自评审）。

    规则 §4.16 PROTOTYPE_IMAGE_INVALID：
    PRD §四 中「原型示意」不仅要是 <img> 标签（§4.15 已覆盖），
    还必须满足以下条件才能通过：
      ① src 引用的图片文件在本地磁盘存在（相对路径基于 PRD 文件所在目录）
      ② <img> 标签含有 style 属性，且至少包含 max-width（响应式）和 border（可见边框）
      ③ 含有 alt 属性（无障碍/语义化）

    参数：
      html_text: PRD HTML 全文
      prd_path: PRD 文件绝对路径（用于解析 img src 相对路径），可为 None

    返回 (warns, ) —— 单元组。
    """
    warns = []

    # 找所有「原型示意」中的 <img>（可能在同一段落或下一段落）
    # 格式1: 原型示意：</p><p><img ...>  （跨段落）
    # 格式2: 原型示意：<img ...>      （同段落）
    proto_sections = re.finditer(
        r'原型示意\s*[:：][^<]{0,200}?(?:</p>\s*<p>)?\s*(<img\s[^>]*>)',
        html_text, re.IGNORECASE
    )

    if not proto_sections:
        # 没有「原型示意」+ img 组合 → 可能是用了链接（由 §4.15 报告）
        return (warns,)

    # 确定基准目录（用于解析 src 相对路径）
    base_dir = ''
    if prd_path:
        base_dir = os.path.dirname(os.path.abspath(prd_path))

    for m in proto_sections:
        img_tag = m.group(1)
        img_start = m.start(1)

        # 提取 src
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
        if not src_match:
            warns.append(
                f"🔴 **原型截图 <img> 缺少 src 属性**："
                f"「原型示意」中的 `<img>` 标签未指定 src 路径。"
                f"\n   触发规则 §4.16 PROTOTYPE_IMAGE_INVALID："
                f"补全 src=\"路径/xxx.png\" 并确保文件存在。")
            continue

        src = src_match.group(1)

        # 检查 ① 文件是否存在
        if base_dir and not src.startswith(('http://', 'https://', 'data:')):
            abs_src = os.path.join(base_dir, src)
            abs_src = os.path.normpath(abs_src)
            if not os.path.isfile(abs_src):
                warns.append(
                    f"🔴 **原型截图文件不存在**（src=\"{src}\"）："
                    f"PRD 引用的图片文件在本地未找到（期望路径：{abs_src}）。"
                    f"线上 GitHub Pages 同样会 404 → 截图显示为破损图标。"
                    f"\n   触发规则 §4.16 PROTOTYPE_IMAGE_INVALID："
                    f"确认截图文件已放入正确目录并已 git push 到仓库。")

        # 检查 ② style 属性（max-width + border）
        style_match = re.search(r'style=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
        if not style_match:
            warns.append(
                f"🟡 **原型截图 <img> 缺少 style 属性**（src=\"{src}\"）："
                f"建议添加 style=\"max-width:100%;border:1px solid #e0e0e0;border-radius:8px;\" "
                f"确保截图响应式展示且有可见边框。"
                f"\n   触发规则 §4.16 PROTOTYPE_IMAGE_INVALID（样式规范）。")
        else:
            style_val = style_match.group(1).lower()
            missing = []
            if 'max-width' not in style_val:
                missing.append('max-width（响应式缩放）')
            if 'max-height' not in style_val:
                missing.append('max-height（高度上限，防超大图撑爆页面）')
            if 'border' not in style_val:
                missing.append('border（可见边框）')
            if missing:
                warns.append(
                    f"🟡 **原型截图 style 不完整**（src=\"{src}\"）："
                    f"缺少 {', '.join(missing)}。"
                    f"\n   当前 style=\"{style_match.group(1)}\""
                    f"\n   建议补全为 style=\"max-width:100%;max-height:800px;border:1px solid #e0e0e0;border-radius:8px;object-fit:contain;\"")

        # 检查 ③ alt 属性
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
        if not alt_match:
            warns.append(
                f"🟡 **原型截图 <img> 缺少 alt 属性**（src=\"{src}\"）："
                f"建议添加 alt=\"xxx端原型\" 以满足无障碍/语义化要求。"
                f"\n   触发规则 §4.16 PROTOTYPE_IMAGE_INVALID（语义规范）。")

    return (warns,)


def _read_png_dimensions(filepath):
    """读取 PNG 文件的像素宽高（从 IHDR chunk 解析）。返回 (w, h) 或 (None, None)。"""
    try:
        with open(filepath, 'rb') as f:
            data = f.read(25)
            if data[:8] != b'\x89PNG\r\n\x1a\n':
                return None, None
            import struct
            w = struct.unpack('>I', data[16:20])[0]
            h = struct.unpack('>I', data[20:24])[0]
            return w, h
    except Exception:
        return None, None


def scan_prototype_image_oversized(html_text, prd_path=None):
    """扫描「原型示意」截图像素尺寸是否过大（v1.0.17 沉淀自评审）。

    规则 §4.17 PROTOTYPE_IMAGE_OVERSIZED：
    原型截图若像素高度 > 1200px（或宽度 > 1920px），在 PRD 页面中渲染后会产生大量空白，
    严重影响阅读体验（读者需要大量滚动才能看到后续内容）。
    典型场景：Edge headless 截图时 --window-size 设得太大（如 1280x3000 整页滚动）。

    阈值：
      - 高度 > 1200px → 🔴 超高（建议 max-height:800px + 重新裁剪/截图）
      - 宽度 > 1920px → 🟡 过宽（通常不影响但浪费空间）

    参数：
      html_text: PRD HTML 全文
      prd_path: PRD 文件绝对路径（用于解析 img src 相对路径）

    返回 (warns, ) —— 单元组。
    """
    warns = []
    MAX_H = 1200   # px，超过此值认为过高
    MAX_W = 1920   # px，超过此值认为过宽

    base_dir = ''
    if prd_path:
        base_dir = os.path.dirname(os.path.abspath(prd_path))

    # 找所有「原型示意」中的 <img>
    for m in re.finditer(
        r'原型示意\s*[:：][^<]{0,200}?(?:</p>\s*<p>)?\s*(<img\s[^>]*>)',
        html_text, re.IGNORECASE
    ):
        img_tag = m.group(1)
        src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
        if not src_match:
            continue
        src = src_match.group(1)

        # 只检查本地文件（跳过 http/data URI）
        if src.startswith(('http://', 'https://', 'data:')):
            continue
        if not base_dir:
            continue

        abs_path = os.path.join(base_dir, src)
        abs_path = os.path.normpath(abs_path)

        if not os.path.isfile(abs_path):
            continue  # 文件不存在由 §4.16 报告

        w, h = _read_png_dimensions(abs_path)
        if w is None or h is None:
            continue  # 非 PNG 文件跳过

        issues = []
        if h > MAX_H:
            issues.append(f'**高度 {h}px**（阈值 {MAX_H}px）→ 渲染后页面产生大量空白')
        if w > MAX_W:
            issues.append(f'宽度 {w}px**（阈值 {MAX_W}px）')

        if issues:
            severity = '🔴' if h > MAX_H else '🟡'
            fix_hint = (
                f"\n   **立即修复**：给 <img> 加 `max-height:800px;object-fit:contain;` 约束渲染高度；"
                f"或用 Edge headless 重新截图时缩小 --window-size 高度参数。"
                f"\n   典型原因：截图时用了整页滚动高度（如 --window-size=1280,3000），"
                f"导致 PNG 包含大量无效空白区域。")
            warns.append(
                f"{severity} **原型截图尺寸过大**（src=\"{src}\"，实际 {w}×{h} px）："
                f"{'; '.join(issues)}"
                f"\n   触发规则 §4.17 PROTOTYPE_IMAGE_OVERSIZED："
                f"{fix_hint}")

    return (warns,)


def scan_reuse_function_verbose(html_text):
    """扫描「已有-沿用」功能点是否写了冗余废话（v1.0.19 沉淀自评审）。

    规则 §4.18 REUSE_FUNCTION_VERBOSE：
    标注为 <span class="tag r">已有-沿用</span> 的功能点，**只允许写一句**
    「沿用现有功能。」，禁止展开按钮列表、原型链接、「本期仅补充」
    等上下文说明——这些不是产品功能描述。

    🔴 判定标准：段落文本去除「沿用现有功能」后仍有 >10 字符的有效内容。
    """
    warns = []

    # 匹配所有「已有-沿用」标签及其后续 <p> 段落
    sections = re.finditer(
        r'(<h[^>]*>[\s\S]*?<span class="tag r">已有-沿用</span></h[^>]*>)'
        r'\s*<div class="sec">\s*<p>([\s\S]*?)</p>',
        html_text, re.IGNORECASE
    )

    for m in sections:
        heading = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        para_text = m.group(2).strip()

        # 去除 HTML 标签和加粗标记
        clean = re.sub(r'<[^>]+>', '', para_text).strip()

        # 标准答案
        standard = '沿用现有功能。'

        if standard in clean:
            # 去掉标准答案后看还有没有废话
            remainder = clean.replace(standard, '').strip()
            # 去掉标点和空白
            remainder = re.sub(r'[，。、：；（）()\s]', '', remainder)
            if len(remainder) > 10:
                warns.append(
                    f"🔴 **「已有-沿用」功能点写了冗余废话**（{heading}）："
                    f"\n   仅允许写一句「{standard}」，当前写了："
                    f"\n   「{clean[:120]}{'...' if len(clean)>120 else ''}」"
                    f"\n   多余内容（{len(remainder)}字符）须删除："
                    f"「{remainder[:80]}{'...' if len(remainder)>80 else ''}」")
        else:
            # 连标准答案都没有
            if clean and len(clean) > 3:
                warns.append(
                    f"🟡 **「已有-沿用」功能点未使用标准文案**（{heading}）："
                    f"\n   当前写的是：「{clean[:100]}{'...' if len(clean)>100 else ''}」"
                    f"\n   应统一为：「{standard}」")

    return (warns,)


def _read_png_dimensions(filepath):
    """读取 PNG 文件的像素宽高（不依赖 PIL）。返回 (w, h) 或 (None, None)。"""
    try:
        with open(filepath, 'rb') as f:
            data = f.read(25)
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return None, None
        w = struct.unpack('>I', data[16:20])[0]
        h = struct.unpack('>I', data[20:24])[0]
        return w, h
    except Exception:
        return None, None


def scan_prototype_screen_ratio(html_text, prd_path=None):
    """扫描原型截图是否使用统一的 PC 端尺寸（v1.0.23 沉淀自评审）。

    规则 §4.19 PROTOTYPE_SCREEN_RATIO（V1.0.23 修订）：
    - **所有原型截图统一使用 PC 端尺寸 1440×900**，不再区分终端类型
    - 非 1440×900 → 🟡 提示（允许偏差，但推荐统一）

    判定依据：读 <img src="..."> 对应 PNG 文件的 IHDR chunk。
    """
    warns = []
    if not prd_path:
        return (warns,)

    prd_dir = os.path.dirname(os.path.abspath(prd_path))

    for m in re.finditer(r'<img\s[^>]*src=["\']([^"\']+\.png)["\']', html_text, re.IGNORECASE):
        src = m.group(1)
        abs_path = os.path.join(prd_dir, src)
        abs_path = os.path.normpath(abs_path)
        w, h = _read_png_dimensions(abs_path)

        if w is None:
            continue

        # 统一标准：1440x900
        if w != 1440 or h != 900:
            warns.append(
                f"🟡 **原型截图尺寸非标准 PC 尺寸**（src=\"{src}\"）："
                f"\n   实际 {w}×{h} px，推荐统一使用 **1440×900**。"
                f"\n   修复命令：msedge --headless --screenshot={src} --window-size=1440,900 原型.html"
                f"\n   触发规则 §4.19 PROTOTYPE_SCREEN_RATIO")

    return (warns,)


def scan_scope_tag_mismatch(html_text, prd_path=None):
    """扫描功能点 tag 标注是否与业务梳理表范围一致（v1.0.21 沉淀自评审）。

    规则 §4.20 SCOPE_TAG_MISMATCH：
    - PRD 中每个功能点的 tag（已有-沿用 / 本期新增 / 本期改动）必须与
      需求梳理阶段确认的范围表（MD/Excel）一致
    - 检测方式：读取 PRD 同目录下的业务梳理 MD 文件，提取「功能×端口」矩阵，
      与 PRD §四 中的 tag 对照
    - 若无业务梳理文件 → 🟡 提示「建议提供业务梳理表供对照」
    - 若 tag 与梳理表矛盾 → 🔴 报告具体差异

    踩坑：优惠券 PRD V1.0.17 把 App 端的商详领券/我的优惠券/下单核销
    错标为「已有-沿用」（套用了小程序/H5 的状态），实际 App 全链路均为
    「暂无，需新增」。V1.0.18 修正。
    """
    warns = []

    # 基于 PRD 路径查找同目录下的业务梳理 MD
    if prd_path:
        prd_dir = os.path.dirname(os.path.abspath(prd_path))
    else:
        prd_dir = os.path.dirname(os.path.abspath(__file__))
    md_files = glob.glob(os.path.join(prd_dir, '*需求梳理*.md'))
    md_files += glob.glob(os.path.join(prd_dir, '*范围*.md'))
    md_files += glob.glob(os.path.join(prd_dir, '*功能生命周期*.md'))

    if not md_files:
        # 尝试更广的搜索
        md_files = glob.glob(os.path.join(prd_dir, '..', '..',
                                           '优惠券新需求', '*.md'))
        md_files = [f for f in md_files if '需求' in f or '范围' in f or '生命周期' in f]

    if not md_files:
        warns.append(
            "🟡 **未找到业务梳理 MD 文件**："
            "无法对照功能点 tag 与需求范围。"
            "\n   建议：在同目录或父目录放置含「功能×端口」范围标注的需求梳理 MD "
            "（如《优惠券需求梳理（线下定稿）.md》或《功能生命周期标注-范围已确认.md》）。")
        return (warns,)

    # 读取业务梳理 MD，提取各端口的功能范围
    scope_map = {}  # {端口: {功能名: '新增'|'已有'|'改动'}}
    for md_path in md_files:
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            # 简单启发式：找表格或列表中的范围标注
            # 匹配类似 "App | 暂无，需新增" 或 "App端 | 新增" 的模式
            for m in re.finditer(
                r'(?:App|APP|app|客户端|C端)[^\n]*?[|:：]\s*(.*?)(?:\n|$)',
                md_content, re.IGNORECASE
            ):
                val = m.group(1).strip()
                if any(k in val for k in ['暂无', '需新增', '新增', 'new']):
                    scope_map.setdefault('App', {})['_default'] = '本期新增'
                elif any(k in val for k in ['已有', '沿用', 'existing']):
                    scope_map.setdefault('App', {})['_default'] = '已有-沿用'
        except Exception:
            pass

    # 检查 PRD 中 App 端功能点的 tag
    app_sections = re.finditer(
        r'<h[34][^>]*>4\.3[.\d]*\s*App[^<]*<span\s+class="tag\s+(\w)"[^>]*>([^<]+)</span>',
        html_text, re.IGNORECASE
    )
    for m in app_sections:
        tag_class = m.group(1)  # y / r / g
        tag_text = m.group(2).strip()
        heading = re.sub(r'<[^>]+>', '', m.group(0)[:80])

        if 'App' in scope_map and '_default' in scope_map['App']:
            expected = scope_map['App']['_default']
            if expected == '本期新增' and tag_text == '已有-沿用':
                warns.append(
                    f"🔴 **App 端功能点 tag 与业务梳理表不一致**（{heading}）："
                    f"\n   PRD 标注：「{tag_text}」"
                    f"\n   业务梳理表标注：应为「{expected}」（App 端全链路新增）"
                    f"\n   ⚠️ 可能原因：错误套用了其他端口（如小程序/H5）的状态标注。")

    if not warns and scope_map:
        pass  # OK, no mismatch found

    return (warns,)


def scan_requirement_md_tag_mismatch(html_text, prd_path=None):
    """扫描 PRD 功能点 tag 与业务梳理 MD 表格的状态是否矛盾（v1.0.24 沉淀自评审）。

    规则 §4.24 REQUIREMENT_MD_TAG_MISMATCH：
    - 业务梳理 MD（线下定稿/范围确认）是功能状态的**唯一权威来源**
    - MD 中标注「暂无/需新增/暂无仅xx有」的功能 → PRD 必须标「本期新增」
    - 若 PRD 标了「已有-沿用」但 MD 说需要新增 → 🔴 矛盾

    数据源：同目录下含「需求梳理」「线下定稿」「范围已确认」关键词的 .md 文件。
    解析其中的 Markdown 表格（列：影响端口 / 影响周期 / 影响功能 / 功能状态）。

    匹配方式：PRD h4 标题关键词与 MD「影响功能」列做模糊匹配（重叠词 ≥2 个即命中）。
    """
    warns = []
    if not prd_path:
        return (warns,)

    prd_dir = os.path.dirname(os.path.abspath(prd_path))

    # 1. 查找业务梳理 MD 文件
    md_files = glob.glob(os.path.join(prd_dir, '*需求梳理*.md'))
    md_files += glob.glob(os.path.join(prd_dir, '*线下定稿*.md'))
    md_files += glob.glob(os.path.join(prd_dir, '*范围*确认*.md'))
    md_files += glob.glob(os.path.join(prd_dir, '*功能生命周期*.md'))

    if not md_files:
        return (warns,)

    # 2. 解析 MD 表格 → 提取 (端口, 功能名, 状态) 三元组
    md_entries = []  # [(port, feature, status), ...]
    for md_path in md_files:
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue

        # 匹配 Markdown 表格行：| 端口 | 周期 | 功能 | 状态 |
        # 跳过表头（|---|---|---|---|）和分隔行
        lines = content.split('\n')
        in_table = False
        header_cols = None
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith('|'):
                in_table = False
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]  # 去掉首尾空元素
            if not cells:
                continue
            # 检测表头或分隔行
            if all(set(c) <= set('-: ') or not c for c in cells):
                continue
            # 首行数据行作为表头
            if not in_table and any('端口' in c or '影响' in c or '功能' in c for c in cells):
                header_cols = cells
                in_table = True
                continue
            if in_table and len(cells) >= 4:
                # 尝试定位端口/功能/状态列
                port_idx = None
                feat_idx = None
                status_idx = None
                for i, col in enumerate(header_cols or []):
                    cl = col.lower()
                    if '端口' in cl or '端' == cl:
                        port_idx = i
                    elif '功能' in cl:
                        feat_idx = i
                    elif '状态' in cl:
                        status_idx = i
                # fallback：按常见顺序 [端口, 周期, 功能, 状态]
                if port_idx is None and len(cells) >= 1:
                    port_idx = 0
                if feat_idx is None and len(cells) >= 3:
                    feat_idx = 2
                if status_idx is None and len(cells) >= 4:
                    status_idx = 3
                if port_idx is not None and feat_idx is not None and status_idx is not None:
                    port = cells[port_idx]
                    feature = cells[feat_idx]
                    status = cells[status_idx]
                    if port and feature and status:
                        md_entries.append((port, feature, status))

    if not md_entries:
        return (warns,)

    # 3. 判定哪些 MD 条目表示"应为新增"
    def is_status_new(s):
        sl = s.lower().replace('，', ',').replace('。', '').replace(' ', '')
        new_keywords = ['暂无', '需新增', '需新', '本期不做' not in s and ('新增' in sl or 'new')]
        no_only_keywords = ['仅商家端有', '仅有', '仅xx有']
        return any(kw in s for kw in new_keywords) or any(kw in s for kw in no_only_keywords)

    # 4. 提取 PRD §四 h4 功能点及其 tag
    prd_sections = []
    for m in re.finditer(
        r'<h[34][^>]*>(\d+\.\d+[\.\d]*)\s*(.*?)\s*<span\s+class="tag\s+(\w)"[^>]*>([^<]+)</span>',
        html_text, re.IGNORECASE
    ):
        section_id = m.group(1)
        title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        tag_class = m.group(3)  # y=新增, r=沿用, g=改动
        tag_text = m.group(4).strip()
        prd_sections.append((section_id, title, tag_class, tag_text))

    # 5. 交叉比对
    for p_section_id, p_title, p_tag_class, p_tag_text in prd_sections:
        # 只检查标为"已有-沿用"的（这些可能是错的）
        if p_tag_text != '已有-沿用':
            continue

        # 提取标题中的关键词（去掉编号、括号内容）
        p_keywords = set(re.sub(r'[()\[\]{}0-9./\s]', '', p_title))

        for md_port, md_feature, md_status in md_entries:
            # 先匹配端口：PRD 标题或上下文中是否包含该端口
            # （简化处理：如果 MD 的端口出现在附近文本中则认为匹配）
            md_feat_keywords = set(re.sub(r'[()\[\]{}，。、/\s]', '', md_feature))

            # 关键词重叠度
            overlap = p_keywords & md_feat_keywords
            if len(overlap) >= 2:  # 至少 2 个关键词匹配
                if is_status_new(md_status):
                    warns.append(
                        f"🔴 **PRD 功能点 tag 与业务梳理 MD 矛盾**（{p_section_id} {p_title}）："
                        f"\n   PRD 标注：「{p_tag_text}」（{p_tag_class}）"
                        f"\n   业务梳理 MD（{md_port}）：「{md_feature}」→ 状态：「{md_status}」"
                        f"\n   判定：MD 明确表示此功能**不存在/需新增**，PRD 不应标为「已有-沿用」。"
                        f"\n   处理方式：改为 <span class=\"tag y\">本期新增</span> 并补充详细 FR。"
                        f"\n   触发规则 §4.24 REQUIREMENT_MD_TAG_MISMATCH")
                    break  # 每个 PRD section 只报一次

    return (warns,)


def scan_missing_prototype_for_new_features(html_text):
    """扫描「本期新增/本期改动」功能点是否缺少原型截图（v1.0.25 沉淀自评审，v1.0.28 增强优先级区分）。

    规则 §4.25 MISSING_PROTOTYPE_FOR_NEW_FEATURE（增强版）：
    - 遍历 §四 中所有 h4 功能点小节
    - 若 h4 的 tag 为「本期新增」或「本期改动」（class 包含 tag y）
    - 检查该 h4 到下一个同级标题之间是否存在 <img> 标签
    - 无 <img> → 进一步判定严重等级：

    **🚨 阻断级（BLOCKER）** — 必须补独立截图才能定版：
      a) 标题含独立页面关键词：详情 / 新建 / 编辑 / 列表 / 看板 / 数据看板 / 查询 / 管理
      b) 后台端（平台端/商家端）的功能点 —— 后台页面无"父级总览图"可引用
      c) h4 内有「表单字段」「字段表」等表单类内容但无截图

    **🟡 提醒级（REMINDER）** — 建议补独立截图，但不阻断：
      a) 客户端（App/H5/小程序）子功能点
      b) 该 h4 所在的 h3 章节顶部已有原型总览图（<img> 距 h3 < 500 字符）
      c) 文字描述中已写明「示意图见 XXX 原型」

    豁免：h4 标题含「差异」「状态机」「流程」「说明」「附录」等非页面类关键词。

    规则 §4.28 TAG_UPGRADE_IMAGE_SYNC（v1.0.28 新增）：
      当功能点 tag 从「已有-沿用」升级为「本期新增/本期改动」时，
      除 FR 文字外必须同步补 <img> 截图。
      本规则与 §4.25 共享检测逻辑，通过 blocker/warn 分级体现：
      - 后台独立页面缺图 → 🚨 阻断（tag 升级后资源未同步）
      - 客户端子功能缺图 → 🟡 提醒（可接受引用父级图）
    """
    blockers = []
    warns = []

    # 匹配 h4 及其 tag
    h4_pattern = re.compile(
        r'<h4[^>]*>(.+?)<span\s+class="tag[^"]*y[^"]*">(.+?)</span></h4>',
        re.DOTALL
    )
    # 找所有 h4 位置，用于判定"到下一个 h4 之间的内容"
    h4_positions = []
    for m in re.finditer(r'<h4', html_text):
        h4_positions.append(m.start())

    # 找所有 h3 位置及其后的首个 img 位置（用于判断"父级总览图覆盖"）
    h3_img_map = {}  # h3_start_pos -> bool (h3 后是否有 img)
    for hm in re.finditer(r'<h3[^>]*>', html_text):
        h3_start = hm.start()
        # 查找 h3 之后 500 字符内是否有 img
        h3_tail = html_text[h3_start:h3_start + 500]
        h3_img_map[h3_start] = bool(re.search(r'<img\s', h3_tail))

    # 豁免关键词（非独立页面的功能点描述）
    skip_keywords = ['差异说明', '状态机', '流程', '说明', '附录']

    # 阻断级关键词：这些类型的页面必须有独立截图
    blocker_keywords = ['详情', '新建', '编辑', '列表', '看板', '数据看板', '查询', '管理']
    # 提醒级关键词：客户端子功能
    reminder_indicators = ['获券弹窗', '我的优惠券', '商品详情领券', '确认订单', '首页']

    for m in h4_pattern.finditer(html_text):
        tag_text = m.group(2).strip()
        title_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 只检查「本期新增」和「本期改动」
        if '本期新增' not in tag_text and '本期改动' not in tag_text:
            continue

        # 豁免非页面类标题
        if any(kw in title_text for kw in skip_keywords):
            continue

        # 确定本节范围：当前 h4 位置 → 下一个 h4 位置（或文件尾）
        start_pos = m.end()
        h4_idx = next((i for i, p in enumerate(h4_positions) if p == m.start()), -1)
        end_pos = html_text.find('<h4', start_pos) if h4_idx >= 0 and h4_idx + 1 < len(h4_positions) else len(html_text)
        section_html = html_text[start_pos:end_pos]

        # 检查是否有 img
        has_img = bool(re.search(r'<img\s', section_html))

        if has_img:
            continue  # 有图，跳过

        # ===== 无图 → 判定严重等级 =====

        # 判断所属 h3 是否有父级总览图
        parent_h3_pos = None
        for h3_pos in sorted(h3_img_map.keys()):
            if h3_pos < m.start():
                parent_h3_pos = h3_pos
            else:
                break
        has_parent_img = h3_img_map.get(parent_h3_pos, False) if parent_h3_pos else False

        # 判断是否有文字引用说明（如"示意图见..."）
        has_ref_text = bool(re.search(r'示意图见|详见.*原型|原型见|参考.*原型', section_html))

        # 判断是否为后台端功能点：查找当前 h4 之前最近的 h3 标题内容
        # 用 h3_positions 已有的数据
        prev_h3_pos = None
        for h3_pos in sorted(h3_img_map.keys()):
            if h3_pos < m.start():
                prev_h3_pos = h3_pos
            else:
                break
        # 取 h3 标签的完整文本（到 </h3> 为止）
        is_backend = False
        if prev_h3_pos is not None:
            h3_end = html_text.find('</h3>', prev_h3_pos)
            if h3_end > prev_h3_pos:
                h3_text = html_text[prev_h3_pos:h3_end]
                is_backend = bool(re.search(r'平台端后台|商家端后台', h3_text))

        # 判断是否为阻断级
        # 关键规则：后台端功能点始终为阻断级（父级总览图通常只展示默认视图如 P1 列表，
        # 不能覆盖 D1 详情/D2 新建/P3 列表/P4 看板等独立页面）
        is_blocker = (
            is_backend  # 后台端功能点 → 始终阻断（不论是否有父级总览图）
            or (any(kw in title_text for kw in blocker_keywords) and not has_parent_img)  # 非后台但有独立页面关键词且无父级图
        )

        # 客户端子功能且有父级图或引用文字 → 降级为提醒
        is_reminder = (
            any(ind in title_text for ind in reminder_indicators)
            or (has_parent_img and not is_backend)
            or has_ref_text
        ) and not is_blocker

        msg_title = f"「{title_text}」"
        msg_tag = f"tag=「{tag_text}」"
        msg_action = "从对应端口原型文件截取 1440×900 后插入该 h4 小节内。"

        if is_blocker:
            blockers.append(
                f"🚨 **{msg_title} 缺少原型截图 [阻断级]**："
                f"\n   {msg_tag}，h4 小节内未找到 <img> 原型截图标签。"
                f"\n   该功能点为{'后台独立页面' if is_backend else '独立页面'}，"
                f"无法引用父级总览图，**必须补独立截图**。"
                f"\n   {msg_action}"
                f"\n   ⛔ 触发规则 §4.25+§4.28：tag 升级后截图资源未同步（阻断级，不补图不可定版）"
            )
        elif is_reminder:
            warns.append(
                f"🟡 **{msg_title} 无独立原型截图 [提醒级]**："
                f"\n   {msg_tag}，h4 小节内无独立 <img>，"
                f"但{'所在 h3 顶部有父级总览图可覆盖' if has_parent_img else '文中已引用原型'}。"
                f"\n   建议补独立截图以提升可读性；如确由父级图覆盖可忽略本提醒。"
                f"\n   触发规则 §4.25 MISSING_PROTOTYPE_FOR_NEW_FEATURE（提醒级）"
            )
        else:
            # 默认按阻断处理
            blockers.append(
                f"🚨 **{msg_title} 缺少原型截图 [阻断级]**："
                f"\n   {msg_tag}，h4 小节内未找到 <img> 原型截图标签。"
                f"\n   {msg_action}"
                f"\n   ⛔ 触发规则 §4.25+§4.28：tag 升级后截图资源未同步（阻断级）"
            )

    return (blockers, warns)


def scan_modal_popup_missing_screenshot(html_text):
    """扫描「弹窗/弹框/Modal」类功能点是否缺少独立弹窗截图（v1.0.29 沉淀自评审）。

    规则 §4.29 MODAL_POPUP_MISSING_SCREENSHOT：
    - 遍历 §四 中所有 h4 功能点小节
    - 若 h4 标题含「弹窗」「弹框」「Modal」「Popup」「对话框」「抽屉」等弹窗关键词
    - 检查该 h4 到下一个 h4 之间是否存在 <img> 标签
    - 无 <img> → 🔴 报缺失：弹窗类功能点应有独立弹窗截图（非引用父级页面图）

    核心逻辑：弹窗是独立 UI 组件，与页面级原型截图不同。仅引用父级页面总览图
    无法展示弹窗的内部布局（标题/券列表/按钮/关闭交互），必须单独截取。
    """
    warns = []
    h4_pattern = re.compile(
        r'<h4[^>]*>(.+?)</h4>',
        re.DOTALL
    )
    h4_positions = []
    for m in re.finditer(r'<h4', html_text):
        h4_positions.append(m.start())

    # 弹窗关键词
    modal_keywords = ['弹窗', '弹框', 'Modal', 'Popup', '对话框', '抽屉', 'overlay', 'dialog']
    # 排除关键词：标题含这些词时，即使带"弹窗"也是「引用/差异/入口」而非独立弹窗组件，
    # 不应要求独立截图（避免 4.3.1 首页·获券弹窗入口、4.4.1 外壳差异 等误报）。
    modal_exclude = ['差异', '对比', '规范', '外壳', 'diff', '入口', '示意', '总览', '引用', '说明']

    for m in h4_pattern.finditer(html_text):
        title_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 只检查含弹窗关键词的功能点
        if not any(kw in title_text for kw in modal_keywords):
            continue
        # 排除「引用/差异/入口」类标题（非独立弹窗组件）
        if any(ex in title_text for ex in modal_exclude):
            continue

        start_pos = m.end()
        h4_idx = next((i for i, p in enumerate(h4_positions) if p == m.start()), -1)
        end_pos = html_text.find('<h4', start_pos) if h4_idx >= 0 and h4_idx + 1 < len(h4_positions) else len(html_text)
        section_html = html_text[start_pos:end_pos]

        has_img = bool(re.search(r'<img\s', section_html))

        if not has_img:
            warns.append(
                f"🔴 **「{title_text}」缺少独立弹窗截图**："
                f"\n   该功能点为弹窗/弹框类组件（标题含弹窗关键词），但 h4 小节内未找到 <img> 独立截图标签。"
                f"\n   弹窗是独立 UI 组件，与页面级原型不同——父级页面总览图无法展示弹窗内部布局。"
                f"\n   应从对应端口原型中触发弹窗状态后截取独立截图（1440×900），"
                f"\n   展示弹窗完整内容：标题区 / 内容列表 / 操作按钮 / 关闭方式。"
                f"\n   触发规则 §4.29 MODAL_POPUP_MISSING_SCREENSHOT"
            )

    return (warns,)


def scan_screenshot_duplicates(html_text, base_dir=None):
    """扫描 PRD 引用的本地截图是否存在「内容完全相同」的情况（v1.0.30 沉淀自评审）。

    规则 §4.30 SCREENSHOT_DUPLICATE_DETECTION：
    - 多张截图字节（md5）完全一致时，导入 Word/钉钉等容器会被去重为 1 张，
      导致其余视图「看起来有图、实际缺失」，常规存在性检测发现不了。
    - 常见于：截原型时视图未正确切换（如仍停在首页默认视图）、弹窗未触发即截图。
    - 检测：提取所有 <img src> 对应的本地 PNG，按 md5 分组，组内 >1 张 → 🔴 报重复。

    依赖：base_dir 为 PRD 文件所在目录（用于解析相对 src）。
    """
    import hashlib
    from collections import defaultdict
    warns = []
    if not base_dir or not os.path.isdir(base_dir):
        return warns
    imgs = re.findall(r'<img[^>]*src="([^"]+)"', html_text)
    groups = defaultdict(list)
    for src in imgs:
        p = os.path.join(base_dir, src)
        if os.path.exists(p):
            try:
                h = hashlib.md5(open(p, 'rb').read()).hexdigest()
                groups[h].append(os.path.basename(p))
            except Exception:
                pass
    for h, members in groups.items():
        if len(members) > 1:
            warns.append(
                f"🔴 **检测到 {len(members)} 张截图内容完全相同（疑似截取失败）**："
                f"\n   {', '.join(members)}"
                f"\n   这些 PNG 字节（md5）完全一致，导入 Word/钉钉时会被去重为 1 张，"
                f"导致其余视图缺图（存在性检测发现不了）。"
                f"\n   请重新从原型截取对应视图：确认页面已正确切换 / 弹窗已触发后再截图，"
                f"保证每张图内容独立、md5 不同。"
                f"\n   触发规则 §4.30 SCREENSHOT_DUPLICATE_DETECTION")
    return warns


    """扫描非功能性需求章节中的冗余说明框/废话段落（v1.0.21 沉淀自评审）。

    规则 §4.21 VERBOSE_NFR_WARNING：
    - §五（非功能性需求）/ §七（边界条件）/ §八（文档维护）等非核心功能章节中，
      不应出现大段「⚠️ 注意」「处理要求」「一码一状态」等操作指引型文字
    - 这些内容属于开发/测试执行规范，不是产品需求文档的内容
    - 检测 <div class="warn"> / <div class="note"> 在 §五~§九 中的出现
    - 若内容超过 40 字且包含「注意/处理要求/确保/须按/禁止凭空」等关键词 → 🔴 冗余

    踩坑：优惠券 PRD V1.0.20 的 §5.1 埋点需求中有 ~120 字的 warn 框
    （"需对齐埋点表 v2.3...禁止凭空定版...本期已移除的埋点..."），
    属于操作指引而非需求说明，V1.0.21 删除。
    """
    warns = []

    # 找到 §五~§九 范围内的 warn/note 框
    section_match = re.search(
        r'五、非功能性需求[\s\S]*?(?=十、|$)', html_text)
    if not section_match:
        return (warns,)

    section_text = section_match.group(0)

    for box_type in ['warn', 'note']:
        pattern = rf'<div class="{box_type}">(.*?)</div>'
        for m in re.finditer(pattern, section_text, re.DOTALL):
            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            # 去掉空白字符后检查长度
            clean_len = len(re.sub(r'\s', '', content))
            verbose_keywords = ['注意', '处理要求', '确保', '须按', '禁止凭空',
                                '引用参数一律', '本期已移除', '一码', '事件树']
            has_verbose = any(kw in content for kw in verbose_keywords)

            if clean_len > 40 and has_verbose:
                short = content[:80] + ('...' if len(content) > 80 else '')
                warns.append(
                    f"🔴 **非功能性需求章节存在冗余说明框**（<{box_type}>）："
                    f"\n   内容：「{short}」"
                    f"\n   字数：{clean_len}字（>{40}字阈值）"
                    f"\n   含冗余关键词：{[kw for kw in verbose_keywords if kw in content]}"
                    f"\n   👉 此类操作指引不属于 PRD 需求说明，应删除。")

    return (warns,)


def scan_scope_leak_feature(html_text, scope_keywords=None):
    """扫描 PRD 中出现了不在本期功能范围内的功能/概念（v1.0.21 沉淀自评审）。

    规则 §4.22 SCOPE_LEAK_FEATURE：
    - PRD 正文中不应出现未纳入本期范围的功能名称、业务概念或约束规则
    - 典型表现：底价保护、SaaS 配置、火山引擎 XX 能力等未在本期交付的功能
      却出现在功能说明/状态转换表/API 清单/验收标准/边界清单中
    - 检测方式：维护一个「已知范围外概念」列表 + 启发式模式匹配
    - 若 PRD 中出现范围外概念 → 🔴 报告位置并建议删除

    注意：此规则需要人工维护 scope_keywords 列表（每期需求不同），
    默认检测常见泄漏模式。完全准确需要对照需求范围表逐项核对。

    踩坑：优惠券 PRD V1.0.20 在 9 处出现「底价保护」（一背景/二状态转换表/
    三API清单/4.3.5详细逻辑/note框/AC验收/§七边界），但底价保护并未纳入
    本期功能范围。V1.0.21 全部清除。
    """
    warns = []
    if scope_keywords is None:
        # 默认常见范围外概念（可按项目配置）
        scope_keywords = ['底价保护', '最低零售价.*击穿', 'min_retail_price']

    for keyword in scope_keywords:
        matches = list(re.finditer(keyword, html_text, re.IGNORECASE))
        if matches:
            locations = []
            for mm in matches[:8]:  # 最多报 8 处
                pos = mm.start()
                # 取前后各 30 字符定位上下文
                start = max(0, pos - 30)
                end = min(len(html_text), pos + len(mm.group()) + 30)
                ctx = html_text[start:end]
                ctx = re.sub(r'<[^>]+>', '', ctx).replace('\n', ' ').strip()
                locations.append(f'  ...{ctx}...')

            warns.append(
                "🔴 **PRD 出现本期范围外的功能/概念**「{}」："
                "\n   共出现 {} 处：{}".format(
                    keyword, len(matches), '\n'.join(locations))
                + "\n   👉 该功能/概念未纳入本期需求范围，应从 PRD 中全部删除。"
                + "\n   💡 如确实要做，请先更新需求范围表（§三/§一）再加入功能说明。")

    return (warns,)


def scan_mixed_view_screenshot(html_text):
    """扫描原型截图是否将多个视图（列表/新建/编辑/详情/弹窗）混在一张图里（v1.0.26 沉淀自评审）。

    规则 §4.26 MIXED_VIEW_SCREENSHOT：
    - 一个功能点小节（h4）如果包含多个视图类型（如「P2 列表 + D3 新建」、
      「列表 + 详情页」、「列表 + 弹窗」），每个视图必须分别有独立的 <img>
    - 检测方式：
      a) h4 标题含「+」或「、」等分隔符，暗示多页面 → 该节内 <img> 数量应 ≥ 2
      b) h4 节内有多个 <p><b>视图名</b> 子标题 → 每个 <p><b> 后应有独立 <img>
    - 若多视图只配了 1 张截图 → 🔴 报「多视图混在一张截图，需拆分」

    典型反面案例：优惠券 PRD V1.0.25 的 4.1.4 「P2 发券活动管理列表 + D3 发券活动」
    只放了 1 张 coupon-d3-send-edit.png，同时包含上半部分 P2 列表和下半部分 D3 表单。
    V1.0.26 拆为 coupon-p2-send-list.png + coupon-d3-send-edit.png 两张独立截图。
    """
    warns = []

    # 排除：差异/规范/外壳/范围/对比类说明章节（非原型视图），以及流程图/时序图/泳道图（属图示非原型截图）
    section_exclude = ['差异', '规范', '外壳', '范围', '对比', '说明', '示意', '总览',
                       '引用', '流程图', '时序图', '泳道', '图 1', '图 2', '图 3', '图 4', '图 5']

    # 匹配 h4 功能点小节
    h4_pattern = re.compile(
        r'<h4[^>]*>(.+?)<span\s+class="tag[^"]*"[^>]*>(.+?)</span></h4>',
        re.DOTALL)
    img_pattern = re.compile(r'<img\s[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)
    # 匹配 <p><b>视图名</b> 形式的子视图标题
    subview_pattern = re.compile(r'<p><b>([^<]+)</b></p>\s*<p><img', re.DOTALL)

    for m in h4_pattern.finditer(html_text):
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        tag = re.sub(r'<[^>]+>', '', m.group(2)).strip()

        # 只检查本期新增/改动的功能点
        if '新增' not in tag and '改动' not in tag:
            continue
        # 排除差异/规范/流程图等非原型视图章节
        if any(ex in title for ex in section_exclude):
            continue

        # 获取该 h4 到下一个 h4/h3/h2 之间的内容
        start = m.end()
        next_heading = re.search(r'<h[234][\s>]', html_text[start:])
        if not next_heading:
            continue
        section_html = html_text[start:start + next_heading.start()]

        # 统计该节内的 <img> 数量
        imgs = img_pattern.findall(section_html)
        img_count = len(imgs)

        # 检测方式：标题含多视图分隔符，且标题中明确命名了 ≥2 个独立页面标识（P\d / D\d）
        # 视图数量估计：以标题中的页面标识（P2/D3 等）为准；无页面标识时退化为视图类型词计数。
        multi_indicators = ['+', '／', '/', '、', '＋', '＆', '&']
        is_multi_title = any(ind in title for ind in multi_indicators)
        page_ids = re.findall(r'\b[PD]\d+\b', title)
        view_words = [w for w in ['列表', '详情', '新建', '编辑', '弹窗', '页面'] if w in title]
        # 「新建/编辑」是同一表单（创建即编辑），不算多视图
        if set(view_words) == {'新建', '编辑'}:
            view_words = []
        if page_ids:
            distinct_view_count = len(set(page_ids))
        else:
            distinct_view_count = len(view_words)

        # 判定：标题明确多视图（≥2 个独立页面）但截图数量不足 → 🔴
        if is_multi_title and distinct_view_count >= 2 and img_count < distinct_view_count:
            warns.append(
                f"🔴 **多视图混在一张截图**（h4: 「{title}」）："
                f"\n   标题明确包含 {distinct_view_count} 个独立页面/视图（如 P2+D3、列表+详情），"
                f"但该节仅有 {img_count} 张 <img>。"
                f"\n   要求：每个视图（列表/新建/编辑/详情/弹窗）必须分别截取独立截图。"
                f"\n   当前图片：{', '.join(imgs) if imgs else '无'}"
                f"\n   触发规则 §4.26 MIXED_VIEW_SCREENSHOT")

    return (warns,)


def scan_verbose_table_annotations(html_text):
    """扫描表格/状态流转表中的冗余验证备注（v1.0.27 沉淀自评审）。

    规则 §4.27 VERBOSE_TABLE_ANNOTATIONS：
    - PRD 表格（尤其是状态流转表）中不应出现开发/设计阶段的调试备注
    - 典型冗余模式（绿色小字 ✅ 备注）：
      a) `✅ 原型已有（截图验证：xxx）` — 截图验证备注
      b) `✅ 方案确认：xxx` — 方案确认备注
      c) `✅ 原型已验证（截图确认：xxx）` — 验证备注
      d) `✅ 同上` — 懒惰引用
    - 这些是写 PRD 时的自我验证笔记，不是给读者看的正式内容
    - HTML 特征：`<span style="color:#2ba245;font-size:11px">✅ ...</span>`

    典型反面案例：优惠券 PRD V1.0.26 的「优惠券配置状态转换表」原型按钮位置列，
    5 行均带绿色 ✅ 冗余备注（如「截图验证：进行中行显示红色'下架'」）。
    V1.0.27 全部清除。
    """
    warns = []

    # 匹配绿色小字 ✅ 备注模式
    pattern = re.compile(
        r'<span\s+style="color:#2ba245;font-size:11px">\s*✅\s*([^<]+)</span>',
        re.IGNORECASE)

    for m in pattern.finditer(html_text):
        annotation = m.group(1).strip()
        # 获取所在行上下文（前后 80 字符）
        start = max(0, m.start() - 80)
        end = min(len(html_text), m.end() + 40)
        context = html_text[start:end].replace('\n', ' ').strip()

        warns.append(
            f"🔴 **表格中存在冗余验证备注**："
            f"\n   内容：「{annotation}」"
            f"\n   上下文：...{context}..."
            f"\n   这是开发/设计阶段的调试笔记，不属于 PRD 正式内容，应直接删除。"
            f"\n   触发规则 §4.27 VERBOSE_TABLE_ANNOTATIONS")

    # 也检测其他常见冗余模式（不限于绿色 span）
    # 如表格单元格内的「（复数验证：...）」「（方案确认：...）」等括号备注
    verbose_patterns = [
        (r'（复数验证[^）]*）', '「复数验证」备注'),
        (r'（截图验证[^）]*）', '「截图验证」备注'),
        (r'（方案确认[^）]*）', '「方案确认」备注'),
        (r'（已验证[^）]*）', '「已验证」备注'),
        (r'\(复数验证[^)]*\)', '「复数验证」备注(半角)'),
        (r'\(截图验证[^)]*\)', '「截图验证」备注(半角)'),
    ]

    for pat, label in verbose_patterns:
        for m in re.finditer(pat, html_text):
            # 排除已在上面绿色 span 中报告的
            ann_text = m.group(0)
            # 检查是否在 <td> 或 <th> 内（表格中）
            pos = m.start()
            preceding = html_text[max(0, pos - 200):pos]
            if '<td' not in preceding and '<th' not in preceding:
                continue  # 不在表格内，跳过

            warns.append(
                f"🟡 **表格中可能存在冗余备注**（{label}）："
                f"\n   内容：{ann_text}"
                f"\n   如确认为开发调试笔记应删除；如为业务规则说明可保留但建议改写为正式表述。"
                f"\n   触发规则 §4.27 VERBOSE_TABLE_ANNOTATIONS")

    return (warns,)


def scan_lazy_function_detail(html_text):
    """扫描 §四 功能需求详情中「本期新增 / 本期改动」功能点是否偷懒（未按模板逐页面逐功能点拆解）。

    规则 §4.23 LAZY_FUNCTION_DETAIL（沉淀自 2026-07-28 优惠券 PRD 评审）：
    - 团队《PRD 输出规范》与 prd-detail-template.md 要求：每个功能点必须拆为
      「列表字段表（字段名称/需求说明/备注）+ 排序/分页/合计/唯一性」
      「功能按钮总表（功能名称/功能说明/备注）」
      「每个按钮独立小节（功能说明/显示位置/权限/前置条件/功能实现=逐步+异常+校验文案）」
      「查询条件表」「字段级数据来源」「状态流转」。
    - 偷懒特征：功能点仅用一张「要素/说明」「项目/说明」「描述/说明」等汇总式扁平表
      充当全部内容，缺少上述结构化子节。
    - 已有-沿用（tag r）功能点不检查（按 §4.18 只需一句话）。
    - 后端契约类（明确声明不涉前端）按模板「范围声明」豁免。

    严重度：
    - 🔴 无任何 <table>，或仅有一张 catch-all 汇总表而无任何结构化子节 → 偷懒，必须重写
    - 🟡 缺字段级数据来源 / 缺前置条件·权限 → 需补充
    """
    import re as _re

    warns = []

    # 1. 截取 §四 区段
    m4 = _re.search(r'<h2>\s*四[、.].*?</h2>(.*?)(?=<h2>\s*五[、.])', html_text, _re.S)
    if not m4:
        return (warns,)
    sec4 = m4.group(1)

    # 2. 切分功能点：仅 h4 作为功能点（h3 是端口大节，跳过不查）
    parts = _re.split(r'(<h[34][^>]*>.*?</h[34]>)', sec4, maxsplit=0)
    blocks = []  # (heading_text, body_html)
    cur_h4 = None
    cur_body = []
    for chunk in parts:
        if not chunk.strip():
            continue
        hm = _re.match(r'<h([34])[^>]*>(.*?)</h[34]>', chunk, _re.S)
        if hm:
            level = hm.group(1)
            text = _re.sub(r'<[^>]+>', '', hm.group(2)).strip()
            if level == '4':
                if cur_h4 is not None:
                    blocks.append((cur_h4, ''.join(cur_body)))
                cur_h4 = text
                cur_body = []
            else:
                # h3 端口大节：结束当前 h4 块，h3 自身不计入功能点
                if cur_h4 is not None:
                    blocks.append((cur_h4, ''.join(cur_body)))
                    cur_h4 = None
                    cur_body = []
        else:
            if cur_h4 is not None:
                cur_body.append(chunk)
    if cur_h4 is not None:
        blocks.append((cur_h4, ''.join(cur_body)))

    # 结构化表头特征
    struct_patterns = [
        _re.compile(r'字段名称'),
        _re.compile(r'功能名称'),
        _re.compile(r'查询条件'),
        _re.compile(r'取值逻辑说明'),
    ]
    # catch-all 懒表特征（两列，首列是汇总词，次列是「说明」）
    lazy_header = _re.compile(r'<th>(要素|项目|描述|内容|说明)</th><th>说明</th>')
    # 跨章节引用豁免（明确「同 4.x / 见 4.x / 引用 / 逻辑同」的关联小节不查 🟡）
    ref_pat = _re.compile(r'同\s+.*?4\.\d|见\s+4\.\d|引用|参考\s*平台端|详见\s+4\.|逻辑同')

    def has_structured_table(body):
        tables = _re.findall(r'<table>.*?</table>', body, _re.S)
        for t in tables:
            if any(p.search(t) for p in struct_patterns):
                return True
        return False

    def has_any_table(body):
        return '<table>' in body

    def has_lazy_only(body):
        tables = _re.findall(r'<table>.*?</table>', body, _re.S)
        if not tables:
            return False
        # 有结构化表 → 不算懒
        if has_structured_table(body):
            return False
        # 所有表都是 catch-all 汇总表 → 懒
        for t in tables:
            if lazy_header.search(t):
                return True
        return False

    for heading, body in blocks:
        if not heading:
            continue
        # 仅检查「本期新增 / 本期改动」功能点
        if '本期新增' not in heading and '本期改动' not in heading:
            continue
        # 已有-沿用跳过
        if '已有-沿用' in heading:
            continue

        # 🔴 无任何表
        if not has_any_table(body):
            warns.append(
                f"🔴 **功能点「{heading}」偷懒：无任何字段/按钮明细表**。"
                f"\n   按模板必须含列表字段表 / 功能按钮总表 / 查询条件等结构化子节，"
                f"禁止仅用一段文字描述。")
            continue

        # 🔴 仅 catch-all 懒表
        if has_lazy_only(body):
            warns.append(
                f"🔴 **功能点「{heading}」偷懒：仅用「要素/说明」类汇总表充当全部内容**。"
                f"\n   必须按 prd-detail-template.md 拆为：列表字段表（字段名称/需求说明/备注）"
                f"+ 排序/分页/合计/唯一性、功能按钮总表、每个按钮独立小节"
                f"（功能说明/显示位置/权限/前置条件/功能实现=逐步+异常+校验文案）、"
                f"查询条件表、字段级数据来源、状态流转。")

        # 🟡 仅对「含结构化表 + 非跨章节引用」的真实详情小节做补充检查
        is_ref = bool(ref_pat.search(body))
        if is_ref:
            continue
        if has_structured_table(body):
            if ('数据来源' not in body) and ('取值逻辑' not in body):
                warns.append(
                    f"🟡 **功能点「{heading}」缺字段级数据来源**："
                    f"未说明字段来自《XX表》/调XX接口，需补「数据来源（字段级）」小节。")
            # 含功能按钮总表的交互类功能点才查前置条件/权限
            if ('功能按钮总表' in body) and ('前置条件' not in body) and ('权限' not in body):
                warns.append(
                    f"🟡 **功能点「{heading}」缺前置条件/权限说明**："
                    f"需补按钮级前置条件与权限（菜单/数据范围）。")

    return (warns,)


def scan_table_quality(html_text):
    """扫描 HTML 中所有 <table> 的结构/排版异常。

    检测项分两级：
      🔴 结构性（必须修）：表头列数不匹配、空单元格无占位符
      🟡 排版风险（建议修）：td 内换行/内联样式、缺说明、colspan/rowspan

    返回 (struct_warns, style_warns, table_count)。
    """
    from html.parser import HTMLParser

    class _TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tables = []
            self._cur = None
            self._in_thead = False
            self._in_tbody = False
            self._cur_row = []
            self._row_cells = 0

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self._cur = {"has_thead": False, "has_caption": False,
                             "head_cols": [], "body_rows": [],
                             "empty_tds": [], "br_in_td": [],
                             "inline_style_in_td": [], "has_colspan_rowspan": False}
                self.tables.append(self._cur)
            elif tag == "caption" and self._cur:
                self._cur["has_caption"] = True
            elif tag == "thead" and self._cur:
                self._in_thead = True
                self._cur["has_thead"] = True
            elif tag == "tbody" and self._cur:
                self._in_tbody = True
            elif tag in ("tr",) and self._cur:
                self._cur_row = []
                self._row_cells = 0
            elif tag in ("td", "th") and self._cur:
                self._cur_row.append({"tag": tag, "text": "", "colspan": 1,
                                       "has_br": False, "has_inline_style": False,
                                       "is_empty": True})
                for k, v in attrs:
                    if k == "colspan":
                        try: self._cur_row[-1]["colspan"] = int(v)
                        except ValueError: pass
                cs = self._cur_row[-1]["colspan"]
                if cs > 1:
                    self._cur["has_colspan_rowspan"] = True
                self._row_cells += cs

        def handle_endtag(self, tag):
            if tag == "thead":
                # flush 未关闭 tr（某些 HTML 中 </tr> 可能在 </thead> 之后）
                if self._row_cells > 0 and self._cur:
                    self._cur["head_cols"].append(self._row_cells)
                    self._cur_row = []
                    self._row_cells = 0
                self._in_thead = False
            elif tag == "tbody":
                self._in_tbody = False
            elif tag == "tr" and self._cur:
                if self._in_thead:
                    if self._row_cells > 0:
                        self._cur["head_cols"].append(self._row_cells)
                elif self._in_tbody or not self._in_thead:
                    row_info = {"cols": self._row_cells, "cells": list(self._cur_row)}
                    self._cur["body_rows"].append(row_info)
                self._cur_row = []
                self._row_cells = 0
            elif tag in ("td", "th") and self._cur_row:
                cell = self._cur_row[-1]
                txt = cell["text"].strip()
                cell["is_empty"] = not bool(txt)
                if (cell["is_empty"] and
                    (self._in_tbody or (not self._in_thead and self._cur.get("body_rows")))):
                    self._cur["empty_tds"].append("(空)")
                if cell["has_br"]:
                    self._cur["br_in_td"].append(txt[:30] or "(含br)")
                if cell["has_inline_style"]:
                    self._cur["inline_style_in_td"].append(txt[:30] or "(含style)")

        def handle_data(self, data):
            if self._cur_row:
                self._cur_row[-1]["text"] += data
                if "<br" in data or "\n" in data:
                    self._cur_row[-1]["has_br"] = True
                if "style=" in data:
                    self._cur_row[-1]["has_inline_style"] = True

    parser = _TableParser()
    try:
        parser.feed(html_text)
    except Exception:
        return [], [], 0

    struct_warns = []
    style_warns = []

    for idx, t in enumerate(parser.tables, 1):
        tlabel = f"表格#{idx}"
        # 跳过非数据表格：
        #   a) 极小表格（≤1 行数据，通常是状态/指标小表）
        #   b) 无 thead 的宽表（通常是属性-值型信息卡，如文档头/参数表）
        is_info_card = (not t["has_thead"] and
                        len(t["body_rows"]) > 0 and
                        all(r["cols"] <= 2 for r in t["body_rows"]))
        if len(t["body_rows"]) <= 1 or is_info_card:
            continue

        head_set = set(t["head_cols"]) if t["head_cols"] else set()
        ref_cols = t["head_cols"][0] if t["head_cols"] else 0

        # 🔴 1) thead 内行列数不一致
        if len(head_set) > 1:
            struct_warns.append(
                f"[{tlabel}] thead 各行列数不一致（{t['head_cols']}），表头错乱")
        # 🔴 2) 数据行与表头列数不匹配
        for ri, row in enumerate(t["body_rows"], 1):
            if row["cols"] != 0 and row["cols"] != ref_cols:
                struct_warns.append(
                    f"[{tlabel}] 数据行第{ri}行({row['cols']}列)≠表头({ref_cols}列)，渲染必错位")
        # 🔴 3) 空单元格无占位符
        empty_count = sum(1 for r in t["body_rows"] for c in r["cells"]
                          if c.get("is_empty") and c["tag"] == "td")
        if empty_count > 0:
            struct_warns.append(
                f"[{tlabel}] {empty_count} 个空 <td> 无占位符（建议填「—」），可能塌陷")

        # 🟡 4) 缺 thead
        if not t["has_thead"]:
            style_warns.append(f"[{tlabel}] 缺少 <thead>，表头无语义区分")
        # 🟡 5) td 内 <br>
        if t["br_in_td"]:
            style_warns.append(
                f"[{tlabel}] {len(t['br_in_td'])} 个 <td> 含 <br> 换行"
                f"（例：{t['br_in_td'][0]}…）")
        # 🟡 6) 内联 style
        if t["inline_style_in_td"]:
            style_warns.append(
                f"[{tlabel}] {len(t['inline_style_in_td'])} 个 <td> 用内联 style"
                f"（例：{t['inline_style_in_td'][0]}…）")
        # 🟡 7) colspan/rowspan
        if t["has_colspan_rowspan"]:
            style_warns.append(f"[{tlabel}] 使用 colspan/rowspan，注意跨行对齐")

        # ---- 新增：CSS 视觉渲染层检测（结构正确但渲染可能错位）----
        # 8) 🟡 td 内含 <br> + 长文字（>12字）→ 撑爆列宽风险
        long_br_cells = []
        for ri, row in enumerate(t["body_rows"], 1):
            for ci, cell in enumerate(row["cells"]):
                txt = cell.get("text", "").strip()
                if cell.get("has_br") and len(txt) > 12:
                    long_br_cells.append(
                        f"R{ri}C{ci}({len(txt)}字):「{txt[:20]}…」")
        if long_br_cells:
            style_warns.append(
                f"[{tlabel}] {len(long_br_cells)} 个 <td> 含 <br>+长文字"
                f"(>12字)，可能撑爆列宽导致视觉错位。"
                f"建议：缩短文字 / 加 table-layout:fixed + word-break。"
                f"例：{long_br_cells[0]}")

        # 9) 🔴 表格缺 table-layout:fixed 且存在长内容 td → 高错位风险
        has_fixed_layout = bool(re.search(
            r'table-layout\s*:\s*fixed', html_text))
        has_word_break = bool(re.search(
            r'(?:th|td)\s*\{[^}]*word-break', html_text,
            re.DOTALL))
        if (not has_fixed_layout and long_br_cells):
            struct_warns.append(
                f"[{tlabel}] 🔴 CSS 错位风险：<table> 缺 "
                f"`table-layout:fixed`，且有 {len(long_br_cells)} 个长内容 "
                f"<td>，浏览器会按内容自动分配列宽导致错位！"
                f"必须加 `table-layout:fixed` + `word-break:break-all`。")

        # 10) 🟡 单个 td 纯文本超长（>40字）无截断控制
        long_text_cells = []
        for ri, row in enumerate(t["body_rows"], 1):
            for ci, cell in enumerate(row["cells"]):
                txt = cell.get("text", "").strip()
                if len(txt) > 40 and not cell.get("has_br"):
                    long_text_cells.append(
                        f"R{ri}C{ci}({len(txt)}字)")
        if long_text_cells:
            style_warns.append(
                f"[{tlabel}] {len(long_text_cells)} 个 <td> 纯文本超长(>40字)"
                f"（{long_text_cells[0]}），建议折行或精简文案。")

        # 11) 🔴 矩阵表（≥4列 + 短标记单元格占比≥50%）必须用 SVG 绘制（v1.0.15）
        #     经验证：HTML <table> 在 GitHub Pages / Jekyll 渲染管道下会发生
        #     列错位（数据列全部挤到一列），colgroup + table-layout:auto 均无法根治
        #     ——属平台级渲染差异，CSS 调整无效。凡「端口×模块 / 状态×条件 /
        #     角色×权限」等交叉矩阵表（单元格以 ✓/—/已有功能 等短标记为主），
        #     一律用 <svg> 重绘（每个单元格 = 独立定位的 <rect> + <text>）。
        #     注意：状态明细表/字段表（单元格以长文本为主，— 仅作空占位）不算
        #     矩阵表，HTML <table> 渲染正常，不触发本条。
        matrix_markers = ['✓', '—', '●', '○', '✕', '✔', '已有功能',
                          '待定', '可选', '不支持', '部分支持']
        marker_cells = 0
        total_cells = 0
        for r in t['body_rows']:
            for c in r['cells']:
                txt = c.get('text', '').strip()
                if not txt:
                    continue
                total_cells += 1
                # 短标记单元格：文本≤8字且含标记符号（— 仅作空占位也计入）
                if len(txt) <= 8 and any(m in txt for m in matrix_markers):
                    marker_cells += 1
        marker_ratio = marker_cells / total_cells if total_cells else 0
        if ref_cols >= 4 and marker_ratio >= 0.5:
            struct_warns.append(
                f"[{tlabel}] 🔴 **矩阵表必须用 SVG 绘制**：本表 {ref_cols} 列，"
                f"短标记单元格占比约 {marker_ratio*100:.0f}%（✓/—/已有功能 等），"
                f"属交叉矩阵表。"
                f"经验证 HTML <table> 在 GitHub Pages/Jekyll 渲染下会发生列错位"
                f"（数据列全部挤到一列），colgroup + table-layout:auto 均无法根治。"
                f'\n   修复：改用 <svg> 重绘矩阵表（参照 PRD §3.2 流程图 SVG 方案——'
                f'每个单元格 = 独立定位的 <rect> + <text>，任意环境渲染一致）。'
                f'\n   规则：凡「端口×模块 / 状态×条件 / 角色×权限」类矩阵表，'
                f'一律 SVG 绘制，禁止用 HTML <table>。')

    return struct_warns, style_warns, len(parser.tables)


# ---- 辅助函数：提取第 N 个 <table> 的原始 HTML 片段 ----
def _extract_table_Nth(full_html, table_index):
    """从完整 HTML 中提取第 N 个（1-based）<table> 的原始片段。"""
    count = 0
    pos = 0
    while True:
        start = full_html.find('<table', pos)
        if start == -1:
            return ""
        count += 1
        if count == table_index:
            end = full_html.find('</table>', start)
            if end == -1:
                return full_html[start:]
            return full_html[start:end + 8]
        pos = start + 1


def detect_edge_exe():
    """定位 Edge 可执行文件（headless 截图用）。"""
    candidates = [
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    import shutil
    return shutil.which('msedge') or ''


def force_view(html, view_id, kind):
    """在原型 HTML 中强制显示指定视图（移除 hidden / 置为 active），返回新 HTML。"""
    if kind == 'app':
        # App 原型：<section class="page active" id="p_x"> —— 先把所有 active 复位，再激活目标
        html = re.sub(r'class="page active"', 'class="page"', html)
        html = re.sub(r'(<section class="page" id="%s")' % re.escape(view_id),
                      r'\1 class="active"', html)
    elif kind == 'modal':
        # 弹窗：去除 display:none，加 show 类
        html = re.sub(r'id="%s" style="display:none"' % re.escape(view_id),
                      r'id="%s" class="show"' % re.escape(view_id), html)
        html = re.sub(r'id="%s" class="hidden"' % re.escape(view_id),
                      r'id="%s" class="show"' % re.escape(view_id), html)
    else:
        # 平台端/商家端后台原型：<div id="viewX" class="hidden"> —— 先全量隐藏，再显示目标
        html = re.sub(r'(<div id="view[A-Za-z0-9]+")(\s+class="[^"]*")?',
                      lambda m: m.group(1) + ' class="hidden"', html)
        html = re.sub(r'<div id="%s" class="hidden">' % re.escape(view_id),
                      r'<div id="%s">' % re.escape(view_id), html)
    return html


def capture_view_screenshot(proto_path, view_id, dst_path, kind, edge_exe=None, trigger=None):
    """从原型 HTML 截取指定视图为 1440×900 PNG。成功返回 True。
    trigger：可选 JS 片段（如 'setTimeout(showArrival,200);'），注入快照 </body> 前触发弹窗内容渲染。"""
    if not edge_exe:
        edge_exe = detect_edge_exe()
    if not edge_exe or not os.path.exists(edge_exe):
        return False
    try:
        with open(proto_path, encoding='utf-8', errors='ignore') as f:
            html = f.read()
        html = force_view(html, view_id, kind)
        if trigger:
            html = html.replace('</body>', '<script>%s</script></body>' % trigger)
        snap = proto_path + '.snap_tmp.html'
        with open(snap, 'w', encoding='utf-8') as f:
            f.write(html)
        import subprocess
        result = subprocess.run(
            [edge_exe, '--headless=new', '--disable-gpu',
             '--screenshot=' + dst_path, '--window-size=1440,900',
             'file:///' + snap.replace('\\', '/')],
            capture_output=True, text=True, timeout=30)
        os.remove(snap)
        return os.path.exists(dst_path) and os.path.getsize(dst_path) > 0
    except Exception:
        return False


def detect_prototype_kind(proto_path):
    """判断原型类型：app / platform / modal（按 DOM 特征）。"""
    try:
        with open(proto_path, encoding='utf-8', errors='ignore') as f:
            head = f.read(20000)
    except Exception:
        return 'platform'
    if 'class="page active"' in head or 'class="page"' in head:
        return 'app'
    return 'platform'


def find_missing_screenshot_sections(html_text):
    """返回缺原型截图的功能点小节列表（合并 §4.25 + §4.29 判定，供 --auto-fill 使用）。
    每项：{title, start, end, reason}。

    判定（与 §4.25 报告逻辑保持一致，避免误把"被父级总览图覆盖"的子功能当缺失）：
    - 后台端（平台端/商家端）功能点：无 own <img> → 缺失（必须补）
    - 标题含独立页面关键词（详情/新建/编辑/列表/看板/查询/管理）：无 own <img> → 缺失
    - 弹窗/Modal 类（已排除 差异/规范/外壳/入口 等非组件）：无 own <img> → 缺失
    - 其余客户端子功能：若所在 h3 顶部已有父级总览图 → 视为已覆盖（跳过）；
      否则仍判缺失（避免"很多图缺失"）。
    """
    missing = []
    modal_keywords = ['弹窗', '弹框', 'Modal', 'Popup', '对话框', '抽屉', 'overlay', 'dialog']
    modal_exclude = ['差异', '对比', '规范', '外壳', 'diff', '入口', '示意', '总览', '引用', '说明']
    distinct_keywords = ['详情', '新建', '编辑', '列表', '看板', '数据看板', '查询', '管理']
    h4_positions = [m.start() for m in re.finditer(r'<h4', html_text)]
    h3_positions = [m.start() for m in re.finditer(r'<h3[^>]*>', html_text)]

    # h3 后 500 字符内是否有父级总览图
    h3_has_img = {}
    for h3_pos in h3_positions:
        h3_has_img[h3_pos] = bool(re.search(r'<img\s', html_text[h3_pos:h3_pos + 500]))

    for m in re.finditer(r'<h4[^>]*>(.+?)</h4>', html_text, re.DOTALL):
        full = m.group(0)
        title_text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        tag_text = ''
        tm = re.search(r'class="tag[^"]*y[^"]*">([^<]+)</span>', full)
        if tm:
            tag_text = tm.group(1).strip()

        is_new = ('本期新增' in tag_text or '本期改动' in tag_text)
        is_modal = any(kw in title_text for kw in modal_keywords) and \
                   not any(ex in title_text for ex in modal_exclude)

        if not (is_new or is_modal):
            continue

        start_pos = m.end()
        h4_idx = next((i for i, p in enumerate(h4_positions) if p == m.start()), -1)
        end_pos = html_text.find('<h4', start_pos) if h4_idx >= 0 and h4_idx + 1 < len(h4_positions) else len(html_text)
        section_html = html_text[start_pos:end_pos]

        if re.search(r'<img\s', section_html):
            continue  # 已有截图，跳过

        # 找最近的 h3（判定后台端 + 父级图）
        prev_h3 = None
        for h3_pos in h3_positions:
            if h3_pos < m.start():
                prev_h3 = h3_pos
            else:
                break
        is_backend = False
        has_parent_img = False
        if prev_h3 is not None:
            h3_end = html_text.find('</h3>', prev_h3)
            h3_text = html_text[prev_h3:h3_end] if h3_end > prev_h3 else ''
            is_backend = bool(re.search(r'平台端后台|商家端后台', h3_text))
            has_parent_img = h3_has_img.get(prev_h3, False)

        has_distinct = any(kw in title_text for kw in distinct_keywords)

        # 跳过条件：非后台 + 被父级总览图覆盖 + 非独立页面 + 非弹窗
        if (not is_backend) and has_parent_img and (not has_distinct) and (not is_modal):
            continue  # 视为已覆盖（如首页入口卡被首页总览图覆盖）

        reason = '§4.25 本期新增/改动缺图' if is_new else '§4.29 弹窗缺独立截图'
        missing.append({'title': title_text, 'start': start_pos, 'end': end_pos, 'reason': reason})
    return missing


def auto_fill_prototype_screenshots(prd_path):
    """检出缺图 → 直接生成并插入截图（不询问）。返回 (filled, failed, skipped)。

    依赖 PRD 同目录的 prototype_screenshot_map.json：
    {
      "<h4标题(去tag)>": [
        {"proto": "平台端后台原型.html", "view": "viewX",
         "out": "coupon-prd-assets/xxx.png", "label": "说明", "kind": "platform|app|modal(可选)"}
      ]
    }
    已有 <img> 的小节或 mapping 未覆盖的小节会被跳过（skipped 报告人工处理）。
    """
    prd_dir = os.path.dirname(os.path.abspath(prd_path))
    map_path = os.path.join(prd_dir, 'prototype_screenshot_map.json')
    if not os.path.exists(map_path):
        return [], [], [('NO_MAP', '未找到 prototype_screenshot_map.json，无法自动补图')]

    with open(map_path, encoding='utf-8') as f:
        mapping = json.load(f)

    with open(prd_path, encoding='utf-8', errors='ignore') as f:
        html = f.read()

    missing = find_missing_screenshot_sections(html)
    filled, failed, skipped = [], [], []

    # 建立标题→插入位置的映射（在 html 中按 start 定位）
    for item in missing:
        title = item['title']
        # 匹配 mapping 键：精确 → 包含
        matched_keys = [k for k in mapping if k == title]
        if not matched_keys:
            matched_keys = [k for k in mapping if k in title or title in k]
        if not matched_keys:
            skipped.append((title, 'mapping 未覆盖，需人工补图'))
            continue
        key = matched_keys[0]
        specs = mapping[key]
        gen_imgs = []
        ok = True
        for spec in specs:
            proto = os.path.join(prd_dir, spec['proto'])
            if not os.path.exists(proto):
                failed.append((title, f"原型文件不存在：{spec['proto']}"))
                ok = False
                continue
            kind = spec.get('kind') or detect_prototype_kind(proto)
            out_rel = spec['out']
            dst = os.path.join(prd_dir, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if capture_view_screenshot(proto, spec['view'], dst, kind, trigger=spec.get('trigger')):
                gen_imgs.append((out_rel, spec.get('label', title)))
            else:
                failed.append((title, f"截图失败：{spec['proto']}#{spec['view']}"))
                ok = False
        if ok and gen_imgs:
            # 插入 <img> 到该小节开头（</h4> 之后）
            imgs_html = ''.join(
                f'<p><img src="{rel}" style="max-width:100%;max-height:800px;'
                f'border:1px solid #e0e0e0;border-radius:8px;object-fit:contain;" '
                f'alt="{lbl}"></p>' for rel, lbl in gen_imgs)
            insert_at = html.find('</h4>', item['start'] - 50) + len('</h4>')
            html = html[:insert_at] + '\n' + imgs_html + '\n' + html[insert_at:]
            filled.append((title, [g[0] for g in gen_imgs]))

    if filled:
        with open(prd_path, 'w', encoding='utf-8') as f:
            f.write(html)

    return filled, failed, skipped


def main():
    auto_fill = '--auto-fill' in sys.argv
    if len(sys.argv) < 2:
        print("用法：python check_prd.py <prd文件> [--auto-fill]")
        sys.exit(2)
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"文件不存在：{path}")
        sys.exit(2)

    text = get_text(path)
    norm = text.lower()

    # 表格扫描需要原始 HTML（含标签），仅对 HTML 文件生效
    raw_html = ""
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.html', '.htm'):
        with open(path, encoding='utf-8', errors='ignore') as f:
            raw_html = f.read()

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
    rl = scan_red_line(text, raw_html)
    ut = scan_uncertain_traceability(text)
    tv = scan_tracking_v23(text, norm)
    dg_found, dg_check = scan_diagram_consistency(text)
    tq_struct, tq_style, tq_cnt = scan_table_quality(raw_html) if raw_html else ([], [], 0)
    rd_hits = scan_redundant_declarations(text)
    fd_warns, fd_infos = scan_flow_diagram_consistency(raw_html if raw_html else html_text, text)
    sm_warns, sm_infos = scan_state_machine(text, raw_html if raw_html else html_text)
    st_warns, st_infos = scan_scope_tagging(text)
    ph_warns, ph_infos = scan_pending_hygiene(text, raw_html if raw_html else html_text)
    rw_warns, rw_fixes = scan_resolved_warn_boxes(raw_html if raw_html else html_text)
    pl_warns, = scan_prototype_link_instead_of_image(raw_html if raw_html else html_text)
    pi_warns, = scan_prototype_image_valid(raw_html if raw_html else html_text, path)
    po_warns, = scan_prototype_image_oversized(raw_html if raw_html else html_text, path)
    rv_warns, = scan_reuse_function_verbose(raw_html if raw_html else html_text)
    sr_warns, = scan_prototype_screen_ratio(raw_html if raw_html else html_text, path)

    # ---- 新增：范围一致性 / 冗余框 / 范围泄漏检测（V1.0.21）----
    st_warns, = scan_scope_tag_mismatch(raw_html if raw_html else html_text, path)
    # vn_warns: scan_verbose_nfr_warnings (function removed in earlier refactor, placeholder kept)
    vn_warns = []
    sl_warns, = scan_scope_leak_feature(raw_html if raw_html else html_text)
    ld_warns, = scan_lazy_function_detail(raw_html if raw_html else html_text)
    rmtm_warns, = scan_requirement_md_tag_mismatch(raw_html if raw_html else html_text, path)
    mpf_blockers, mpf_warns = scan_missing_prototype_for_new_features(raw_html if raw_html else html_text)
    mvs_warns, = scan_mixed_view_screenshot(raw_html if raw_html else html_text)
    mps_warns, = scan_modal_popup_missing_screenshot(raw_html if raw_html else html_text)
    vta_warns, = scan_verbose_table_annotations(raw_html if raw_html else html_text)

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

    # 表格质量扫描
    if tq_cnt > 0:
        if tq_struct:
            print(f"### 📋 表格结构性异常（{len(tq_struct)} 处，必须修）")
            for w in tq_struct:
                print(f"- 🔴 {w}")
            print()
        if tq_style:
            print(f"### 📋 表格排版风险（{len(tq_style)} 处，建议修）")
            for w in tq_style:
                print(f"- 🟡 {w}")
            print()
        if not tq_struct and not tq_style:
            print("✅ 全部表格结构正常、排版规范。")
    else:
        print("（未检测到 <table> 标签，跳过表格质量扫描）")

    # 冗余声明扫描
    if rd_hits:
        print(f"### 🗑️ 冗余声明（{len(rd_hits)} 处，建议删除）")
        for pat_name, desc, snippet in rd_hits:
            print(f"- ⚠️ [{desc}] 命中「{pat_name}」：…{snippet}…")
        print()
        print("处理要求：PRD 应直接写「做什么/怎么做」，不需要自证式免责/范围说明块。")
        print("除非用户明确要求保留，否则一律删除。")
        print()
    else:
        print("✅ 未发现冗余声明/免责块。")

    # 业务流程图一致性扫描
    if fd_warns or fd_infos:
        print(f"### 🔄 业务流程图一致性（{len(fd_warns)} 告警 / {len(fd_infos)} 提示）")
        for w in fd_warns:
            print(f"- {w}")
            print()
        for i in fd_infos:
            print(f"- 💡 {i}")
        if not fd_warns:
            print()
    else:
        pass  # 无流程图相关内容，静默跳过

    # 状态机完整性扫描
    if sm_warns or sm_infos:
        print(f"### ⚙️ 状态机完整性（{len(sm_warns)} 告警 / {len(sm_infos)} 提示）")
        for w in sm_warns:
            print(f"- {w}")
            print()
        for i in sm_infos:
            print(f"- 💡 {i}")
        if not sm_warns:
            print()
    else:
        pass  # 无状态机内容，静默跳过

    # 功能范围标注扫描
    if st_warns or st_infos:
        print(f"### 🏷️ 功能范围标注（{len(st_warns)} 告警 / {len(st_infos)} 提示）")
        for w in st_warns:
            print(f"- ⚠️ {w}")
        for i in st_infos:
            print(f"- 💡 {i}")
        print()
        print("处理要求：§四 每个功能点须标注 已有-沿用 / 本期新增 / 本期改动；"
              "已有功能仅写一句「沿用现有功能，详见原型」，不展开细节。")
        print()
    else:
        print("✅ 全部功能点已标注范围（已有/新增/改动）。")

    # 待确认项卫生 + 状态机前后矛盾扫描
    if ph_warns or ph_infos:
        print(f"### 🧹 待确认项卫生 / 状态机前后矛盾（{len(ph_warns)} 告警 / {len(ph_infos)} 提示）")
        for w in ph_warns:
            print(f"- {w}")
            print()
        for i in ph_infos:
            print(f"- 💡 {i}")
        print()
        print("处理要求：待确认项不得与「设计如此/已有-沿用」决策冲突，"
              "不得前后矛盾（状态机同一状态不能既声明无编辑又保留编辑行）。")
        print()
    else:
        print("✅ 待确认项无与现有功能/设计决策冲突，状态机无前后矛盾。")

    if rw_warns:
        print(f"### 🗑️ 冗余警告框（{len(rw_warns)} 处，应直接删除）")
        for w in rw_warns:
            print(f"- {w}")
            print()
        print("处理要求：以上 warn 框内容全部为「已解决/设计如此/已确认」"
              "等已闭环项 → 直接删除整个 <div class=\"warn\"> 块，无需保留。")
        print()
    else:
        print("✅ 无冗余警告框（所有 ⚠️ 框均含未闭环待确认项或合法说明）。")

    if pl_warns:
        print(f"### 🖼️ 原型示意应为截图（{len(pl_warns)} 处，链接→截图）")
        for w in pl_warns:
            print(f"- {w}")
            print()
        print("处理要求：将「原型示意：<a href>」替换为"
              "「<img src=\"原型截图/xxx.png\">」（Edge headless 截图）。")
        print()
    else:
        print("✅ 所有「原型示意」均已嵌入截图（非文字链接）。")

    if pi_warns:
        print(f"### 🖼️ 原型截图有效性检查（{len(pi_warns)} 处，§4.16 图片/样式/路径）")
        for w in pi_warns:
            print(f"- {w}")
            print()
        print("处理要求：确保截图文件存在本地+已推送到 GitHub、"
              "<img> 含 style(max-width+max-height+border) + alt 属性。")
        print()
    else:
        print("✅ 所有「原型示意」截图文件存在、样式规范、语义完整。")

    if po_warns:
        print(f"### 📐 原型截图尺寸检查（{len(po_warns)} 处，§4.17 超大图/空白）")
        for w in po_warns:
            print(f"- {w}")
            print()
        print("处理要求：给 <img> 加 max-height:800px;object-fit:contain; "
              "或重新截图缩小 --window-size 高度参数。")
        print()
    else:
        print("✅ 所有「原型示意」截图尺寸合理（高度≤1200px，无超大空白）。")

    if rv_warns:
        print(f"### 📝 「已有-沿用」冗余检查（{len(rv_warns)} 处，§4.18 禁止废话）")
        for w in rv_warns:
            print(f"- {w}")
            print()
        print("处理要求：「已有-沿用」功能点只允许写一句「沿用现有功能。」"
              "——不展开按钮列表、原型链接、「本期仅补充」等上下文说明。")
        print()
    else:
        print("✅ 所有「已有-沿用」功能点均只写标准文案，无冗余赘述。")

    if sr_warns:
        print(f"### 🖥️ 原型截图尺寸检查（{len(sr_warns)} 处，§4.19 统一PC尺寸）")
        for w in sr_warns:
            print(f"- {w}")
            print()
        print("处理要求：所有原型截图统一使用 PC 端尺寸 1440×900，"
              "不再区分终端类型。")
        print()
    else:
        print("✅ 所有原型截图屏幕比例正确（PC端≥1000px / 移动端≤500px）。")

    # ---- V1.0.21 新增规则输出 ----
    if st_warns:
        print(f"### 📋 功能点 tag 与业务梳理表不一致（{len(st_warns)} 处，§4.20 范围对照）")
        for w in st_warns:
            print(f"- {w}")
            print()
        print("处理要求：对照需求梳理阶段确认的范围表（MD/Excel），"
              "修正功能点 tag 标注。禁止跨端口套用状态。")
        print()
    else:
        print("✅ 功能点 tag 与业务梳理表范围一致（或未找到梳理文件供对照）。")

    if vn_warns:
        print(f"### 🗑️ 非功能性需求章节冗余说明框（{len(vn_warns)} 处，§4.21 冗余框）")
        for w in vn_warns:
            print(f"- {w}")
            print()
        print("处理要求：删除 §五~§九 中的操作指引型 warn/note 框，"
              "PRD 只保留需求说明，不写执行规范。")
        print()
    else:
        print("✅ 非功能性需求章节无冗余说明框。")

    if sl_warns:
        print(f"### 🚫 PRD 出现本期范围外的功能/概念（{len(sl_warns)} 处，§4.22 范围泄漏）")
        for w in sl_warns:
            print(f"- {w}")
            print()
        print("处理要求：删除所有不在本期需求范围内的功能/概念引用，"
              "或先更新范围表再加入功能说明。")
        print()
    else:
        print("✅ 未发现本期范围外的功能/概念泄漏。")

    # ---- V1.0.22 新增：功能详情懒写检测 ----
    if ld_warns:
        print(f"### ✍️ 功能需求详情偷懒检测（{len(ld_warns)} 处，§4.23 逐页面逐功能点）")
        for w in ld_warns:
            print(f"- {w}")
            print()
        print("处理要求：每个「本期新增/本期改动」功能点必须按 prd-detail-template.md 拆为"
              "列表字段表（字段名称/需求说明/备注）+ 排序/分页/合计/唯一性、"
              "功能按钮总表、每个按钮独立小节（功能说明/显示位置/权限/前置条件/功能实现=逐步+异常+校验文案）、"
              "查询条件表、字段级数据来源、状态流转。禁止仅用「要素/说明」汇总表充当全部内容。")
        print()
    else:
        print("✅ 所有「本期新增/本期改动」功能点均按模板逐页面逐功能点拆解，无偷懒。")

    if rmtm_warns:
        print(f"### 📋 PRD tag 与业务梳理 MD 矛盾（{len(rmtm_warns)} 处，§4.24 MD交叉比对）")
        for w in rmtm_warns:
            print(f"- {w}")
            print()
        print("处理要求：以业务梳理 MD（线下定稿/范围确认）为唯一权威来源，"
              "MD 标注「暂无/需新增」的功能必须标 <span class=\"tag y\">本期新增</span> 并补详细 FR。")
        print()
    else:
        pass  # 无 MD 文件或无矛盾时不输出

    # §4.25+§4.28 缺截图：阻断级（blockers）优先输出，再输出提醒级（warns）
    if mpf_blockers:
        print(f"### 🚨🖼️ 新增/改动功能缺少原型截图 [阻断级]（{len(mpf_blockers)} 处，不补图不可定版 · §4.25+§4.28）")
        for w in mpf_blockers:
            print(f"- {w}")
            print()
        print("⛔ **阻断级要求**：以上为独立页面/后台页面/表单类功能点，"
              "必须从对应端口原型 HTML 截取 1440×900 独立截图，"
              "以 <img> 标签插入该 h4 小节内。tag 从「已有-沿用」升级为「本期新增」时必须同步补图。")
        print()

    if mpf_warns:
        print(f"### 🟡🖼️ 新增/改动功能无独立原型截图 [提醒级]（{len(mpf_warns)} 处，建议补图 · §4.25）")
        for w in mpf_warns:
            print(f"- {w}")
            print()
        print("💡 提醒：以上为客户端子功能点或已有父级总览图覆盖的功能点，"
              "建议补独立截图提升可读性；如确由父级图覆盖可忽略本提醒。")
        print()

    if not mpf_blockers and not mpf_warns:
        pass  # 无缺图问题

    if mvs_warns:
        print(f"### 🖼️ 多视图截图未拆分（{len(mvs_warns)} 处，§4.26 混合截图）")
        for w in mvs_warns:
            print(f"- {w}")
            print()
        print("处理要求：每个视图（列表/新建/编辑/详情/弹窗）必须分别截取独立截图，"
              "以独立的 <img> 标签插入，禁止多视图混在一张图里。")
        print()

    if mps_warns:
        print(f"### 🔴 弹窗/弹框类功能点缺少独立截图（{len(mps_warns)} 处，§4.29 弹窗截图）")
        for w in mps_warns:
            print(f"- {w}")
            print()
        print("处理要求：弹窗是独立 UI 组件，必须从原型中触发弹窗状态后截取独立截图"
              "（1440×900），展示弹窗完整内容。不可仅引用父级页面总览图替代。")
        print()

    if vta_warns:
        print(f"### 📝 表格冗余验证备注（{len(vta_warns)} 处，§4.27 冗余备注）")
        for w in vta_warns:
            print(f"- {w}")
            print()
        print("处理要求：删除所有绿色 ✅ 验证备注/方案确认/截图验证等开发调试笔记。"
              "如为必要业务规则说明，改写为正式表述（去掉 ✅ 前缀和括号备注格式）。")
        print()

    # ---------- 阶段5（扩展）：重复截图检测 ----------
    sdup_warns = scan_screenshot_duplicates(
        raw_html if raw_html else html_text,
        os.path.dirname(path) if path else None)
    if sdup_warns:
        print(f"### 🔁 重复截图检测（{len(sdup_warns)} 处，§4.30 重复截图）")
        for w in sdup_warns:
            print(f"- {w}")
            print()
        print("处理要求：重新从原型截取重复视图，确保每张图内容独立、md5 不同"
              "（导入 Word/钉钉后才不会因去重而缺图）。")
        print()

    # ---------- 自动补图（--auto-fill）----------
    if auto_fill:
        print()
        print("## 🤖 自动补图（--auto-fill）")
        print()
        filled, failed, skipped = auto_fill_prototype_screenshots(path)
        if filled:
            print(f"✅ 已自动补图 {len(filled)} 处：")
            for t, imgs in filled:
                print(f"- {t} → {', '.join(imgs)}")
            print()
        if failed:
            print(f"⚠️ 补图失败 {len(failed)} 处（需排查原型/视图）：")
            for t, msg in failed:
                print(f"- {t}：{msg}")
            print()
        if skipped:
            print(f"ℹ️ 跳过 {len(skipped)} 处（mapping 未覆盖，需人工补图）：")
            for t, msg in skipped:
                print(f"- {t}：{msg}")
            print()
        if not (filled or failed or skipped):
            print("✅ 无缺图，无需补图。")
            print()

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
    red_total = len(rl) + len(ut) + len(tv) + len(tq_struct) + len(rd_hits) + len(fd_warns) + len(sm_warns) + len(st_warns) + len(ph_warns)
    if red_total:
        print(f"⚠️ **阶段4 发现 {red_total} 处风险**（红线词 {len(rl)} / 待确认悬空 {len(ut)}"
              f" / 埋点规范 {len(tv)} / 表格结构异常 {len(tq_struct)}"
              f" / 冗余声明 {len(rd_hits)} / 流程图一致性 {len(fd_warns)}"
              f" / 状态机完整性 {len(sm_warns)} / 功能范围标注 {len(st_warns)}"
              f" / 待确认项卫生 {len(ph_warns)}）："
              "须逐项确认或修正后再定稿。")
    print()


if __name__ == '__main__':
    main()
