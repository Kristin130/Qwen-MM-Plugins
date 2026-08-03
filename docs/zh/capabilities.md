# 能力与工具

[English](../en/capabilities.md) · **中文**

Qwen-MM-Plugins 提供六个能力,各自单独安装(见 [安装](../../README.zh.md#-安装))。本页列出每个能力提供的内容。

- [🖼 core —— 视觉](#-core--视觉)
- [🎬 video-memory —— 长视频记忆](#-video-memory--长视频记忆)
- [✂️ video-edit —— 剪辑 + 生成](#-video-edit--剪辑--生成)
- [🧊 blender —— 三维建模](#-blender--三维建模)
- [📐 freecad —— 参数化 CAD](#-freecad--参数化-cad)
- [🎓 edu-agent —— 讲题视频](#-edu-agent--讲题视频)

---

## 🖼 core —— 视觉

基础多模态读取 + 分析。安装名 / 入口:`qwen-mm-plugins-core`。

**读取(内容直接喂给模型)**
- `read_image` —— 动态分辨率读取图片,对齐模型 patch 网格
- `read_video` —— 提取视频帧,自动 FPS / 分辨率
- `visualize` —— 通用文件可视化:PDF / Office / CSV / 代码 / SVG / DrawIO / 3D / GIS / Notebook / LaTeX

**多模态 API(DashScope)**
- `vision_chat` —— 视觉对话,支持图片 / 视频输入
- `ocr` —— 图片文字识别
- `grounding` —— 目标检测定位,返回像素 bbox(可配合 `draw_bbox` 画框)
- `segmentation` —— 文本提示分割(SAM3)
- `transcribe_audio` —— 语音识别(ASR),输出 SRT / 文本 / JSON

**图像 / 帧产出(存成文件 + 预览)**
- `crop` —— 按框裁剪图片
- `draw_bbox` —— 在图片上画标注框
- `save_view` —— 把文档页 / 视频帧抽成独立图片文件

**联网(Serper)**
- `web_search` —— 联网搜索,返回标题 / 摘要 / URL
- `web_extractor` —— 抓取网页正文,可摘要
- `image_search` —— 以图搜图(反向图像搜索)

Key:多模态 API 需要 `DASHSCOPE_API_KEY`;联网工具需要 `SERPER_API_KEY`;原生读图/视频/文档不需要 key。详见 [依赖](../../README.zh.md#-依赖)。精确 schema 见该能力的 `SKILL.md` 或各工具的 inputSchema。

---

## 🎬 video-memory —— 长视频记忆

面向超长视频(30 分钟以上)问答的层次化图记忆。安装名 / 入口:`qwen-mm-plugins-video-memory`。

用法是工作流式的:在 harness 里用 `@/path/to/video.mp4 <问题>` 提问。首次提问时插件会在视频旁构建一棵 4 层图(Root → SuperEvent → MacroEvent → Subgraph)+ embedding 索引,之后用下面这组查询工具回答(逐层下钻):

- `get_summary` —— 视频级根摘要(标题、主题、关键实体、情感基调)
- `get_super_events` —— 列出高层叙事弧(super event)
- `get_macro_events` —— 列出 macro event(可限定某个 super event 内)
- `get_subgraph` —— 下钻到某个 macro event 的详细子图(实体 / 事件 / 边 / 屏幕文字)
- `search_nodes` —— 按 embedding 相似度对实体与事件节点做语义检索
- `enumerate_events` —— 按时间顺序枚举所有匹配的事件实例(专为计数 / "出现多少次"类问题设计)
- `search_ocr_text` —— 仅对屏幕文字(OCR)节点做语义检索
- `search_asr_text` —— 对语音转写(ASR)节点做语义检索
- `search_by_time` —— 查找覆盖某时间区间的 macro event

📖 完整手册(安装、环境变量、示例):[video-memory-usage.md](video-memory-usage.md)。

---

## ✂️ video-edit —— 剪辑 + 生成

视频剪辑 skill + DashScope 生成工具。安装名 / 入口:`qwen-mm-plugins-video-edit`。

**生成工具(DashScope)**
- `qwen_image` —— 图片生成、编辑与翻译(Qwen-Image)
- `qwen_tts` —— 文本转语音(Qwen3-TTS-Flash)
- `wan_s2v` —— 数字人口型视频(Wan2.2-S2V)
- `wan_t2v` —— 文本生成视频(万相,wan2.7 系列)
- `happyhorse` —— 视频生成与编辑(HappyHorse)

**剪辑 skill** —— 剪辑侧由能力下的 [`skill/`](../../src/capabilities/video-edit/skill/) 驱动:`workflows/`(端到端配方)、`engines/`(渲染引擎选择矩阵)、`mcps/`(外部服务目录),以及 `craft/`、`looks/`、`review/`(技法、风格、质检参考)。

Key:生成工具需要 `DASHSCOPE_API_KEY`。

---

## 🧊 blender —— 三维建模

通过 socket 驱动一个**正在运行**的 Blender(三维建模 / 材质 / 灯光 / 渲染)。安装名 / 入口:`qwen-mm-plugins-blender`。

瘦客户端:工具连接到一台装好随包 blender-mcp addon 的实时 Blender。`QWEN_MM_AUTOLAUNCH=1`(插件清单里默认预设)会在第一次工具调用时把 Blender 拉起来,Linux-x86_64 上缺应用时自动下载;否则用 `qwen-mm-plugins-blender --launch-app` 启动。

**场景与代码**
- `execute_blender_code` —— 在 Blender 里执行任意 Python(主力工具)
- `get_scene_info` —— 汇总当前场景
- `get_object_info` —— 查看单个对象
- `get_viewport_screenshot` —— 截取视口

**PolyHaven 素材**
- `get_polyhaven_status`、`get_polyhaven_categories`、`search_polyhaven_assets`、`download_polyhaven_asset`、`set_texture`

**Sketchfab 模型**
- `get_sketchfab_status`、`search_sketchfab_models`、`get_sketchfab_model_preview`、`download_sketchfab_model`

**Hyper3D / Rodin 生成**
- `get_hyper3d_status`、`generate_hyper3d_model_via_text`、`generate_hyper3d_model_via_images`、`poll_rodin_job_status`、`import_generated_asset`

**Hunyuan3D 生成**
- `get_hunyuan3d_status`、`generate_hunyuan3d_model`、`poll_hunyuan_job_status`、`import_generated_asset_hunyuan`

驱动 Blender 本身不需要 API key(部分素材/生成后端在 Blender 内单独配置各自的 key)。📖 完整手册(安装、`--launch-app`、环境变量、排障):[blender-freecad-usage.md](blender-freecad-usage.md)。

---

## 📐 freecad —— 参数化 CAD

驱动一个**正在运行**的 FreeCAD(参数化建模、改属性、STEP/STL 导入导出、FEM)。安装名 / 入口:`qwen-mm-plugins-freecad`。

瘦客户端:工具通过 XML-RPC 连接到一台装好随包 FreeCADMCP addon 的实时 FreeCAD。`QWEN_MM_AUTOLAUNCH=1`(插件清单里默认预设)会在第一次工具调用时把 FreeCAD 拉起来,Linux-x86_64 上缺应用时自动下载;否则用 `qwen-mm-plugins-freecad --launch-app` 启动。

**文档**
- `create_document`、`list_documents`、`reload_document`

**对象**
- `create_object`、`edit_object`、`delete_object`、`get_object`、`get_objects`

**零件库**
- `get_parts_list`、`insert_part_from_library`

**视图与代码**
- `get_view` —— 按标准视角截图
- `execute_code`、`execute_code_async` —— 在 FreeCAD 里执行 Python

**FEM**
- `run_fem_analysis` —— 运行有限元分析(需要 CalculiX)

驱动 FreeCAD 本身不需要 API key。📖 完整手册(安装、`--launch-app`、环境变量、排障):[blender-freecad-usage.md](blender-freecad-usage.md)。

---

## 🎓 edu-agent —— 讲题视频

把一道数学 / 理科题(或题目图片)变成一步步讲解的中文**视频**或交互页面。安装名:`qwen-mm-plugins-edu-agent`。**纯 skill** —— 没有 MCP server。

纯 Agent Skill:模型自己脚手架、渲染并配音(用 `npx hyperframes` + Qwen-TTS)。因为没有 MCP server,`uvx` 不会替它装任何东西,运行时依赖(Node.js ≥18、hyperframes CLI、`dashscope`/`soundfile`/`numpy`/`requests`、ffmpeg、`DASHSCOPE_API_KEY`)需自己备齐。

📖 完整环境准备(依赖表、网络边界、前置条件):[installation.md](installation.md)。
