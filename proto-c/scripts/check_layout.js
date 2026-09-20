#!/usr/bin/env node
/**
 * check_layout.js —— C 端原型「布局 / 选中态」硬门禁（proto-c 通用，参数化，跨项目复用）
 *
 * 背景：PROTO-TAB-001。两类高频事故靠冒烟/点击穿透都测不出来：
 *   ① 横向 tab/筛选栏总宽超出视口，末项被挤出可视区（用户完全看不到，且无横滑提示）；
 *   ② 选中态配色凭品牌主色臆断，与基线截图不符（线条/颜色肉眼可辨）。
 * 这些都只有「真实布局引擎 + 计算样式」能测，jsdom（穿透测试）没有布局，测不了 → 必须用 playwright。
 *
 * 用法：
 *   node check_layout.js --src <原型.html> --checks <checks.json> [--viewport 414x900] [--keep-bg]
 *
 * checks.json（数组，每项一个场景/页面态）：
 * [
 *   {
 *     "name": "订单Tab(全部)",              // 必填，场景名
 *     "setup": "goOrders('all')",           // 可选，进页面/切状态的 JS（在页面上下文执行）
 *     "noOverflow": ["#ordTabs"],           // 可选，断言 scrollWidth <= clientWidth+1（无横向溢出）
 *     "inView": [".ord-tabs .ot:last-child"],// 可选，断言元素右缘 <= 其最近滚动容器右缘
 *     "style": [                            // 可选，断言计算样式（用分号或对象；见下）
 *       {"sel": ".ord-tabs .ot.on", "color": "rgb(34, 34, 34)", "fontWeight": "600"},
 *       {"sel": ".ord-tabs .ot.on", "pseudo": "::after", "backgroundColor": "rgb(26, 173, 124)", "width": "19px"}
 *     ]
 *   }
 * ]
 * style 的键 = 计算样式属性名（驼峰或 CSS 名皆可）；值 = 期望串。
 * px 数值允许 ±1.5px 误差；颜色按 rgb 串精确比对。
 *
 * 退出码：0 = 全部通过；1 = 有断言失败；2 = 参数错误。
 */
const fs = require('fs');
const path = require('path');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return (i >= 0 && process.argv[i + 1]) ? process.argv[i + 1] : def;
}

const src = arg('src');
const checksFile = arg('checks');
const vp = (arg('viewport', '414x900')).split('x').map(Number);
if (!src || !checksFile) {
  console.error('用法: node check_layout.js --src <原型.html> --checks <checks.json> [--viewport 414x900]');
  process.exit(2);
}
if (!fs.existsSync(src)) { console.error('原型不存在: ' + src); process.exit(2); }
if (!fs.existsSync(checksFile)) { console.error('checks.json 不存在: ' + checksFile); process.exit(2); }

let checks;
try { checks = JSON.parse(fs.readFileSync(checksFile, 'utf8')); }
catch (e) { console.error('checks.json 解析失败: ' + e.message); process.exit(2); }
if (!Array.isArray(checks)) { console.error('checks.json 必须是数组'); process.exit(2); }

