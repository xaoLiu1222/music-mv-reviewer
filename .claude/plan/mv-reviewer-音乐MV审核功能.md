# MV审核功能实现计划

## 任务概述

为 video-analyzer 项目添加音乐MV审核功能，支持7条审核规则，违规视频移动到指定目录。

## 审核规则

| 规则 | 描述 | 技术方案 |
|------|------|---------|
| 1 | 作词作曲：林夕，不能要 | ShazamAPI + MusicBrainz API |
| 2 | 竖屏，或有上下左右全黑边 | OpenCV 画面分析 |
| 3 | 声音过大或过小（音量突变） | pydub 音频波形分析 |
| 4 | 画面内容暴露，导向有问题 | Vision LLM 内容审核 |
| 5 | 背景只有风景画，无其他内容 | Vision LLM 场景分类 |
| 6 | 内容里有广告 | Vision LLM 广告检测 |
| 7 | 吸毒画面 | Vision LLM 敏感内容检测 |

## 技术栈

- **音乐识别**: ShazamAPI (开源免费)
- **元数据查询**: MusicBrainz API (完全免费)
- **视觉分析**: 硅基流动 Qwen2.5-VL / 现有LLM客户端
- **音频分析**: pydub (已有依赖)
- **画面分析**: OpenCV (已有依赖)

---

## 文件结构

```
video_analyzer/
├── mv_reviewer/                    # 新增：MV审核模块
│   ├── __init__.py                 # 模块初始化
│   ├── reviewer.py                 # 审核主逻辑 (~150行)
│   ├── rules/                      # 规则引擎
│   │   ├── __init__.py
│   │   ├── base_rule.py            # 规则基类 (~50行)
│   │   ├── metadata_rule.py        # 规则1: 作词作曲 (~120行)
│   │   ├── aspect_rule.py          # 规则2: 竖屏/黑边 (~80行)
│   │   ├── volume_rule.py          # 规则3: 音量突变 (~100行)
│   │   └── content_rule.py         # 规则4-7: 内容审核 (~150行)
│   ├── services/                   # 外部服务
│   │   ├── __init__.py
│   │   ├── shazam_client.py        # Shazam音频识别 (~80行)
│   │   └── musicbrainz_client.py   # MusicBrainz元数据 (~100行)
│   └── models/
│       ├── __init__.py
│       └── review_result.py        # 审核结果模型 (~60行)
├── cli_review.py                   # 新CLI入口 (~180行)
├── prompts/
│   └── mv_review/                  # 审核专用prompt
│       └── content_review.txt      # 内容审核提示词
└── config/
    └── review_config.json          # 审核配置（可选）
```

---

## 详细步骤

### 步骤 1: 数据模型和规则基类

**文件**: `mv_reviewer/models/review_result.py`

```python
@dataclass
class RuleViolation:
    rule_id: int           # 规则编号 1-7
    rule_name: str         # 规则名称
    description: str       # 违规描述
    confidence: float      # 置信度 0-1
    details: Dict[str, Any] # 详细信息

@dataclass
class ReviewResult:
    video_path: Path
    is_violation: bool     # 是否违规
    violations: List[RuleViolation]
    metadata: Dict[str, Any]  # 歌曲元数据
    review_time: float     # 审核耗时
```

**文件**: `mv_reviewer/rules/base_rule.py`

```python
class BaseRule(ABC):
    rule_id: int
    rule_name: str

    @abstractmethod
    def check(self, context: ReviewContext) -> Optional[RuleViolation]:
        """检查是否违规，返回None表示通过"""
        pass
```

### 步骤 2: 音乐识别服务

**文件**: `mv_reviewer/services/shazam_client.py`

- 依赖: `shazamio` (异步Shazam API)
- 功能: 从视频音频中识别歌曲
- 返回: 歌曲名称、歌手名称

**文件**: `mv_reviewer/services/musicbrainz_client.py`

- 依赖: `musicbrainzngs` (官方Python库)
- 功能: 根据歌名+歌手查询作词作曲
- 返回: 作词者、作曲者列表

### 步骤 3: 规则实现

**规则1 - 作词作曲检测** (`metadata_rule.py`):
```python
class MetadataRule(BaseRule):
    rule_id = 1
    rule_name = "作词作曲检测"
    blocked_creators = ["林夕"]  # 可配置

    def check(self, context):
        # 1. ShazamClient 识别歌曲
        # 2. MusicBrainzClient 查询元数据
        # 3. 检查作词/作曲是否在黑名单
```

**规则2 - 竖屏/黑边检测** (`aspect_rule.py`):
```python
class AspectRule(BaseRule):
    rule_id = 2
    rule_name = "竖屏/黑边检测"

    def check(self, context):
        # 1. 获取视频第一帧
        # 2. 检测宽高比 (竖屏: height > width)
        # 3. 检测四边黑边 (边缘像素均值 < 阈值)
```

**规则3 - 音量突变检测** (`volume_rule.py`):
```python
class VolumeRule(BaseRule):
    rule_id = 3
    rule_name = "音量突变检测"
    volume_change_threshold = 10  # dB

    def check(self, context):
        # 1. 使用pydub加载音频
        # 2. 分段计算RMS音量
        # 3. 检测相邻段音量差异是否超过阈值
```

**规则4-7 - 内容审核** (`content_rule.py`):
```python
class ContentRule(BaseRule):
    # 合并规则4,5,6,7，使用Vision LLM一次性检测

    def check(self, context):
        # 1. 获取关键帧
        # 2. 使用审核专用prompt调用Vision LLM
        # 3. 解析返回结果，判断各项违规
```

