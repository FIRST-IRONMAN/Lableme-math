# Lableme-math
一、labelme 是一个用 Python 编写的图形化图像标注工具，灵感来自 MIT 的  ，使用 Qt 构建界面。它是应用程序而非库——v7 明确不对外暴露稳定的 Python API，所有内部模块已私有化（_ 前缀）。 当前版本：7.0.4（主线，Unreleased 在开发中） 许可证：GPL-3.0-only 作者：Kentaro Wada 官网：labelme.io（提供免 Python/Qt 的独立可执行版）

二、平台与版本策略

支持（v7.x）  维护（v6.3.x）

Python  3.12 – 3.14  3.10 – 3.11
Qt  Qt6 (PySide6)  Qt5
OS  64 位 macOS / Windows / Linux  旧系统

遵循 SPEC 0 决定 Python 版本下限，与 numpy/scipy/scikit-image 步调一致
v6.3.x 仅接收关键修复（安全漏洞、数据丢失、安装/启动破损），所有新功能都在 v7.x

v6 → v7 的 Breaking Changes：
Qt 绑定 PyQt5 → PySide6
Python 最低 3.10 → 3.12
内部模块全部私有化（labelme.app/labelme.utils 等导入失效）

---

三、核心功能

标注能力
多边形、矩形、圆形、直线、点、折线（linestrip）、掩码（mask）、有向矩形
图像级 Flag 标注（分类/清洗）
视频标注
Shape 分组（group_id）、实例分割

AI 能力
AI Assist：SAM / SAM2 / SAM3 / EfficientSAM 交互式点/框提示标注
AI Text Prompt：YOLO-World / SAM3 开放词表文生标注
统一抽象层 osam，支持多模型切换

导出与集成
VOC 格式（语义/实例分割）
COCO 格式（实例分割）

GUI 定制
预定义标签/Flag、自动保存、标签校验、快捷键自定义
20 种语言（英日韩中德法西等）

本项目定制扩展（从 5.3.1 迁移）
LaTeX/KaTeX 公式渲染（离线字体内嵌）
Description 文本描述面板（双击编辑 + 双向联动）
Canvas 描述文字叠加（随缩放自适应）
外部编辑器集成（如 Pinta，可配置）

---

四、技术栈

分类  技术

语言  Python ≥3.12（全面类型标注）
GUI  PySide6 ≥6.8
构建  hatchling + hatch-vcs（PEP 621）
包管理  uv（含 uv.lock）
AI  onnxruntime + osam
科学计算  numpy、scipy、scikit-image、matplotlib
图像  pillow、imgviz、tifffile（多光谱 TIFF）
配置  ruamel.yaml（保留注释）
日志  loguru（文件轮转 + Qt 日志桥接）
代码质量  ruff、ty、taplo、mdformat、yamlfix、typos
测试  pytest + pytest-qt + xdist + cov

---

五、架构特点

labelme/
├── _app.py          主窗口编排（3101 行）
├── _shape.py        Shape 数据模型（纯 dataclass，numpy，无 Qt）
├── _label_file.py   标注文件读写（函数式）
├── _automation/     AI 抽象层（osam 统一接口）
├── _config/         Schema 驱动配置 + 默认 YAML
├── _utils/          Qt-free 工具
├── _widgets/        UI 组件（21 个模块，含 katex 资源）
└── translate/       20 种语言

设计原则：
私有化——_ 前缀，无公开 API，只承诺 CLI + JSON 格式
数据与渲染分离——Shape 不依赖 Qt，渲染集中在 _shape_render.py
组件化——每个 UI 部件独立模块，通过 Signal 通信
可测试、可维护——完善测试 + ADR 文档 + 严格 lint

---
