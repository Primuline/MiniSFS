<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
<p align="center">
  <a href="https://github.com/Primuline/MiniSFS">
    <img src="https://img.shields.io/badge/GitHub-MiniSFS-blue?style=for-the-badge&logo=github" alt="GitHub Repo">
  </a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
</p>

<br />
<div align="center">

# MiniSFS

  <p align="center">
    一个基于 Pygame 与 NumPy 的二维宇宙飞行模拟器
    <br />
    <br />
    <a href="Intro.md"><strong>查看更详细的项目介绍 »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Primuline/MiniSFS">GitHub 仓库</a>
    ·
    <a href="https://github.com/Primuline/MiniSFS/releases">下载 Release</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>目录</summary>
  <ol>
    <li><a href="#about-the-project">项目介绍</a></li>
    <li><a href="#features">核心功能</a></li>
    <li><a href="#algorithms">核心算法</a></li>
    <li>
      <a href="#getting-started">运行指南</a>
      <ul>
        <li><a href="#prerequisites">环境要求</a></li>
        <li><a href="#installation">安装依赖</a></li>
        <li><a href="#run">运行方式</a></li>
      </ul>
    </li>
    <li><a href="#usage">常用操作</a></li>
    <li><a href="#project-structure">项目结构</a></li>
    <li><a href="#ai-statement">AI 工具使用声明</a></li>
    <li><a href="#references">参考来源与诚信声明</a></li>
    <li><a href="#license">许可证</a></li>
    <li><a href="#appendix">附录</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## 项目介绍
<a id="about-the-project"></a>

<img src="https://raw.githubusercontent.com/Primuline/cloudimg/master/20260619234411.png" style="zoom:50%;" />

MiniSFS 是一个二维宇宙飞行模拟器。项目以 **Pygame** 为界面基础，用 **NumPy** 管理物理状态，实现了沙盒模式、关卡模式、参考系观察、轨迹预测、探测器火箭推进、着陆判定以及基础的空间数据结构优化。

本项目是一个简单的轨道力学模拟小游戏。用户可以在沙盒中放置恒星、行星、探测器和带电天体，也可以进入预设关卡，尝试完成从一个天体到另一个天体的转移与着陆。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- FEATURES -->
## 核心功能
<a id="features"></a>

- **沙盒模式**：自由创建和编辑恒星、行星、探测器、自定义带电天体。
- **关卡模式**：目前实现两个关卡，包括地月转移和地火转移；具体数值借鉴实际天体数据或火箭数据，并为了降低难度对火箭性能进行了适当提升。
- **参考系观察**：双击天体可进入对应参考系，便于观察相对运动。
- **轨迹预测**：辅助观察天体和探测器未来一段时间内的运动趋势。
- **探测器推进与着陆判定**：支持火箭推进控制，并对着陆状态进行基础判定。
- **核心工具**：长度测量、角度测量、网格显示和标签显示。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- ALGORITHMS -->
## 核心算法
<a id="algorithms"></a>

### RK4 积分方法

使用 **RK4（四阶 Runge-Kutta）** 作为主要积分方法求解力学方程。相比显式 Euler 方法，RK4 在轨道模拟中具有更好的稳定性，能够降低能量漂移，使近似圆轨道更加平滑。

### Barnes-Hut QuadTree

`N` 体系统的直接计算复杂度为 `O(n^2)`。为了降低复杂度，项目使用 **Barnes-Hut QuadTree** 算法，在天体数量较多时通过空间划分树把远处天体团近似为一个质心，从而将整体复杂度降低到约 `O(n log n)`。

算法的具体说明见本文档附录。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- GETTING STARTED -->
## 运行指南
<a id="getting-started"></a>

### 环境要求
<a id="prerequisites"></a>

- Python 3.10+
- Windows 10/11

### 安装依赖
<a id="installation"></a>

```bash
pip install pygame numpy
```

### 运行方式
<a id="run"></a>

#### 运行源码版本

```bash
python -m src.main
```

#### 运行打包版本

也可以直接在 Release 页面下载打包好的 `MiniSFS.exe`，双击运行即可。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- USAGE -->
## 常用操作
<a id="usage"></a>

