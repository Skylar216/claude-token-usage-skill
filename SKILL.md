---
name: token-usage
description: Use when the user asks about token usage, API cost, session statistics, or wants to see how much they've used Claude Code across projects. Triggers on words like "token", "usage", "cost", "花了多少", "用量", "统计".
---

# Token Usage

Show Claude Code token usage and estimated cost across all projects.

## When to Use

- User asks about token/cost/usage statistics
- User wants to compare usage across projects
- User asks "花了多少", "用量", "统计", "cost", "token usage"

## Interaction Flow (REQUIRED)

**Before running the script, ALWAYS ask the user these three questions in one message using AskUserQuestion:**

1. **聚合维度** — 按项目 / 按天 / 按周
2. **时间范围** — 最近 N 天 / 最近 N 周（默认 3 周）
3. **项目范围** — 全部项目 / 指定项目（列出可选项）

To list available projects for the user to choose from, run:
```bash
python3 -c "
import os, getpass
skip = {'Users','home','Desktop','Downloads','Documents', getpass.getuser()}
seen = set()
for d in os.listdir(os.path.expanduser('~/.claude/projects/')):
    parts = [p for p in d.split('-') if p]
    found, name = False, []
    for p in parts:
        if p in skip: found = True; continue
        if found: name.append(p)
    n = '-'.join(name)
    if n and n not in seen:
        seen.add(n); print(n)
"
```

After collecting answers, build the command and run it.

## Command Reference

```bash
python3 ~/.claude/skills/token-usage/token-usage.py [OPTIONS]
```

| Option | Description | Example |
|--------|-------------|---------|
| `--weeks N` | 最近 N 周（默认 3） | `--weeks 4` |
| `--days N` | 最近 N 天 | `--days 7` |
| `--group` | 聚合维度：`project`（默认）\| `day` \| `week` | `--group day` |
| `--project` | 只统计指定项目，支持多个、部分匹配 | `--project talent exam` |
| `--extra-skip` | 追加路径段到跳过集合（校准项目名解析） | `--extra-skip work projects` |

**Examples:**

```bash
# 最近 2 周，按项目聚合，全部项目
python3 ~/.claude/skills/token-usage/token-usage.py --weeks 2

# 最近 7 天，按天展示，只看 talent-touch 项目
python3 ~/.claude/skills/token-usage/token-usage.py --days 7 --group day --project talent-touch

# 最近 4 周，按周聚合，看 talent 和 exam 两个项目
python3 ~/.claude/skills/token-usage/token-usage.py --weeks 4 --group week --project talent exam
```

## Output

- **按项目**：带表头的表格，每行一个项目，下方展开模型明细；底部合计行
- **按天**：带表头的表格（日期 / 会话 / 总量 / 输入 / 输出 / 缓存读 / 缓存写 / 费用），底部合计行
- **按周**：同上，标签列为 ISO 周次（如 `2026-W14`），底部合计行
- 所有模式均包含合计行和定价说明

## Notes

- 用户名和路径段**动态获取**（`getpass.getuser()`），无硬编码，任何人可直接使用
- 若项目名解析不正确，用 `--extra-skip` 追加需要跳过的路径段（如工作区名、自定义挂载点）
- 同名项目无论在 `~/Downloads/` 还是 `~/Desktop/` 下均自动合并
- 费用按 API 标准定价估算（Opus $15/$75、Sonnet $3/$15、Haiku $0.80/$4 per 1M input/output tokens）
- 实际花费取决于订阅计划
