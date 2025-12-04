# 规则2调整：黑边检测阈值修改

## 需求描述

**原规则**: 竖屏，或节目有上下左右全黑边 不要

**新规则**: 竖屏，或节目有上下左右全黑边，上下或左右黑边总共比例占比超过或等同于整个视频的40%的比例时，不要

## 变更分析

### 当前逻辑
- 竖屏检测：`height > width` → 违规
- 黑边检测：任意边黑边比例 >= 5% → 违规

### 新逻辑
- 竖屏检测：`height > width` → 违规（保持不变）
- 黑边检测：
  - 上下黑边总和 >= 40% → 违规
  - 或 左右黑边总和 >= 40% → 违规

## 实施步骤

### 步骤1: 修改默认阈值
- 文件: `video_analyzer/mv_reviewer/rules/aspect_rule.py`
- 修改: `DEFAULT_BORDER_RATIO = 0.05` → `DEFAULT_TOTAL_BORDER_RATIO = 0.40`

### 步骤2: 修改黑边检测逻辑
- 修改 `_detect_black_borders()` 方法
- 计算上下黑边总和: `top_ratio + bottom_ratio`
- 计算左右黑边总和: `left_ratio + right_ratio`
- 判断是否 >= 40%

### 步骤3: 更新配置文件
- 文件: `video_analyzer/config/review_config.json`
- 修改: `border_ratio` → `total_border_ratio: 0.40`

### 步骤4: 更新文档
- 更新规则描述

## 代码变更详情

```python
# 修改前
DEFAULT_BORDER_RATIO = 0.05   # Minimum border ratio to trigger (5%)

# 修改后
DEFAULT_TOTAL_BORDER_RATIO = 0.40  # Total border ratio threshold (40%)
```

```python
# 修改前: 检测任意单边黑边
if top_ratio >= self.border_ratio:
    border_sides.append('上')

# 修改后: 检测上下或左右总和
vertical_total = top_ratio + bottom_ratio
horizontal_total = left_ratio + right_ratio

if vertical_total >= self.total_border_ratio:
    # 上下黑边总和超过40%

if horizontal_total >= self.total_border_ratio:
    # 左右黑边总和超过40%
```

## 验收标准

1. 竖屏视频仍然被检测为违规
2. 上下黑边总和 >= 40% 时检测为违规
3. 左右黑边总和 >= 40% 时检测为违规
4. 单边黑边 < 40% 且总和 < 40% 时不触发违规
5. 配置文件可调整阈值

## 预计影响

- 减少误报：之前5%黑边就触发，现在需要40%总和才触发
- 更符合实际需求：只有明显的黑边视频才会被标记

---
创建时间: 2025-12-04
状态: 待执行