| 操作 | 控制方式 |
|:--|:--|
| 平移视角 | 鼠标中键拖拽 或 方向键 |
| 缩放 | 鼠标滚轮 |
| 选中天体 | 左键点击 |
| 进入参考系 | 双击天体 |
| 探测器喷气 | 方向键 |
| 暂停 / 继续 | `Space` |
| 重置当前模式 | `R` |
| 显示快捷键帮助 | `H` |
| 网格 | `G` |
| 标签 | `L` |
| 删除选中天体 | `Del` / `Backspace` |

<img src="https://raw.githubusercontent.com/Primuline/cloudimg/master/20260619234531.png" alt="操作示意图" style="zoom:50%;" />

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- PROJECT STRUCTURE -->
## 项目结构
<a id="project-structure"></a>

```text
MiniSFS/
├── assets/levels/          # 关卡 JSON 数据
├── src/
│   ├── main.py             # 主循环、模式、关卡和交互编排
│   ├── config.py           # 全局常量和默认参数
│   ├── core/               # BodyState 类型、接口和工具
│   ├── physics/            # 力、积分、碰撞、火箭推进
│   ├── quadtree/           # 四叉树、Barnes-Hut、拖尾缓冲
│   ├── rendering/          # Pygame 渲染、相机、HUD、输入框
│   └── input/              # Pygame 事件到命令的转换
├── tests/                  # Pytest 测试
├── docs/                   # 设计文档和规格说明
├── MAIN.md                 # 架构说明
├── Intro.md                # 原 README 功能介绍
├── MiniSFS.spec            # PyInstaller 打包配置
├── requirements.txt        # Python 依赖
└── README.md               # 课程提交说明
```

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- AI STATEMENT -->
## AI 工具使用声明
<a id="ai-statement"></a>

本项目开发过程中使用了 AI 工具辅助，包括 ChatGPT / Codex。AI 主要用于：

- 协助梳理需求和拆分任务。
- 辅助生成部分 UI、测试和文档草稿。
- 辅助定位异常、解释报错和提出修复方案。
- 协助重构和检查代码一致性。

核心系统设计、功能取舍、物理规则设定、测试验收和最终代码合并均经过人工审查与调整。对于 AI 生成或辅助修改的代码，均进行了人工阅读、运行测试和必要的手动修正。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- REFERENCES -->
## 参考来源与诚信声明
<a id="references"></a>

使用的主要第三方库：

- **Pygame**：窗口、事件和 2D 渲染。
- **NumPy**：矩阵状态存储和数值计算。
- **Pytest**：自动化测试。
- **PyInstaller**：Windows 可执行文件打包。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- LICENSE -->
## 许可证
<a id="license"></a>

本项目使用 MIT License。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- APPENDIX -->
## 附录
<a id="appendix"></a>

### Barnes-Hut 四叉树算法

#### 问题背景

N 体引力模拟中，暴力计算每对粒子间的引力需要 **O(n²)** 次运算。当 n = 100 万时完全不可行。Barnes-Hut 将复杂度降至 **O(n log n)**。

#### 核心思想

> **足够远的粒子群，可以用其质心来近似代替。**

当一组粒子距离目标足够远时，不需要逐一计算，只需把这一群粒子看作一个“超级粒子”（质心 + 总质量），误差通常可以接受。

#### 算法步骤

**① 建树**：将所有粒子插入四叉树，每个叶节点存一个粒子，每个内部节点记录其子树的**质心**和**总质量**。

**② 对每个粒子计算合力**：从根节点开始递归遍历，对每个节点判断：

$$
\theta = \frac{s}{d}
$$

- `s`：该节点代表的区域边长
- `d`：粒子到该节点质心的距离
- `θ`：精度参数，通常取 **0.5**

```text
if θ < 阈值:
    用该节点的质心近似计算引力  ← 剪枝，不再深入
else:
    递归遍历四个子节点
```

**③ 积分推进**：用合力更新每个粒子的速度和位置，进入下一时间步，重建四叉树。

### 精度与速度的权衡

| θ 值 | 效果 |
|:--|:--|
| θ = 0 | 退化为暴力 O(n²)，精度最高 |
| θ = 0.5 | 工程常用，精度与速度平衡 |
| θ = 1.0 | 速度最快，误差较大 |

### 复杂度分析

- 建树：**O(n log n)**
- 每个粒子遍历树：**O(log n)**（大量节点被剪枝）
- 总体：**O(n log n)**

### 扩展

- 三维版本称为八叉树（Octree），原理完全相同。
- 现代 GPU 并行版本可模拟大规模粒子系统。
- t-SNE 降维算法也借用了类似思路加速梯度计算。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>
