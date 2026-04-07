# Claude Code Token Usage Skill

一个 [Claude Code](https://claude.ai/code) skill，用于统计你在各项目中的 token 用量和预估费用。

支持按项目、按天、按周聚合，交互式询问统计维度，开箱即用，无硬编码。

## 效果预览

```
最近 3 周 Token 使用统计（03-17 ~ 04-07） — 按项目
==========================================================================================
  项目                       会话       总量       输入       输出      缓存读      缓存写         费用
------------------------------------------------------------------------------------------
  talent-touch               30   319.6M    50.1M   875.9K   195.1M    73.5M  $ 2359.06
    └ opus-4-6                   278.5M   $2242.53
    └ sonnet-4-6                  34.5M     $49.02
    └ haiku-4-5                    1.4M      $0.31

  exam                        7   128.0M     8.7M   686.6K    94.7M    23.9M  $  161.50
    └ sonnet-4-6                 128.0M    $161.50
==========================================================================================
  合计                        60   505.2M    67.4M     1.9M   326.3M   109.6M  $ 2709.14

注：费用按 API 标准定价估算，实际花费取决于订阅计划。
```

## 安装

将以下两个文件放到 `~/.claude/skills/token-usage/` 目录下：

```bash
mkdir -p ~/.claude/skills/token-usage
# 将 SKILL.md 和 token-usage.py 复制到该目录
```

目录结构：

```
~/.claude/skills/token-usage/
├── SKILL.md          # Skill 描述，Claude Code 自动加载
└── token-usage.py    # 统计脚本
```

## 使用方式

### 方式一：通过 Claude Code 对话触发（推荐）

在 Claude Code 中直接说：

> 看看用量 / 查一下 token 统计 / 最近花了多少

Claude 会自动识别并弹出交互式问卷，询问：
- 聚合维度（按项目 / 按天 / 按周）
- 时间范围（最近 N 天 / N 周）
- 项目范围（全部 / 指定项目）

然后自动运行并展示结果。

### 方式二：直接运行脚本

```bash
python3 ~/.claude/skills/token-usage/token-usage.py [OPTIONS]
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `--weeks N` | 最近 N 周（默认 3） | `--weeks 4` |
| `--days N` | 最近 N 天 | `--days 7` |
| `--group` | 聚合维度：`project`（默认）\| `day` \| `week` | `--group day` |
| `--project` | 只统计指定项目，支持多个、部分名称匹配 | `--project my-app` |
| `--extra-skip` | 追加路径段到跳过集合，用于校准项目名解析 | `--extra-skip work` |

**示例：**

```bash
# 最近 2 周，按项目聚合，全部项目
python3 ~/.claude/skills/token-usage/token-usage.py --weeks 2

# 最近 7 天，按天展示，只看某个项目
python3 ~/.claude/skills/token-usage/token-usage.py --days 7 --group day --project my-app

# 最近 4 周，按周聚合
python3 ~/.claude/skills/token-usage/token-usage.py --weeks 4 --group week

# 项目名解析不对时，追加需要跳过的路径段
python3 ~/.claude/skills/token-usage/token-usage.py --extra-skip work projects
```

## 费用估算说明

费用按 Anthropic API 标准定价估算（per 1M tokens）：

| 模型 | 输入 | 输出 | 缓存读 | 缓存写 |
|------|------|------|--------|--------|
| Claude Opus | $15 | $75 | $1.875 | $18.75 |
| Claude Sonnet | $3 | $15 | $0.375 | $3.75 |
| Claude Haiku | $0.80 | $4 | $0.08 | $1 |

> 如果你使用的是 Claude Max 等订阅计划，实际花费为订阅费，这里显示的是等价 API 价值。

## 注意事项

- 脚本通过 `getpass.getuser()` 动态获取当前用户名，**无硬编码**，任何人可直接使用
- 同名项目无论放在 `~/Desktop/`、`~/Downloads/` 还是其他目录，均自动合并统计
- 数据来源为 `~/.claude/projects/` 下的本地会话文件，不会上传任何数据

## 系统要求

- Python 3.6+
- [Claude Code](https://claude.ai/code) 已安装并使用过（需要本地会话数据）
