# paper_data

此目录用于 GitHub Pages 发布课程论文配套材料。

## 页面

- `index.html`: 交互式行业六维参数雷达图。
- `map.html`: 交互式上海生产活动 POI 地图。

## 数据

- `data/model_parameters.csv`: 理论模型中 9 类生产活动的六维参数。
- `data/scenario_parameters.csv`: 4 个情景的背景参数向量。
- `data/amap_poi_raw.csv`: 高德地图采集得到的原始 POI 数据。
- `data/poi_classification_audit.csv`: 全部输入 POI 的自动清洗与分类审计表。
- `data/poi_spatial.csv`: 清洗后 POI 及空间变量。

## 复现代码

- `reproduce_poi_figures.py`: 单文件复现脚本，可使用已上传原始数据重新清洗出图，也可配置高德 Web 服务 Key 后重新采集。

运行方法见仓库根目录 `README.md`。
