#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse


PREFERRED_SIGNALS = [
    "clk",
    "rst_n",
    "s_axi_awvalid",
    "s_axi_awready",
    "s_axi_wvalid",
    "s_axi_wready",
    "s_axi_bvalid",
    "s_axi_bready",
    "s_axi_arvalid",
    "s_axi_arready",
    "s_axi_rvalid",
    "s_axi_rready",
    "s_axi_rlast",
    "penable",
    "pwrite",
    "pready",
    "pslverr",
]


def parse_vcd(vcd_path):
    """
    简单 VCD 解析器：
    只解析 $var 定义和 0/1/x/z/bxxx 的值变化。
    足够用于画 AutoFlow 当前 AXI/APB 关键信号。
    """
    id_to_name = {}
    current_time = 0
    values = {}

    with open(vcd_path, "r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 解析信号声明：
            # $var wire 1 " clk $end
            if line.startswith("$var"):
                parts = line.split()
                if len(parts) >= 5:
                    code = parts[3]
                    name = parts[4]
                    id_to_name[code] = name
                    values[name] = []
                continue

            # 解析时间戳
            if line.startswith("#"):
                try:
                    current_time = int(line[1:])
                except ValueError:
                    pass
                continue

            # 单 bit 变化：0! / 1!
            if line[0] in "01xzXZ":
                val = line[0]
                code = line[1:]
                if code in id_to_name:
                    name = id_to_name[code]
                    values[name].append((current_time, val))
                continue

            # 多 bit 变化：b1010 !
            if line.startswith("b"):
                parts = line.split()
                if len(parts) == 2:
                    val = parts[0][1:]
                    code = parts[1]
                    if code in id_to_name:
                        name = id_to_name[code]
                        values[name].append((current_time, val))
                continue

    return values


def logic_to_01(v):
    """
    转成 0/1 用于画波形。
    多 bit 信号只要非零，就画成 1。
    """
    v = str(v).lower()

    if v in ["0", "x", "z"]:
        return 0
    if v == "1":
        return 1

    bits = [c for c in v if c in "01"]
    if not bits:
        return 0

    return 1 if "1" in bits else 0


def select_signals(values):
    selected = []

    for sig in PREFERRED_SIGNALS:
        if sig in values:
            selected.append(sig)

    return selected


def build_wave_points(tv, end_time, x0, x_scale, y_base, amp):
    """
    生成 SVG polyline 点。
    """
    if not tv:
        return ""

    points = []

    # 如果第一条变化不在 0 时刻，补一个起点
    last_time = 0
    last_val = logic_to_01(tv[0][1])

    def xy(t, v):
        x = x0 + t * x_scale
        y = y_base - amp * v
        return x, y

    x, y = xy(0, last_val)
    points.append((x, y))

    for t, raw_v in tv:
        v = logic_to_01(raw_v)

        # 先水平走到当前时间
        x, y = xy(t, last_val)
        points.append((x, y))

        # 再垂直跳变
        x, y = xy(t, v)
        points.append((x, y))

        last_time = t
        last_val = v

    # 延伸到结束时间
    x, y = xy(end_time, last_val)
    points.append((x, y))

    return " ".join(["%.2f,%.2f" % (x, y) for x, y in points])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vcd", required=True)
    parser.add_argument("--svg", required=True)
    parser.add_argument("--title", default="Waveform")
    args = parser.parse_args()

    values = parse_vcd(args.vcd)
    selected = select_signals(values)

    if not selected:
        raise RuntimeError("没有找到可绘制的目标信号")

    end_time = 0
    for sig in selected:
        if values[sig]:
            end_time = max(end_time, values[sig][-1][0])

    if end_time <= 0:
        end_time = 1

    width = 1400
    left = 220
    top = 70
    row_h = 42
    amp = 18
    height = top + len(selected) * row_h + 60

    usable_w = width - left - 60
    x_scale = float(usable_w) / float(end_time)

    out_dir = os.path.dirname(args.svg)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    svg = []
    svg.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (width, height))
    svg.append('<rect width="100%" height="100%" fill="white"/>')
    svg.append('<text x="20" y="35" font-size="24" font-family="Arial">%s</text>' % args.title)

    # 时间轴
    svg.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="black"/>' %
               (left, height - 40, width - 40, height - 40))
    svg.append('<text x="%d" y="%d" font-size="14" font-family="Arial">time</text>' %
               (width - 90, height - 15))

    # 网格线
    grid_count = 10
    for i in range(grid_count + 1):
        x = left + i * usable_w / grid_count
        svg.append('<line x1="%.2f" y1="55" x2="%.2f" y2="%d" stroke="#eeeeee"/>' %
                   (x, x, height - 40))
        time_label = end_time * i / grid_count
        svg.append('<text x="%.2f" y="%d" font-size="11" font-family="Arial" fill="#666">%.0f</text>' %
                   (x - 10, height - 22, time_label))

    # 波形
    for idx, sig in enumerate(selected):
        y_base = top + idx * row_h + amp

        svg.append('<text x="20" y="%.2f" font-size="15" font-family="Arial">%s</text>' %
                   (y_base + 5, sig))

        svg.append('<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#dddddd"/>' %
                   (left, y_base, width - 40, y_base))

        points = build_wave_points(values[sig], end_time, left, x_scale, y_base, amp)

        svg.append('<polyline points="%s" fill="none" stroke="black" stroke-width="2"/>' % points)

    svg.append('</svg>')

    with open(args.svg, "w") as f:
        f.write("\n".join(svg))


if __name__ == "__main__":
    main()