/**
 * regen_prd_shots.js — 需求调整后按真实原型重截 PRD 截图（固化模板）
 *
 * 用法一（单原型，兼容旧版）:
 *   NODE_PATH="<managed node_modules>" node regen_prd_shots.js \
 *     --proto "<原型.html 绝对路径>" \
 *     --map '[{"go":"go('send')","sel":"#viewSend","out":"x.png"}, ...]'
 *
 * 用法二（多原型 / Tab / 弹窗 / 侧栏隐藏，推荐复杂场景）:
 *   NODE_PATH="<managed node_modules>" node regen_prd_shots.js \
 *     --manifest "<manifest.json 绝对路径>"
 *
 * manifest 结构（按 file 分组，每组复用同一 page）:
 * [
 *   {
 *     "file": "<原型.html 绝对路径>",
 *     "entries": [
 *       {
 *         "out": "<输出 png 绝对路径>",
 *         "sel": "<截图容器 CSS 选择器>",
 *         "go": "list",                 // 可选：go() 参数或完整表达式（如 "go('send')" / "go('board')"）
 *         "steps": ["viewCoupon(1)"],  // 可选：go 之后额外执行的 JS（填充数据 / 开弹窗等）
 *         "tabClick": ".tab-item[onclick*=\"couponDetail\"]", // 可选：点击某元素（如切 Tab）
 *         "hideSidebar": true          // 可选：截图前隐藏 .side/.sidebar/nav 侧栏
 *       }
 *     ]
 *   }
 * ]
 *
 * 踩坑固化（2026-08-08 / 2026-08-10 实际验证）:
 *   1) NODE_PATH 必须指向 managed workspace 的 node_modules（playwright 装在那）
 *   2) file:// 路径含中文必须 encodeURI，否则页面加载失败
 *   3) chromium 在无沙箱环境需 args:['--no-sandbox']
 *   4) 用 locator(sel).screenshot() 只截容器元素（不含侧栏），更贴近"页面截图"
 *   5) go(expr) 后 waitForTimeout(400) 等渲染/JS 状态生效
 *   6) 多原型场景、Tab 切换、弹窗打开需用 --manifest 分步骤表达，单 --map 无法覆盖
 */
const pw = require(require('path').join(
  process.env.NODE_PATH || 'C:/Users/13364/.workbuddy/binaries/node/workspace/node_modules',
  'playwright'
));
const fs = require('fs');

function parseArgs(argv) {
  const a = { proto: null, map: null, manifest: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--proto') a.proto = argv[++i];
    else if (argv[i] === '--map') a.map = JSON.parse(argv[++i]);
    else if (argv[i] === '--manifest') a.manifest = argv[++i];
  }
  return a;
}

function toGroups(args) {
  if (args.manifest) {
    return JSON.parse(fs.readFileSync(args.manifest, 'utf-8'));
  }
  if (args.proto && args.map) {
    return [{ file: args.proto, entries: args.map }];
  }
  return null;
}

function buildGoCode(go) {
  if (typeof go !== 'string') return go;
  const trimmed = go.trim();
  // 如果已是完整表达式（含 ( 或 ; 或 =），直接执行
  if (/[();=]/.test(trimmed)) return trimmed;
  // 否则当作 go() 的参数
  return 'go(' + JSON.stringify(trimmed) + ')';
}

(async () => {
  const args = parseArgs(process.argv.slice(2));
  const groups = toGroups(args);
  if (!groups) {
    console.error('用法: node regen_prd_shots.js --proto <原型.html> --map \'[...]\'');
    console.error('   或: node regen_prd_shots.js --manifest <manifest.json>');
    process.exit(2);
  }

  const browser = await pw.chromium.launch({ args: ['--no-sandbox'] });

  for (const g of groups) {
    const fileUrl = 'file:///' + encodeURI(g.file.replace(/\\/g, '/')).replace(/#/g, '%23');
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await page.goto(fileUrl, { waitUntil: 'networkidle' });

    for (const e of g.entries) {
      try {
        if (e.hideSidebar) {
          await page.evaluate(() => {
            ['.side', '.sidebar', 'nav', '#sidebar', '[class*="sidebar"]', '[class*="side-nav"]']
              .forEach(s => document.querySelectorAll(s).forEach(el => el.style.display = 'none'));
            document.body.style.background = '#ffffff';
          });
          await page.waitForTimeout(150);
        }
        if (e.go) {
          const code = buildGoCode(e.go);
          await page.evaluate((c) => { (0, eval)(c); }, code);
          await page.waitForTimeout(450);
        }
        if (e.steps) {
          for (const s of e.steps) {
            await page.evaluate((code) => { (0, eval)(code); }, s);
            await page.waitForTimeout(450);
          }
        }
        if (e.tabClick) {
          await page.evaluate((sel) => { const el = document.querySelector(sel); if (el) el.click(); }, e.tabClick);
          await page.waitForTimeout(450);
        }
        await page.locator(e.sel).screenshot({ path: e.out });
        console.log('shot ok:', e.out);
      } catch (err) {
        console.error('FAIL', e.out, '->', err && err.message);
      }
    }

    await page.close();
  }

  await browser.close();
  console.log('ALL DONE');
})().catch(e => { console.error('ERR', e && e.message); process.exit(1); });