### 步骤 4: 审核主逻辑

**文件**: `mv_reviewer/reviewer.py`

```python
class MVReviewer:
    def __init__(self, config, llm_client):
        self.rules = [
            MetadataRule(config),
            AspectRule(config),
            VolumeRule(config),
            ContentRule(config, llm_client),
        ]

    def review(self, video_path: Path) -> ReviewResult:
        """执行所有规则检查"""
        context = self._build_context(video_path)
        violations = []
        for rule in self.rules:
            violation = rule.check(context)
            if violation:
                violations.append(violation)
        return ReviewResult(...)

    def review_batch(self, directory: Path) -> List[ReviewResult]:
        """批量审核目录下所有视频"""
        pass
```

### 步骤 5: CLI入口

**文件**: `video_analyzer/cli_review.py`

```python
def main():
    parser = argparse.ArgumentParser(description="MV内容审核工具")
    parser.add_argument("input", help="视频文件或目录路径")
    parser.add_argument("--violation-dir", default="violations", help="违规视频移动目录")
    parser.add_argument("--rules", nargs="+", type=int, help="指定检查的规则(1-7)")
    parser.add_argument("--report", help="输出审核报告路径")
    # ... 其他参数
```

**命令示例**:
```bash
# 单文件审核
mv-reviewer video.mp4 --violation-dir ./violations

# 批量审核
mv-reviewer ./mv_folder/ --violation-dir ./violations --report report.json

# 仅检查特定规则
mv-reviewer video.mp4 --rules 1 2 3
```

### 步骤 6: 审核Prompt

**文件**: `prompts/mv_review/content_review.txt`

```
你是一个专业的视频内容审核员。请分析以下视频帧，检查是否存在以下违规内容：

1. 暴露内容：裸露、性暗示、不雅动作
2. 导向问题：政治敏感、暴力血腥、恐怖画面
3. 纯风景背景：画面仅有风景（山水、天空、建筑等），无人物或其他主体内容
4. 广告内容：商品展示、品牌logo、促销信息、二维码
5. 吸毒画面：吸食毒品、注射器、毒品相关物品

请以JSON格式返回检测结果：
{
  "exposure": {"detected": bool, "confidence": float, "description": str},
  "inappropriate": {"detected": bool, "confidence": float, "description": str},
  "landscape_only": {"detected": bool, "confidence": float, "description": str},
  "advertisement": {"detected": bool, "confidence": float, "description": str},
  "drug_use": {"detected": bool, "confidence": float, "description": str}
}
```

### 步骤 7: 配置和依赖

**新增依赖** (`requirements.txt`):
```
shazamio>=0.5.0          # Shazam音频识别
musicbrainzngs>=0.7.1    # MusicBrainz API
```

**审核配置** (`config/review_config.json`):
```json
{
  "rules": {
    "metadata": {
      "enabled": true,
      "blocked_creators": ["林夕"]
    },
    "aspect": {
      "enabled": true,
      "black_border_threshold": 10,
      "min_black_border_ratio": 0.1
    },
    "volume": {
      "enabled": true,
      "change_threshold_db": 10,
      "segment_duration_ms": 1000
    },
    "content": {
      "enabled": true,
      "confidence_threshold": 0.7
    }
  },
  "violation_dir": "violations",
  "report_format": "json"
}
```

### 步骤 8: setup.py 更新

```python
entry_points={
    'console_scripts': [
        'video-analyzer=video_analyzer.cli:main',
        'mv-reviewer=video_analyzer.cli_review:main',  # 新增
    ],
}
```

---

## 预期输出

### 审核报告示例 (JSON)

```json
{
  "summary": {
    "total": 100,
    "passed": 85,
    "violated": 15,
    "review_time": "00:15:32"
  },
  "violations": [
    {
      "video": "song1.mp4",
      "rules_violated": [1],
      "details": {
        "rule_1": {
          "name": "作词作曲检测",
          "song": "红豆",
          "artist": "王菲",
          "lyricist": "林夕",
          "composer": "柳重言"
        }
      },
      "action": "moved_to_violations/song1.mp4"
    }
  ]
}
```

---

## 风险和注意事项

1. **ShazamAPI 限制**: 非官方API，可能有请求限制，需要添加重试机制
2. **MusicBrainz 数据覆盖**: 部分中文歌曲可能查不到，需要fallback处理
3. **Vision LLM 准确度**: 内容审核依赖LLM判断，可能有误判，建议设置置信度阈值
4. **处理时间**: 批量处理大量视频时间较长，考虑添加进度显示

---

## 执行顺序

1. ✅ 创建目录结构和基础文件
2. ✅ 实现数据模型 (`review_result.py`)
3. ✅ 实现规则基类 (`base_rule.py`)
4. ✅ 实现外部服务 (`shazam_client.py`, `musicbrainz_client.py`)
5. ✅ 实现各规则 (`metadata_rule.py`, `aspect_rule.py`, `volume_rule.py`, `content_rule.py`)
6. ✅ 实现审核主逻辑 (`reviewer.py`)
7. ✅ 实现CLI入口 (`cli_review.py`)
8. ✅ 添加审核prompt
9. ✅ 更新配置和依赖
10. ✅ 测试和优化

---

**计划创建时间**: 2025-12-04
**预计完成时间**: 约2-3小时
