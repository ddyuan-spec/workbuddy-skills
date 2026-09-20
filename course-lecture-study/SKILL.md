---
name: course-lecture-study
description: 把本地课程视频+PDF 转成"可学习包"：抽 PDF 文字、转写视频音频为 txt、生成课程地图与每模块学习卡片(含验收题)、并批改用户自测答案。适用于用户说"学这门课/把视频转文字稿/给我划重点+验收题"且素材是本地 mp4+pdf 的场景。
---

# 课程讲义学习工作流（course-lecture-study）

当用户要学一门本地课程（桌面/目录里有一堆 mp4 + 配套 pdf），目标是"先知道内容 → 确认水平 → 一点点学"，用本流程把素材加工成可学习包。

## 触发
- "帮我学这门课 / 总结课程内容 / 把视频转成文字稿 / 给我划重点和验收题"
- 素材特征：目录下有 `*.mp4`（课程视频，常 1GB 上下）+ `*.pdf`（配套讲义）。

## 流程

### 1. 摸清目录 + 建课程地图
- `ls` 课程目录，按文件名序号/命名识别模块结构。
- 产出 `课程地图.md`：模块拆解表（阶段 / 模块 / 核心内容），便于导入钉钉做思维导图二次编辑（用户偏好：可编辑源文件 > 静态图）。

### 2. 抽 PDF 文字（讲义常是文字型，能直接抽）
- 用 managed python 3.13.12 + `pypdf`（装到隔离 venv 的 site-packages，别污染全局）：
  ```
  PY="C:/Users/13364/.workbuddy/binaries/python/versions/3.13.12/python.exe"
  TGT="C:/Users/13364/.workbuddy/binaries/python/envs/pdfread/site-packages"
  "$PY" -m pip install --quiet --target="$TGT" pypdf
  "$PY" -c "import sys; sys.path.insert(0,'$TGT'); from pypdf import PdfReader; ...extract_text()"
  ```
- 抽不到（扫描/图片型）→ 改用领域知识给划重点，并在交付物里标注"PDF 未抽成功"。

### 3. 转写视频音频为 txt（核心交付物）
- 复用 `whisper` venv：`C:/Users/13364/.workbuddy/binaries/python/envs/whisper/Lib/site-packages`（已装 faster_whisper + av/PyAV）。
- 模型：`C:/Users/13364/WorkBuddy/2026-07-10-17-28-23/models/faster-whisper-small`（CPU int8，中文置信度~1.0）。
- **关键坑（必看）**：
  - ⚠️ **直接把 mp4 传给 `WhisperModel.transcribe(path, language="zh", beam_size=5, vad_filter=True)`**，不要先抽 wav。PyAV 新版（av>=10）已**移除** `AudioFrame.reformat`，手动抽音频会 `AttributeError`。faster-whisper 内部用 PyAV 读音频轨道并自处理重采样，直接传视频即可。
  - ⚠️ **运行前必须先 `mkdir -p` 输出目录**。脚本里 `os.makedirs` 在 import 之后才跑，而 shell `> log 2>&1` 重定向在命令启动时就打开文件——目录不存在会直接失败（报 `No such file or directory`，退出码 1）。
  - 运行方式：`cd` 到工作区后 `PYTHONPATH="$ENV" "$PY" script.py > out/run.log 2>&1`，放后台 `run_in_background=true`（1GB 视频 CPU 转写约 30–50 分钟/个）。
  - 产出：每个视频一份 `.txt`（纯文字）+ `.srt`（带时间戳，方便回跳视频）。用户只要纯文字时删掉 `.srt` 和 `run.log` 保持文件夹干净。
- 输出目录建议：`工作区/AI产品课-转录/`。

### 4. 生成学习卡片 + 验收题（每模块一张）
- 结合 PDF 抽出的文字 + 视频文字稿，提炼该模块的「划重点 + 6 道验收题（概念/记忆/设计/架构/PRD指标/应用诊断）」。
- 验收题要能"检验真懂没懂"：最后一道放应用诊断题（给一段素材挑错并映射到审核/设计类别），是试金石。
- 产出 `XX-学习卡片.md`。

### 5. 批改用户自测答案
- 用户答完验收题后，逐题对照卡片判分（✓/△/✗），重点指出：
  - 理由说反/混淆的地方（如"合规最核心"的理由错写成"大模型幻觉"——幻觉其实是"真实/版权不能只靠大模型"的理由）。
  - 漏答项（如指标全对但漏"数据划分 7:2:1"）。
  - 找到问题但没按题目要求"映射到类别"（应用诊断题通病）。
- 产出 `XX-验收题订正.md` 给用户留存。

## 用户偏好（已验证）
- 结论先行、编号式反馈、表格对比；不要 AI 味文案。
- 交付偏好：可编辑 Markdown 源文件（导入钉钉做思维导图），不只给静态图。
- 学习节奏："一点点学"，每个项目 = 划重点 → 看课 → 验收题自测 → 判分 → 决定下一步。

## 判定与下一步建议
- 产品功底强（PRD/原型/规则设计）的用户：结构化题（分类法/架构/审核点）通常全对，缺口在 AI 技术侧细节（规则引擎、数据源对接、评估指标、RAG/Agent/MCP 原理）→ 下一步系统补原理。
- 技术侧弱的用户：先补"为什么真实/版权不能只靠大模型""评估指标拆解"等基础，再上项目。
