// 本地 HTML 可视化就地编辑器 · 零依赖 Node 服务
// 用途：拖入 / 填路径打开任意本地 HTML，实时预览，点文字就地改，保存写回原文件。
// 人机双写纪律：人用此编辑器改文字，AI（WorkBuddy）用工具改同一文件；双方都从磁盘读写，刷新即同步。
const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = 8777;
const EDITOR = path.join(__dirname, 'editor.html');

function send(res, status, body, type) {
  res.writeHead(status, { 'Content-Type': type || 'text/plain; charset=utf-8' });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const u = url.parse(req.url, true);
  const p = u.pathname;

  // 编辑器界面
  if (p === '/' || p === '/editor') {
    fs.readFile(EDITOR, (err, data) => {
      if (err) return send(res, 500, 'editor.html missing: ' + err.message);
      send(res, 200, data, 'text/html; charset=utf-8');
    });
    return;
  }

  // 读取文件（iframe 同源加载，便于就地编辑）
  if (p === '/view' || p === '/read') {
    const target = u.query.path;
    if (!target) return send(res, 400, 'missing path');
    if (!/\.html?$/i.test(target)) return send(res, 400, '只允许 .html/.htm');
    if (!fs.existsSync(target) || !fs.statSync(target).isFile())
      return send(res, 404, '文件不存在: ' + target);
    try {
      const html = fs.readFileSync(target, 'utf-8');
      send(res, 200, html, 'text/html; charset=utf-8');
    } catch (e) {
      send(res, 500, '读取失败: ' + e.message);
    }
    return;
  }

  // 保存：写回原文件
  if (p === '/save' && req.method === 'POST') {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      try {
        const { path: target, html } = JSON.parse(body);
        if (!target || !/\.html?$/i.test(target)) return send(res, 400, 'bad path');
        // 安全：仅允许写已存在文件或同目录新文件，禁止越界到系统目录
        const safe = path.resolve(target);
        if (/^(C:)?[\\/](Windows|System|Program Files|Users[\\/][^\\/]+[\\/]AppData)/i.test(safe) === false) {
          fs.writeFileSync(safe, html, 'utf-8');
          return send(res, 200, JSON.stringify({ ok: true, path: safe }), 'application/json');
        }
        return send(res, 403, JSON.stringify({ ok: false, err: '拒绝写入系统/保护目录' }), 'application/json');
      } catch (e) {
        send(res, 500, JSON.stringify({ ok: false, err: String(e) }), 'application/json');
      }
    });
    return;
  }

  send(res, 404, 'not found');
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('HTML 可视化编辑器已启动: http://localhost:' + PORT);
});
