# UEFI Reader Tool

基于 [MSMTools/UEFIReader](https://github.com/MSMTools/UEFIReader) 设计理念，并借助 AI 辅助编程实现的一个 UEFI 固件解析工具。可以从 UEFI 映像中提取 DXE 驱动、固件卷、自由格式文件等，并自动生成符合 EDK2 规范的 `.inf`、`.dsc.inc` 和 `.inc` 文件，方便集成到其他 UEFI 项目中。

**🌐 网页端在线提取**：无需本地安装，直接上传固件即可解析，请访问 [网页版UEFIReader](https://uefireader.gzlmortal.eu.org/)

## 1. 项目背景
UEFI 固件通常以体积较大的二进制映像（FV 镜像、XBL 镜像等）形式存在，手动提取其中的驱动模块并构建可编译的工程十分繁琐。UEFIReader 能够自动解析 UEFI 固件卷（Firmware Volume）结构，识别各类文件（RAW、FREEFORM、DXE_CORE、DRIVER、APPLICATION 等），并解压 LZMA / GZip 压缩数据，最终输出：

- 提取的二进制片段（`.efi`、`.depex`、`.ui` 等）
- 自动生成的 EDK2 `.inf` 描述文件
- `DXE.dsc.inc`（所有 DXE 模块的引用列表）
- `DXE.inc`（DXE 加载顺序列表）
- `APRIORI.inc`（优先加载列表）

## 2. 功能特性
- **完整解析 UEFI 固件卷**：支持 FV 头部识别、校验和验证，递归处理嵌套卷。
- **支持多种文件类型**：RAW、FREEFORM、SECURITY_CORE、DXE_CORE、DRIVER、APPLICATION、FFS 卷等。
- **解压算法**：LZMA 与 GZip 压缩的 GUID 定义段（GUID defined section）。
- **自动生成 INF**：提取模块名、GUID、Depex、EntryPoint 等信息，生成标准 EDK2 INF。
- **输出组织结构清晰**：按路径层次存放于输出目录，直接可用于 EDK2 构建系统。
- **优先加载列表**：基于 FV 中的 `LoadPriority` 数据生成 `APRIORI.inc`。
- **纯 Python 实现**：仅依赖标准库，无需安装任何第三方包，跨平台运行。

## 3. 运行环境
- **Python**：3.7 及以上版本（推荐 3.10+）
- **依赖**：零第三方库，所有模块均来自 Python 标准库（`os`, `struct`, `uuid`, `gzip`, `lzma`, `argparse`, `pathlib`, `re` 等）

## 4. 安装与使用

### 4.1 命令行本地使用
```bash
git clone https://github.com/Mortal1063/UEFIReader.git
cd UEFIReader
python UEFIReader.py <uefi映像文件> <输出目录>