const PX_TOL = 1.5;

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: vp[0], height: vp[1] }, deviceScaleFactor: 1 });
  const jserr = [];
  page.on('pageerror', e => jserr.push(String(e)));
  await page.goto('file:///' + path.resolve(src).replace(/\\/g, '/'));
  await page.waitForTimeout(250);

  let pass = 0, fail = 0;
  for (const c of checks) {
    const label = c.name || '(未命名场景)';
    const issues = [];
    try {
      if (c.setup) { await page.evaluate(c.setup); await page.waitForTimeout(150); }

      // --- noOverflow ---
      for (const sel of (c.noOverflow || [])) {
        const r = await page.evaluate(s => {
          const el = document.querySelector(s);
          if (!el) return null;
          return { sw: el.scrollWidth, cw: el.clientWidth };
        }, sel);
        if (!r) { issues.push(`noOverflow: 选择器无匹配 ${sel}`); continue; }
        if (r.sw > r.cw + 1) {
          // 找出被挤出的子项，便于定位
          const out = await page.evaluate(s => {
            const box = document.querySelector(s).getBoundingClientRect();
            return [...document.querySelector(s).children]
              .map(el => ({ t: el.textContent.trim().slice(0, 8), right: Math.round(el.getBoundingClientRect().right) }))
              .filter(o => o.right > box.right + 0.5);
          }, sel);
          issues.push(`noOverflow: ${sel} 横向溢出 ${r.sw - r.cw}px（scrollW=${r.sw} > clientW=${r.cw}）` +
            (out.length ? `；被挤出: ${out.map(o => o.t + '@' + o.right).join(', ')}` : ''));
        }
      }

      // --- inView ---
      for (const sel of (c.inView || [])) {
        const r = await page.evaluate(s => {
          const el = document.querySelector(s);
          if (!el) return null;
          const box = el.getBoundingClientRect();
          // 最近的可横向裁剪祖先
          let host = el.parentElement, hostBox = null;
          while (host) {
            const ox = getComputedStyle(host).overflowX;
            if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') { hostBox = host.getBoundingClientRect(); break; }
            host = host.parentElement;
          }
          if (!hostBox) hostBox = { left: 0, right: document.documentElement.clientWidth };
          return { left: box.left, right: box.right, hl: hostBox.left, hr: hostBox.right };
        }, sel);
        if (!r) { issues.push(`inView: 选择器无匹配 ${sel}`); continue; }
        if (r.right > r.hr + 0.5) {
          issues.push(`inView: ${sel} 右缘 ${Math.round(r.right)} 超出容器 ${Math.round(r.hr)}（被挤出可视区）`);
        }
      }

      // --- style ---
      for (const st of (c.style || [])) {
        const sel = st.sel, pseudo = st.pseudo || null;
        const want = Object.assign({}, st);
        delete want.sel; delete want.pseudo;
        const got = await page.evaluate(([s, p, keys]) => {
          const el = document.querySelector(s);
          if (!el) return null;
          const cs = getComputedStyle(el, p || undefined);
          const o = {};
          for (const k of keys) {
            const prop = k.replace(/[A-Z]/g, m => '-' + m.toLowerCase());
            o[k] = cs.getPropertyValue(prop) || cs[k];
          }
          return o;
        }, [sel, pseudo, Object.keys(want)]);
        if (!got) { issues.push(`style: 选择器无匹配 ${sel}`); continue; }
        for (const [k, exp] of Object.entries(want)) {
          const act = (got[k] || '').trim();
          const isPx = /^-?[\d.]+px$/.test(String(exp).trim()) && /^-?[\d.]+px$/.test(act);
          const ok = isPx
            ? Math.abs(parseFloat(act) - parseFloat(exp)) <= PX_TOL
            : act === String(exp).trim();
          if (!ok) {
            issues.push(`style: ${sel}${pseudo || ''} ${k} 期望「${exp}」实际「${act}」`);
          }
        }
      }
    } catch (e) {
      issues.push('执行异常: ' + e.message);
    }

    if (issues.length === 0) { pass++; console.log(`  ✓ ${label}`); }
    else {
      fail++;
      console.log(`  ✗ ${label}`);
      issues.forEach(m => console.log(`      - ${m}`));
    }
  }

  if (jserr.length) { fail++; console.log(`  ✗ JS 运行期错误: ${jserr.join(' | ')}`); }

  await browser.close();
  console.log(`\n=== 结果: ${pass} 通过 / ${fail} 失败 ===`);
  if (fail === 0) { console.log('✅ 布局/选中态门禁通过'); process.exit(0); }
  console.log('❌ 布局/选中态门禁未通过，禁止交付'); process.exit(1);
})();
