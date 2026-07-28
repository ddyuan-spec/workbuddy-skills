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
                              r'添加券|编辑券|下架券|支付成功|触发条件|用券)'
            modules_found = set(re.findall(module_patterns, plain_text))
            # 节点中能匹配到模块词的数量
            node_plain = ' '.join(nodes)
            matched = sum(1 for m in modules_found if m in node_plain)
            coverage = matched / len(modules_found) * 100 if modules_found else 100
            if coverage < 50:
                infos.append(
                    f"流程图节点对正文功能模块覆盖度偏低（约 {coverage:.0f}%）；"
                    f"建议确认图中是否遗漏关键环节（如制券模板库、发券引擎、"
                    f"数据看板、核销引擎等后台/服务端环节）")
            else:
                infos.append(f"流程图节点对正文功能模块覆盖度约 {coverage:.0f}% ✅")

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
    loose_start = re.findall(
        r'[^>](任意|所有|全部|无论.*状态)[^<]*\s*(删除|作废|回滚|下架)',
        plain_text)
    if loose_start:
        for start, action in loose_start:
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

    return struct_warns, style_warns, len(parser.tables)


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
    red_total = len(rl) + len(ut) + len(tv) + len(tq_struct) + len(rd_hits) + len(fd_warns) + len(sm_warns)
    if red_total:
        print(f"⚠️ **阶段4 发现 {red_total} 处风险**（红线词 {len(rl)} / 待确认悬空 {len(ut)}"
              f" / 埋点规范 {len(tv)} / 表格结构异常 {len(tq_struct)}"
              f" / 冗余声明 {len(rd_hits)} / 流程图一致性 {len(fd_warns)}"
              f" / 状态机完整性 {len(sm_warns)}）："
              "须逐项确认或修正后再定稿。")
    print()


if __name__ == '__main__':
    main()
