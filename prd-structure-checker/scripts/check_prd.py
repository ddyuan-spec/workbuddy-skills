#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRD 结构排查脚本
扫描一份 PRD 文档（.md/.txt/.docx/.html），对照必含板块清单，
分三阶段输出报告：
  阶段1（结构存在性）：一~九 必含板块是否出现（缺失即不通过）。
  阶段2（§D 内容深度）：功能需求详情是否达到"模板式详清"门槛
        （逐页原型截图 / 字段明细表 / 按钮权限表 / 逐步操作逻辑 /
         查询条件规格 / 数据来源标注 / 计算公式 / 显示位置等）。
  阶段3（待确认项扫描）：检测全文"待确认/需确认/@X确认/TBD/待补充"等
        标记，提醒向用户澄清或保留占位，禁止臆测填充。
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
    print()


if __name__ == '__main__':
    main()
