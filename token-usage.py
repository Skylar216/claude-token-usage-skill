#!/usr/bin/env python3
"""Claude Code token usage statistics across all projects."""

import getpass
import json
import os
import glob
import argparse
from datetime import datetime, timedelta
from collections import defaultdict


# 动态构建路径段跳过集合：系统固定段 + 当前用户名 + 常见挂载点
_USERNAME = getpass.getuser()
_SKIP_SEGMENTS = {"Users", "home", "Desktop", "Downloads", "Documents", _USERNAME}


def get_project_name(dirname):
    """
    从 Claude 项目目录名中提取项目名称。
    目录名格式为用连字符拼接的路径，如 -Users-alice-Desktop-my-project。
    跳过系统路径段（Users/home/Desktop/Downloads/Documents）和当前用户名，
    取剩余部分作为项目名。若解析失败则返回原始目录名。
    """
    parts = dirname.split("-")
    meaningful = []
    found_anchor = False
    for p in parts:
        if not p:
            continue
        if p in _SKIP_SEGMENTS:
            found_anchor = True
            continue
        if found_anchor:
            meaningful.append(p)
    return "-".join(meaningful) if meaningful else dirname


def fmt(n):
    """Format token count to human-readable string."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def calc_cost(model, inp, out, cr, cw):
    """Estimate cost using standard API pricing (per 1M tokens)."""
    if "opus" in model:
        return (inp * 15 + out * 75 + cr * 1.875 + cw * 18.75) / 1_000_000
    elif "sonnet" in model:
        return (inp * 3 + out * 15 + cr * 0.375 + cw * 3.75) / 1_000_000
    elif "haiku" in model:
        return (inp * 0.8 + out * 4 + cr * 0.08 + cw * 1) / 1_000_000
    return 0


def normalize_model(model):
    """Normalize model name for display."""
    return (
        model.replace("claude-", "")
        .replace("-20251001", "")
        .replace("-20250514", "")
    )


def parse_timestamp(ts):
    """Parse timestamp to datetime, supporting both ISO string and epoch ms."""
    if isinstance(ts, str) and ts:
        try:
            return datetime.fromisoformat(ts[:19])
        except Exception:
            return None
    elif isinstance(ts, (int, float)) and ts > 0:
        try:
            return datetime.fromtimestamp(ts / 1000)
        except Exception:
            return None
    return None


def week_label(dt):
    """Return ISO week label like '2026-W14'."""
    return dt.strftime("%Y-W%W")


def day_label(dt):
    """Return date label like '2026-04-07'."""
    return dt.strftime("%Y-%m-%d")


def load_records(cutoff, projects_filter=None):
    """
    Load all assistant records from ~/.claude/projects within the cutoff.
    Returns list of dicts with keys: project, model, inp, out, cr, cw, dt, sid
    """
    proj_dir = os.path.expanduser("~/.claude/projects/")
    if not os.path.isdir(proj_dir):
        return []

    records = []
    for proj in os.listdir(proj_dir):
        proj_path = os.path.join(proj_dir, proj)
        if not os.path.isdir(proj_path):
            continue

        friendly = get_project_name(proj)

        # 项目过滤：支持部分匹配
        if projects_filter:
            match = any(f.lower() in friendly.lower() for f in projects_filter)
            if not match:
                continue

        for f in glob.glob(os.path.join(proj_path, "*.jsonl")):
            with open(f) as fh:
                for line in fh:
                    try:
                        d = json.loads(line.strip())
                        if d.get("type") != "assistant":
                            continue

                        dt = parse_timestamp(d.get("timestamp", ""))
                        if dt is None or dt < cutoff:
                            continue

                        msg = d.get("message", {})
                        if not isinstance(msg, dict):
                            continue

                        usage = msg.get("usage", {})
                        model = normalize_model(msg.get("model", "unknown"))
                        sid = d.get("sessionId", "")

                        records.append({
                            "project": friendly,
                            "model": model,
                            "inp": usage.get("input_tokens", 0),
                            "out": usage.get("output_tokens", 0),
                            "cr": usage.get("cache_read_input_tokens", 0),
                            "cw": usage.get("cache_creation_input_tokens", 0),
                            "dt": dt,
                            "sid": sid,
                        })
                    except Exception:
                        pass

    return records


def aggregate(records, group_by):
    """
    Aggregate records by group_by key.
    group_by: 'project' | 'day' | 'week'
    Returns ordered list of (label, stats_dict).
    """
    stats = defaultdict(lambda: {
        "inp": 0, "out": 0, "cr": 0, "cw": 0,
        "sessions": set(), "cost": 0.0,
        "models": defaultdict(lambda: {"inp": 0, "out": 0, "cr": 0, "cw": 0}),
    })

    for r in records:
        if group_by == "project":
            key = r["project"]
        elif group_by == "day":
            key = day_label(r["dt"])
        elif group_by == "week":
            key = week_label(r["dt"])
        else:
            key = r["project"]

        s = stats[key]
        s["inp"] += r["inp"]
        s["out"] += r["out"]
        s["cr"] += r["cr"]
        s["cw"] += r["cw"]
        s["sessions"].add(r["sid"])
        s["cost"] += calc_cost(r["model"], r["inp"], r["out"], r["cr"], r["cw"])
        m = s["models"][r["model"]]
        m["inp"] += r["inp"]
        m["out"] += r["out"]
        m["cr"] += r["cr"]
        m["cw"] += r["cw"]

    # 排序：时间维度按时间升序，项目按总量降序
    if group_by in ("day", "week"):
        return sorted(stats.items(), key=lambda x: x[0])
    else:
        return sorted(stats.items(), key=lambda x: -(x[1]["inp"] + x[1]["out"] + x[1]["cr"] + x[1]["cw"]))


def print_stats(rows, group_by, time_label):
    """Print aggregated stats table."""
    print(f"\n{time_label}")

    grand = {"inp": 0, "out": 0, "cr": 0, "cw": 0, "sessions": 0, "cost": 0.0}

    # 列宽配置
    COL0 = 22  # 标签列宽（日期/周/项目名）

    if group_by == "project":
        # 按项目：原有流水格式 + 模型明细
        print("=" * 90)
        print(
            f"  {'项目':<{COL0}} {'会话':>4}  {'总量':>7}  {'输入':>7}  {'输出':>7}  {'缓存读':>7}  {'缓存写':>7}  {'费用':>9}"
        )
        print("-" * 90)
        for label, s in rows:
            total = s["inp"] + s["out"] + s["cr"] + s["cw"]
            ns = len(s["sessions"])
            grand["inp"] += s["inp"]
            grand["out"] += s["out"]
            grand["cr"] += s["cr"]
            grand["cw"] += s["cw"]
            grand["sessions"] += ns
            grand["cost"] += s["cost"]
            print(
                f"  {label:<{COL0}} {ns:>4}  {fmt(total):>7}  {fmt(s['inp']):>7}  "
                f"{fmt(s['out']):>7}  {fmt(s['cr']):>7}  {fmt(s['cw']):>7}  ${s['cost']:>8.2f}"
            )
            for m, ms in sorted(s["models"].items()):
                if m in ("<synthetic>", "unknown"):
                    continue
                mt = ms["inp"] + ms["out"] + ms["cr"] + ms["cw"]
                mc = calc_cost(m, ms["inp"], ms["out"], ms["cr"], ms["cw"])
                print(f"    └ {m:<{COL0+1}} {fmt(mt):>7}   ${mc:.2f}")
            print()
        print("=" * 90)
    else:
        # 按天/按周：带表头的表格，末尾附合计行
        label_col = "日期" if group_by == "day" else "周次"
        print("=" * 82)
        print(
            f"  {label_col:<{COL0}} {'会话':>4}  {'总量':>7}  {'输入':>7}  {'输出':>7}  {'缓存读':>7}  {'缓存写':>7}  {'费用':>9}"
        )
        print("-" * 82)
        for label, s in rows:
            total = s["inp"] + s["out"] + s["cr"] + s["cw"]
            ns = len(s["sessions"])
            grand["inp"] += s["inp"]
            grand["out"] += s["out"]
            grand["cr"] += s["cr"]
            grand["cw"] += s["cw"]
            grand["sessions"] += ns
            grand["cost"] += s["cost"]
            print(
                f"  {label:<{COL0}} {ns:>4}  {fmt(total):>7}  {fmt(s['inp']):>7}  "
                f"{fmt(s['out']):>7}  {fmt(s['cr']):>7}  {fmt(s['cw']):>7}  ${s['cost']:>8.2f}"
            )
        print("-" * 82)

    gt = grand["inp"] + grand["out"] + grand["cr"] + grand["cw"]
    width = 90 if group_by == "project" else 82
    print("=" * width)
    print(
        f"  {'合计':<{COL0}} {grand['sessions']:>4}  {fmt(gt):>7}  {fmt(grand['inp']):>7}  "
        f"{fmt(grand['out']):>7}  {fmt(grand['cr']):>7}  {fmt(grand['cw']):>7}  ${grand['cost']:>8.2f}"
    )
    print("\n注：费用按 API 标准定价估算，实际花费取决于订阅计划。")


def main():
    parser = argparse.ArgumentParser(description="Claude Code token usage statistics")
    parser.add_argument("--days", type=int, help="按天统计最近 N 天")
    parser.add_argument("--weeks", type=int, help="按周统计最近 N 周")
    parser.add_argument(
        "--group",
        choices=["project", "day", "week"],
        default="project",
        help="聚合维度：project（默认）| day | week",
    )
    parser.add_argument(
        "--project",
        nargs="*",
        help="只统计指定项目（支持部分名称匹配，可多个），不指定则统计全部",
    )
    parser.add_argument(
        "--extra-skip",
        nargs="*",
        metavar="SEGMENT",
        help="追加到路径跳过集合的段名（用于校准项目名解析，如工作区名、自定义挂载点等）",
    )
    args = parser.parse_args()

    # 用户校准：将额外的路径段加入跳过集合
    if args.extra_skip:
        _SKIP_SEGMENTS.update(args.extra_skip)

    # 确定时间范围
    if args.days:
        cutoff = datetime.now() - timedelta(days=args.days)
        time_label = f"最近 {args.days} 天 Token 使用统计（{cutoff.strftime('%m-%d')} ~ {datetime.now().strftime('%m-%d')}）"
    elif args.weeks:
        cutoff = datetime.now() - timedelta(weeks=args.weeks)
        time_label = f"最近 {args.weeks} 周 Token 使用统计（{cutoff.strftime('%m-%d')} ~ {datetime.now().strftime('%m-%d')}）"
    else:
        # 默认 3 周
        cutoff = datetime.now() - timedelta(weeks=3)
        time_label = f"最近 3 周 Token 使用统计（{cutoff.strftime('%m-%d')} ~ {datetime.now().strftime('%m-%d')}）"

    records = load_records(cutoff, projects_filter=args.project)

    if not records:
        proj_hint = f"（项目过滤: {args.project}）" if args.project else ""
        print(f"未找到符合条件的使用数据{proj_hint}。")
        return

    rows = aggregate(records, args.group)

    # 标题补充维度信息
    dim_map = {"project": "按项目", "day": "按天", "week": "按周"}
    full_label = f"{time_label} — {dim_map[args.group]}"
    if args.project:
        full_label += f"（项目: {', '.join(args.project)}）"

    print_stats(rows, args.group, full_label)


if __name__ == "__main__":
    main()
