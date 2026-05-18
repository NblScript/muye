from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path("/mnt/c/shuangdian/05-1 作品信息概要表（人工智能实践赛、挑战赛，2026版）模板.docx")
OUTPUT = ROOT / "2026002224-作品信息概要表.docx"
README_OUTPUT = ROOT / "2026002224-03设计与开发文档-readme.txt"


def set_run_font(run, size: float = 9.5, bold: bool = False) -> None:
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    run.font.size = Pt(size)
    run.font.bold = bold


def set_cell_text(cell, text: str, *, size: float = 9.5, bold: bool = False, align=None) -> None:
    cell.text = ""
    parts = text.split("\n")
    paragraph = cell.paragraphs[0]
    paragraph.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.LEFT
    for index, part in enumerate(parts):
        if index:
            paragraph = cell.add_paragraph()
            paragraph.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.LEFT
        run = paragraph.add_run(part)
        set_run_font(run, size=size, bold=bold)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def style_document(document: Document) -> None:
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            set_run_font(run, 10.5)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        set_run_font(run, 9.5)


def fill_basic_info(table) -> None:
    set_cell_text(table.cell(0, 3), "2026002224", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_cell_text(table.cell(0, 10), "牧野智农——智能农业害虫防治系统", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    set_cell_text(table.cell(1, 12), "■实践赛  □挑战赛", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

    intro = (
        "作品简介(100字以内)：\n"
        "牧野智农面向大田植保场景，集成 YOLO 害虫识别、天气融合、Qwen+RAG 决策、PX4 仿真执行和 React 指挥大屏，形成从虫情感知到无人机作业展示的闭环系统。"
    )
    innovation = (
        "创新描述（100字以内）：\n"
        "把识别、天气、知识增强决策、航线规划和 PX4 本地航线执行贯通；AI 负责农事建议，规则规划器负责飞行参数，兼顾智能性、安全性和演示稳定性。"
    )
    special = (
        "特别说明（100字以内）：\n"
        "地图为前端 SVG 虚拟农田示意，不接入真实地图底图。使用 OpenAI ChatGPT/Codex 辅助代码分析、文档草稿和调试建议，内容经团队核验，核心设计与实现由团队完成。"
    )
    set_cell_text(table.cell(2, 0), intro, size=9)
    set_cell_text(table.cell(3, 0), innovation, size=9)
    set_cell_text(table.cell(4, 0), special, size=9)


def fill_authors(table) -> None:
    # 参赛成员姓名和分工比例需要以最终报名信息为准，这里只保留待补充占位。
    author_headers = ["待补充1", "待补充2", "待补充3", "待补充4", "待补充5"]
    for col, name in zip([2, 6, 9, 11, 14], author_headers):
        set_cell_text(table.cell(6, col), name, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

    for row in range(7, 14):
        for col in [2, 6, 9, 11, 14]:
            set_cell_text(table.cell(row, col), "待补充", align=WD_ALIGN_PARAGRAPH.CENTER)

    teacher_roles = (
        "■项目创意  ■理论指导  ■技术方案  □实验场地  □硬件资源\n"
        "□数据提供  □后勤支持  ■宣讲通知  ■组织协调  □经费支持\n"
        "□其他：答辩材料修改建议"
    )
    set_cell_text(table.cell(14, 5), teacher_roles, size=9)


def fill_platforms(table) -> None:
    set_cell_text(table.cell(15, 4), "■Windows  ■Linux  □macOS  ■其他：WSL/Ubuntu、PX4/Gazebo 仿真环境", size=9)
    set_cell_text(table.cell(16, 4), "■Windows  ■Linux  □macOS  □iOS  □Android  ■其他：Chrome/Edge 浏览器、PX4 SITL/Gazebo", size=9)
    tools = (
        "Python 3.11、FastAPI、React/Vite/TypeScript、YOLO、SQLite、ChromaDB、MAVSDK、PX4 SITL、Gazebo；\n"
        "后台大语言模型：通义千问（Qwen，DashScope）；文本向量模型：text-embedding-v3。"
    )
    set_cell_text(table.cell(17, 4), tools, size=8.8)
    refs = (
        "1、PX4 与 MAVSDK 官方文档\n"
        "2、FastAPI、React、Vite 官方文档\n"
        "3、Ultralytics YOLO、ChromaDB、DashScope、和风天气开发文档"
    )
    set_cell_text(table.cell(18, 4), refs, size=8.8)
    submits = "■报告文档  ■演示视频  ■PPT  ■源代码  ■部署文件  ■数据集  ■模型\n■其他：readme.txt、运行说明、配置说明"
    set_cell_text(table.cell(19, 4), submits, size=9)


def fill_related_files(table) -> None:
    rows = [
        (
            "文件：2026002224-作品信息概要表.docx\n描述：作品基础信息、简介、创新点、开发平台、提交内容及相关文件说明。",
            "■已上传到网盘\n□未上传，下载地址：随参赛总文件夹提交",
            "■自制  □未知版权\n□开源  □授权方：",
        ),
        (
            "文件：2026002224-作品报告.docx\n描述：项目背景、需求分析、技术方案、系统实现、测试分析和作品总结。",
            "■已上传到网盘\n□未上传，下载地址：随参赛总文件夹提交",
            "■自制  □未知版权\n□开源  □授权方：",
        ),
        (
            "文件：muye 项目源码\n描述：FastAPI 后端、YOLO 接口、RAG 决策、PX4 仿真、React 前端、测试与部署脚本。",
            "■已上传到网盘\n□未上传，下载地址：随参赛总文件夹提交",
            "■自制  □未知版权\n■开源组件  授权方：见依赖许可证",
        ),
        (
            "文件：data/samples 与 data/seeds\n描述：演示图片、农业种子数据、农药目录、地块和作物周期等测试数据。",
            "■已上传到网盘\n□未上传，下载地址：随参赛总文件夹提交",
            "■自制整理  □未知版权\n□开源  □授权方：",
        ),
        (
            "文件：YOLO 检测模型与配置\n描述：害虫检测模型权重、类别配置和本地推理服务配置。",
            "■已上传到网盘\n□未上传，下载地址：随参赛总文件夹提交",
            "■自制/训练  □未知版权\n■开源框架  授权方：Ultralytics YOLO",
        ),
        (
            "文件：readme.txt\n描述：说明本文件夹用途，并逐项说明设计与开发文档目录中的文件。",
            "■已上传到网盘\n□未上传，下载地址：随参赛总文件夹提交",
            "■自制  □未知版权\n□开源  □授权方：",
        ),
    ]
    for row_index, (desc, status, copyright_status) in enumerate(rows, start=22):
        set_cell_text(table.cell(row_index, 1), desc, size=8.5)
        set_cell_text(table.cell(row_index, 8), status, size=8.5)
        set_cell_text(table.cell(row_index, 13), copyright_status, size=8.5)


def write_readme() -> None:
    content = """2026002224-03设计与开发文档

本文件夹作用：
用于存放“牧野智农——智能农业害虫防治系统”的设计、开发、说明类文档，供大赛评审了解作品的总体方案、技术路线、实现过程、测试情况和相关文件信息。

文件说明：
1. 2026002224-作品报告.docx
   基于人工智能实践赛作品报告模板编写，内容包括作品概述、问题分析、解决思路、技术方案、系统实现、测试分析、作品总结、创新点、应用推广和参考资料。

2. 2026002224-作品信息概要表.docx
   基于人工智能实践赛/挑战赛作品信息概要表模板填写，内容包括作品编号、作品名称、作品简介、创新描述、开发制作平台、运行展示平台、开发工具、提交内容和相关文件说明。

3. 中国大学生计算机设计大赛AI工具使用说明.pdf
   大赛相关说明文档，用于核对人工智能工具使用、参赛材料填写和提交规范。

4. readme.txt
   本说明文件，简要说明当前文件夹作用，并对文件夹内各文件进行描述。
"""
    README_OUTPUT.write_text(content, encoding="utf-8")


def main() -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(TEMPLATE)
    document = Document(TEMPLATE)
    style_document(document)
    table = document.tables[0]
    fill_basic_info(table)
    fill_authors(table)
    fill_platforms(table)
    fill_related_files(table)
    document.save(OUTPUT)
    write_readme()
    print(OUTPUT)
    print(README_OUTPUT)


if __name__ == "__main__":
    main()
