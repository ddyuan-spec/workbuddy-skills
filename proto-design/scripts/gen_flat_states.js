#!/usr/bin/env node
/**
 * gen_flat_states.js —— 把「带交互的 HTML 原型」的每个状态抓取成「平铺静态稿」（proto-design 用）
 *
 * 与 gen_flat_modao.py 的区别：本脚本先用 playwright **真实渲染每个状态**再抓 DOM，
 * 因此 JS 动态生成的内容（商品列表、订单卡片、金额计算、弹窗回填值、空态等）都是
 * 「真实渲染后的值」，无需再手写 PATCHES 静态补值。适合 JS 渲染重的交互原型一键出平铺图。
 *
 * 用法：
 *   NODE_PATH="<含 playwright 的 node_modules>" <node> gen_flat_states.js \
 *     --src <原型.html> --out <平铺.html> --states <states.json> \
 *     [--title "标题"] [--viewport 420x900] [--design-h 812]
 *
 * states.json（数组，顺序 = 平铺顺序）：
 * [
 *   {"label":"积分商城列表"},                                             // 默认态
 *   {"label":"商品详情","setup":"go('p_detail')"},                        // setup = 在页面上下文执行的 JS
 *   {"label":"立即购买弹窗","setup":"go('p_detail');openBuy()","extras":["buyModal"]},  // extras = 追加的兄弟元素 id（如弹窗）
 *   {"label":"我的订单 · 已完成","setup":"goOrders('all');switchOrderTab('done')"},
 *   {"label":"全局 Toast 提示","setup":"go('p_mall')","toast":"虚拟商品，无需发货"}
 * ]
 *   - setup  可选，抓取前在页面里执行的 JS 字符串（内部可含引号，JSON 里记得转义）
 *   - extras 可选，要一并截入本帧的「页面之外的兄弟元素」id（典型：弹窗 modal）；按当前状态原样抓取
 *   - toast  可选，若给出则把 #toast 文本设为该值并强制显示
 *
 * 关键设计（踩坑固化，勿改）：
 *   1) 平铺手机框内页面的高度必须用 `min-height:<design-h>`（默认 812），**不能只写 height:auto**。
 *      原型的底部操作条（tabbar / cf-foot / cs-foot / det-foot）多为 position:absolute;bottom:0，
 *      交互版靠「固定视口高度」承载；若平铺时页面高度变 auto，短内容页的底部条会「压住」内容
 *      （实测事故：收银台「找朋友支付」行、确认订单「订单备注」块被底部按钮盖住）。
 *      min-height 让短页保持设计高、长页自然增长，与原交互版观感一致，且无需逐页补 padding。
 *   2) 产出为「真·无交互」：整份不含 <script>，并剥离所有 onclick / oninput。
 *   3) 顶部标注「无交互 / 静态展示」（PROTO-FLAT-004）。
 *
 * 退出码：0 = 成功；2 = 参数错误。
 */
const fs = require('fs');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return (i >= 0 && process.argv[i + 1]) ? process.argv[i + 1] : def;
}
const src = arg('src');
const out = arg('out');
const statesFile = arg('states');
const title = arg('title', '平铺图（无交互 · 静态展示）');
const designH = Number(arg('design-h', '812'));
const vp = (arg('viewport', '420x900')).split('x').map(Number);

if (!src || !out || !statesFile) {
  console.error('用法: node gen_flat_states.js --src <原型.html> --out <平铺.html> --states <states.json> [--title ..] [--viewport 420x900] [--design-h 812]');
  process.exit(2);
}
if (!fs.existsSync(src)) { console.error('原型不存在: ' + src); process.exit(2); }
if (!fs.existsSync(statesFile)) { console.error('states.json 不存在: ' + statesFile); process.exit(2); }

let states;
try { states = JSON.parse(fs.readFileSync(statesFile, 'utf8')); }
catch (e) { console.error('states.json 解析失败: ' + e.message); process.exit(2); }
if (!Array.isArray(states)) { console.error('states.json 必须是数组'); process.exit(2); }

