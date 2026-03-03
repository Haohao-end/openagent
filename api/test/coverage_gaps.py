#!/usr/bin/env python3
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _parse_args():
    parser = argparse.ArgumentParser(description="输出模块覆盖空洞清单")
    parser.add_argument("--xml", default="tmp/coverage.xml", help="coverage xml 文件路径")
    parser.add_argument("--threshold", type=float, default=80.0, help="低于该覆盖率的模块将被标记为空洞")
    parser.add_argument("--limit", type=int, default=50, help="最多输出多少个模块")
    return parser.parse_args()


def _load_rows(xml_path: Path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    rows = []
    for class_el in root.findall(".//class"):
        filename = class_el.attrib.get("filename", "")
        line_rate = float(class_el.attrib.get("line-rate", "0") or 0)
        missing_lines = []
        lines_el = class_el.find("lines")
        if lines_el is not None:
            for line_el in lines_el.findall("line"):
                if int(line_el.attrib.get("hits", "0")) == 0:
                    missing_lines.append(int(line_el.attrib.get("number", "0")))

        rows.append(
            {
                "filename": filename,
                "coverage": line_rate * 100,
                "missing_count": len(missing_lines),
                "missing_preview": ", ".join(str(line) for line in missing_lines[:10]),
            }
        )
    return rows


def main():
    args = _parse_args()
    xml_path = Path(args.xml)
    if not xml_path.exists():
        print(f"[coverage-gaps] 未找到覆盖率文件: {xml_path}")
        print("[coverage-gaps] 请先运行: pytest")
        return 1

    rows = _load_rows(xml_path)
    if not rows:
        print("[coverage-gaps] coverage.xml 中没有 class 覆盖数据")
        return 1

    rows.sort(key=lambda item: (item["coverage"], -item["missing_count"], item["filename"]))
    gaps = [item for item in rows if item["coverage"] < args.threshold][: args.limit]

    print(f"[coverage-gaps] threshold={args.threshold:.1f}% | total_modules={len(rows)}")
    if not gaps:
        print("[coverage-gaps] 未发现低于阈值的模块")
        return 0

    print("[coverage-gaps] 模块覆盖空洞清单:")
    for item in gaps:
        preview = item["missing_preview"] if item["missing_preview"] else "-"
        print(
            f"- {item['filename']}: {item['coverage']:.2f}% "
            f"(missing_lines={item['missing_count']}, sample={preview})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
