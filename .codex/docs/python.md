# MiniSFS Python 编码规范

## 1. 风格

- 遵循 PEP 8。
- 使用 4 空格缩进。
- 单行尽量不超过 100 字符。
- 导入顺序为：标准库、第三方库、项目内部模块，每组之间空一行。

## 2. 命名

- 类名：`PascalCase`
- 函数与方法：`snake_case`
- 变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有成员：前导下划线，如 `_private_method`

## 3. 类型与文档

- 新增或修改的公开函数必须带参数与返回值类型注解。
- 新增公开类、公开函数、公开模块应写 docstring。
- docstring 优先使用 Google 风格。

## 4. NumPy 约定

- 使用 `import numpy as np`。
- 物理和几何计算优先使用向量化操作。
- 固定数值数组优先使用 `np.float64`。
- `BodyState` 字段必须使用 `src/core/types.py` 中的列索引常量，避免硬编码列号。

## 5. 测试

- 使用 `pytest`。
- 浮点比较使用 `pytest.approx`。
- Pygame 相关测试应尽量使用 headless/dummy video driver。
- 修改核心逻辑后至少运行相关测试；跨模块改动后运行 `pytest tests/ -q`。