const raw = fs.readFileSync(src, 'utf8');
const styleMatch = raw.match(/<style[^>]*>([\s\S]*?)<\/style>/i);
const styleCss = styleMatch ? styleMatch[1] : '';
const strip = (s) => String(s || '')
  .replace(/ onclick="[^"]*"/gi, '')
  .replace(/ oninput="[^"]*"/gi, '')
  .replace(/ onchange="[^"]*"/gi, '');

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: vp[0], height: vp[1] }, deviceScaleFactor: 1 });
  await page.goto('file:///' + require('path').resolve(src).replace(/\\/g, '/'));
  await page.waitForTimeout(400);

  const frames = [];
  for (const st of states) {
    if (st.setup) { await page.evaluate(st.setup); await page.waitForTimeout(250); }
    let html = await page.evaluate(() => {
      const p = document.querySelector('.phone .page.active')
             || document.querySelector('.page.active')
             || document.querySelector('.phone .page');
      return p ? p.outerHTML : '';
    });
    const parts = [html];
    for (const id of (st.extras || [])) {
      const ex = await page.evaluate((eid) => { const e = document.getElementById(eid); return e ? e.outerHTML : ''; }, id);
      if (ex) parts.push(ex); else console.error('  ! extras 未找到 #' + id);
    }
    if (st.toast) {
      const t = await page.evaluate((msg) => {
        const t = document.getElementById('toast');
        if (!t) return '';
        t.textContent = msg; t.classList.add('on'); return t.outerHTML;
      }, st.toast);
      if (t) parts.push(t); else console.error('  ! 未找到 #toast');
    }
    if (!html) console.error('  ! 未抓到 active page：' + (st.label || '') + '（setup 是否漏了跳转？）');
    frames.push({ label: st.label || '(未命名)', html: strip(parts.join('')) });
  }
  await browser.close();

  let items = '';
  for (const f of frames) {
    items += `    <div class="flat-item">\n      <div class="flat-label">${f.label}</div>\n      <div class="flat-phone">${f.html}</div>\n    </div>\n`;
  }

  const doc = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<style>
${styleCss}
/* ============ 平铺模式覆盖样式（gen_flat_states.js 生成，勿手改） ============ */
body{background:#eceef1;padding:24px}
.flat-wrap{max-width:1440px;margin:0 auto}
.flat-head{background:#fff;border-radius:14px;padding:16px 20px;margin-bottom:22px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
.flat-head h1{margin:0 0 6px;font-size:18px;color:#1a1a1a}
.flat-head p{margin:0;font-size:13px;color:#8A9099;line-height:1.6}
.flat-tag{display:inline-block;background:#FFF1E0;color:#B26A00;font-size:11px;padding:2px 9px;border-radius:4px;font-weight:600;margin-left:8px}
.flat-grid{display:flex;flex-wrap:wrap;gap:26px 24px;align-items:flex-start}
.flat-item{display:flex;flex-direction:column;align-items:center;gap:12px}
.flat-label{font-size:13px;font-weight:600;color:#333;background:#fff;padding:7px 16px;border-radius:18px;box-shadow:0 1px 5px rgba(0,0,0,.08);white-space:nowrap}
.flat-phone{position:relative;width:375px;background:#fff;border-radius:32px;box-shadow:0 12px 40px rgba(0,0,0,.15);overflow:visible;margin:0}
.flat-phone .page{position:relative;top:auto;right:auto;bottom:auto;left:auto;inset:auto;display:none;height:auto;min-height:${designH}px;overflow:visible}
.flat-phone .page.active{display:block}
.flat-phone .modal{position:absolute;inset:0}
.flat-phone .toast{position:absolute}
</style>
</head>
<body>
<div class="flat-wrap">
  <div class="flat-head">
    <h1>${title}<span class="flat-tag">无交互 / 静态展示</span></h1>
    <p>由交互原型（${require('path').basename(src)}）导出，每个页面平铺呈现，含弹窗与 Toast 提示。已剥离所有 onclick / oninput，元素不再响应点击，仅供评审、截图、墨刀导入使用。</p>
  </div>
  <div class="flat-grid">
${items}  </div>
</div>
</body>
</html>`;

  fs.writeFileSync(out, doc);
  console.log('DONE frames=' + frames.length + ' bytes=' + doc.length + ' -> ' + out);
})();
