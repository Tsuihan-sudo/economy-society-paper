# 课程论文数据与复现材料

本仓库用于展示课程论文《城市中心生产活动的集聚阈值与上海 POI 证据》的源码、论文图、POI 数据、交互页面和最小复现代码。

仓库不是一个正式经济学实证项目，而是课程论文的可审阅材料。POI 数据来自地图平台自动采集与规则清洗，作用是提供描述性证据，不是企业普查，也不构成因果识别。

## 仓库内容

```text
paper.tex
  论文 LaTeX 源码。

figures/
  论文使用的 PNG 图片。

paper_data/
  index.html
    可交互行业六维参数雷达图。
  map.html
    可交互上海 POI 地图，可勾选显示不同生产类型。
  reproduce_poi_figures.py
    单文件复现代码：获取 POI、清洗分类、生成论文 POI 图。
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
  运行单文件复现代码所需的 Python 包。
```

## 在线页面

如果本仓库启用了 GitHub Pages，并选择 `main` 分支的 `/paper_data` 目录作为发布源，则通常可以访问：

```text
https://<你的用户名>.github.io/<仓库名>/
```

其中：

- `index.html` 是可交互雷达图；
- `map.html` 是可交互 POI 地图；
- `data/amap_poi_raw.csv` 是原始 POI 数据；
- `data/poi_classification_audit.csv` 是分类审计表。

## 本地环境准备

建议使用 Python 3.10 或更高版本。

在仓库根目录打开 PowerShell：

```powershell
cd D:\Original_F\Vscode\Economy_society
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

依赖很少，只包括：

- `pandas`
- `numpy`
- `matplotlib`

## 验证方式一：使用已上传原始数据复现

这是最适合老师审阅的方式。它不会重新联网采集，只使用仓库中的 `paper_data/data/amap_poi_raw.csv`，然后重新执行：

```text
原始 POI 数据 -> 自动清洗分类 -> 空间变量 -> 论文 POI 图
```

运行：

```powershell
python paper_data/reproduce_poi_figures.py --use-existing
```

成功后会更新：

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

如果输出中出现类似下面的数值，说明复现口径与论文当前数据一致：

```text
清洗后保留: 2756 条
传统制造: 1072
城市型生产: 476
城市型生产到人民广场均值: 18.94 km
传统制造到人民广场均值: 28.16 km
```

## 验证方式二：申请自己的高德 Key 并重新采集

这一步用于验证采集流程，而不是要求重新得到完全相同的数据。地图平台数据会随时间变化，因此重新采集的 POI 数量可能与论文提交时不同。

### 1. 获取高德 Web 服务 Key

1. 打开高德开放平台：`https://lbs.amap.com/`
2. 登录或注册账号。
3. 进入控制台或应用管理。
4. 创建一个应用。
5. 在该应用下添加 Key。
6. 服务平台选择 `Web 服务`。
7. 提交后复制得到的 Key。

高德官方文档中也说明，创建 Key 时服务平台需要选择 `Web 服务`，Web 服务 API 的请求参数中 `key` 是必填项。

### 2. 在本地写入 Key

在仓库根目录新建 `.env` 文件，内容如下：

```text
AMAP_KEY=这里替换成你的高德Web服务Key
```

注意：

- 不要把 `.env` 上传到 GitHub。
- 本仓库的 `.gitignore` 已经忽略 `.env`。
- 代码只读取 Key，不会把 Key 写入 CSV 或打印到终端。

### 3. 一键重新采集、清洗、出图

运行：

```powershell
python paper_data/reproduce_poi_figures.py --collect
```

这会执行：

```text
调用高德 Web 服务 -> 保存原始 POI -> 自动清洗分类 -> 计算空间变量 -> 生成论文 POI 图
```

默认是全市关键词检索，和当前上传数据的采集方式一致。若希望按 16 个行政区逐区检索，可运行：

```powershell
python paper_data/reproduce_poi_figures.py --collect --by-district
```

逐区检索更细，但会消耗更多 API 调用次数，结果也会与论文当前数据不完全相同。

## 交互页面本地查看

由于浏览器直接打开本地 HTML 时可能限制 `fetch()` 读取 CSV，建议启动一个本地静态服务器：

```powershell
python -m http.server 8765 --directory paper_data
```

然后在浏览器打开：

```text
http://127.0.0.1:8765/
```

雷达图页面：

```text
http://127.0.0.1:8765/index.html
```

交互地图：

```text
http://127.0.0.1:8765/map.html
```

## 方法边界

本仓库保留原始数据和分类审计表，是为了让老师可以检查：

- 采集了哪些关键词；
- 哪些 POI 被过滤；
- 每条 POI 被归入哪一类；
- 分类理由是什么；
- 空间距离如何计算。

但这些数据仍有局限：

- POI 是地图平台样本，不是完整企业名录；
- 自动分类可能有漏判或误判；
- 距离圈层是本文人为设定的操作性分组；
- 图表展示的是描述性空间分布，不是因果识别。

