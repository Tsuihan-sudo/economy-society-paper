# 课程论文原始数据与复现材料

本项目用于展示课程论文《城市中心生产活动的集聚阈值与上海 POI 证据》的源码、论文图、POI 数据、交互页面和最小复现代码。

## 内容

```text
paper.tex
  论文 LaTeX 源码。

figures/
  论文使用的图片。

paper_data/
  index.html
    可交互行业六维参数雷达图。
  map.html
    可交互上海 POI 地图，可勾选显示不同生产类型。
  reproduce_poi_figures.py
    复现代码：获取 POI、清洗分类、生成论文 POI 图。
  data/
    amap_poi_raw.csv
      高德地图返回的原始 POI 数据。
    poi_classification_audit.csv
      自动清洗与分类审计表，每条输入记录都有状态和分类理由。
    poi_spatial.csv
      清洗后 POI 与空间变量。
    model_parameters.csv
      理论模型行业六维参数。
    scenario_parameters.csv
      理论模型情景参数。

requirements.txt
  复现代码的运行环境。
```

## 在线页面

- `index.html` 是可交互雷达图；
- `map.html` 是可交互 POI 地图；
- `data/amap_poi_raw.csv` 是原始 POI 数据；
- `data/poi_classification_audit.csv` 是分类审计表。

## 复现教程

跟随本节内容操作，可以复现论文中使用的所有 POI 相关结果图。

复现有两种方式：

- 使用仓库中已经上传的原始数据复现。这不需要高德 Web 服务 Key，不联网，结果应与论文一致。
- 申请高德 Key 后重新采集 POI 数据。因为地图平台数据可能会随时间更新，结果不保证与论文完全相同。

### 0. 下载项目

如果熟悉 Git，可以克隆本项目：

```powershell
git clone https://github.com/Tsuihan-sudo/economy-society-paper.git
cd 项目文件夹
```

如果不熟悉 Git，也可以在 GitHub 页面点击 `Code` -> `Download ZIP`，解压后进入解压得到的文件夹。

无论使用哪种方式，后续命令都需要在“项目根目录”运行。项目根目录应当能看到这些文件和文件夹：

```text
README.md
paper.tex
requirements.txt
figures/
paper_data/
```

在终端中可以用下面的命令检查当前位置：

```powershell
dir
```

macOS 或 Linux 用户可使用：

```bash
ls
```

### 1. Python 环境

建议使用 Python 3.10 或更高版本。先检查本机是否已经安装 Python：

```powershell
python --version
```

如果提示找不到 `python`，需要先从 Python 官网安装，或使用 Anaconda/Miniconda。安装后重新打开终端再执行上面的命令。

建议创建一个独立虚拟环境，避免影响你电脑上已有的 Python 包：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 提示不允许运行 `Activate.ps1`，可以跳过激活步骤，后续把 `python` 替换为 `.\.venv\Scripts\python.exe` 即可。

如果你使用 macOS 或 Linux，对应命令是：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

然后安装本项目需要的依赖：

```powershell
python -m pip install -r requirements.txt
```

依赖只有 `pandas`、`numpy` 和 `matplotlib`。

### 2. 用已上传原始数据复现论文图

它只读取仓库中的：

```text
paper_data/data/amap_poi_raw.csv
```

然后重新执行：

```text
原始 POI 数据 -> 自动清洗分类 -> 计算空间变量 -> 生成论文 POI 图
```

在仓库根目录运行：

```powershell
python paper_data/reproduce_poi_figures.py --use-existing
```

运行成功后，程序会重新生成或覆盖以下文件：

```text
paper_data/data/poi_classification_audit.csv
paper_data/data/poi_spatial.csv
figures/poi_distance_distribution.png
figures/poi_distance_distribution_polycentric.png
figures/category_distance_comparison.png
figures/poi_scatter_map.png
figures/category_by_zone.png
figures/category_by_nearest_center_zone.png
```

其中：

- `poi_classification_audit.csv` 记录每条 POI 的清洗状态、分类结果和分类理由；
- `poi_spatial.csv` 是清洗后的 POI 数据，并包含单中心距离、多中心距离和距离分组；
- `figures/` 中的图片是论文正文和附录使用的所有 POI 图。

如果终端输出中出现接近下面的结果，说明复现结果与论文数据一致：

```text
raw rows: 2801
clean kept: 2756
传统制造: 1072
城市型生产: 476
城市型生产到人民广场均值: 18.94 km
传统制造到人民广场均值: 28.16 km
```

### 3. 重新采集 POI 数据

若想要复现论文结果的全过程，可按本小节内容操作。由于地图平台的 POI 数据会不断更新，重新采集得到的数量和论文中的数量可能不同。

#### 3.1 申请高德 Web 服务 Key

1. 打开高德开放平台：`https://lbs.amap.com/`
2. 注册或登录账号。
3. 进入控制台。
4. 创建一个应用。
5. 在应用下添加 Key。
6. 服务平台选择 `Web 服务`。
7. 复制生成的 Key。

注意：这里需要的是 `Web 服务` Key，不是 Android、iOS 或 Web 端 JavaScript Key。

#### 3.2 写入本地 `.env`

在仓库根目录新建一个名为 `.env` 的文件，内容为：

```text
AMAP_KEY=这里替换成你的高德Web服务Key
```

例如：

```text
AMAP_KEY=abcdefg1234567890
```

不要把 `.env` 上传到网络。`.env` 只应该保存在你自己的电脑上。代码只读取这个 Key，不会有任何形式的泄露。

如果你不想创建 `.env`，也可以在命令中直接传入 Key：

```powershell
python paper_data/reproduce_poi_figures.py --collect --amap-key 你的高德Web服务Key
```

#### 3.3 运行重新采集

在仓库根目录运行：

```powershell
python paper_data/reproduce_poi_figures.py --collect
```

程序会执行：

```text
调用高德 Web 服务 -> 保存原始 POI -> 自动清洗分类 -> 计算空间变量 -> 生成论文 POI 图
```

默认使用论文附录所列举的关键词检索、清洗和分类规则。

### 4. 本地查看交互页面

本项目还提供两个交互页面：

- `paper_data/index.html`：行业六维参数雷达图；
- `paper_data/map.html`：上海 POI 交互地图，可勾选不同生产类型。

可以直接双击 HTML 文件打开，但如果浏览器禁止本地页面读取 CSV，可以在仓库根目录启动一个静态服务器：

```powershell
python -m http.server 8765 --directory paper_data
```

然后在浏览器打开：

```text
http://127.0.0.1:8765/
```

对应页面为：

```text
http://127.0.0.1:8765/index.html
http://127.0.0.1:8765/map.html
```

