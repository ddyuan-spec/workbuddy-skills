# workbuddy-skills

WorkBuddy 可复用 Skills 集合（user-level，跨所有项目/任务生效）。

## 已收录

### requirement-workflow
「需求输出 workflow」Skill：通用，适用于任意项目。从项目信息收集 → 需求梳理（影响范围/流程图/信息架构/状态机/脑图）→ 可交互原型 → PRD（调用 prd-structure-checker 结构检查）→ 终版存档 GitHub 的完整 10 步流程。

触发方式：对话中输入「新需求」「用需求 workflow 跑新需求」等表述即自动强制触发。

## 安装方式

把本仓库 clone 到 WorkBuddy 的 user-level skills 目录即可全局生效：

```bash
# 只取单个 skill 目录到 ~/.workbuddy/skills/ 下（推荐，避免目录嵌套）
git clone --depth 1 https://github.com/ddyuan-spec/workbuddy-skills.git _tmp
cp -r _tmp/requirement-workflow "$HOME/.workbuddy/skills/"
rm -rf _tmp
```

安装后重启 WorkBuddy（或重新加载 Skills），在任意项目对话中即可调用。

## 目录约定
- 每个 skill 一个独立文件夹，含 `SKILL.md` 与可选 `references/`、`scripts/`、`assets/`
- 不直接依赖其他 skill，互不耦合
