[根目录](/home/nano/桌面/openProject/video-analyzer/CLAUDE.md) > **video_analyzer**

# video_analyzer 核心模块

## 变更记录 (Changelog)

### 2025-12-04
- 初始化模块文档
- 完成核心组件分析

---

## 模块职责

video_analyzer 是项目的核心分析引擎，负责：
- 视频帧提取与关键帧识别
- 音频提取与 Whisper 转录
- LLM 客户端管理与视觉分析
- 配置系统与提示词加载
- CLI 命令行接口

---

## 入口与启动

### 主入口点

**文件**：`cli.py`
**命令**：`video-analyzer`（通过 setup.py 注册）

```python
# 入口函数
def main():
    # 1. 解析命令行参数
    # 2. 加载配置（级联：CLI > 用户配置 > 默认配置）
    # 3. 初始化组件（VideoProcessor, AudioProcessor, VideoAnalyzer）
    # 4. 执行三阶段处理
    # 5. 输出 JSON 结果
```

### 启动流程

```bash
video-analyzer video.mp4 [选项]
```

**关键参数**：
- `--client`：选择 LLM 客户端（ollama/openai_api）
- `--model`：指定视觉模型
- `--whisper-model`：Whisper 模型大小或路径
- `--start-stage`：从特定阶段开始（1-3）
- `--max-frames`：限制处理帧数
- `--log-level`：日志级别（DEBUG/INFO/WARNING/ERROR）

---

## 对外接口

### CLI 接口

**命令行工具**：`video-analyzer`

```bash
# 基本用法
video-analyzer <video_path> [options]

# 完整示例
video-analyzer video.mp4 \
    --client openai_api \
    --api-key sk-xxx \
    --api-url https://openrouter.ai/api/v1 \
    --model meta-llama/llama-3.2-11b-vision-instruct:free \
    --whisper-model large \
    --prompt "描述视频中的主要活动" \
    --max-frames 30 \
    --keep-frames \
    --log-level DEBUG
```

### Python API

```python
from video_analyzer.config import Config
from video_analyzer.frame import VideoProcessor
from video_analyzer.audio_processor import AudioProcessor
from video_analyzer.analyzer import VideoAnalyzer
from video_analyzer.clients.ollama import OllamaClient

# 初始化配置
config = Config("config")

# 创建处理器
video_processor = VideoProcessor(video_path, output_dir, model)
audio_processor = AudioProcessor(language="en", model_size_or_path="medium")

# 提取帧和音频
frames = video_processor.extract_keyframes(frames_per_minute=60)
transcript = audio_processor.transcribe(audio_path)

# 分析
client = OllamaClient("http://localhost:11434")
analyzer = VideoAnalyzer(client, model, prompt_loader, temperature=0.2)
frame_analyses = [analyzer.analyze_frame(frame) for frame in frames]
video_description = analyzer.reconstruct_video(frame_analyses, frames, transcript)
```

---

## 关键依赖与配置

### 外部依赖

```
opencv-python>=4.8.0      # 视频帧提取
numpy>=1.24.0             # 数值计算
torch>=2.0.0              # PyTorch（Whisper 依赖）
openai-whisper>=20231117  # 音频转录
faster-whisper>=0.6.0     # 更快的 Whisper 实现
requests>=2.31.0          # HTTP 客户端
Pillow>=10.0.0            # 图像处理
pydub>=0.25.1             # 音频处理备用方案
```

### 配置文件

**位置**：`config/default_config.json`

```json
{
  "clients": {
    "default": "ollama",
    "temperature": 0.0,
    "ollama": {
      "url": "http://localhost:11434",
      "model": "llama3.2-vision"
    },
    "openai_api": {
      "api_key": "",
      "model": "meta-llama/llama-3.2-11b-vision-instruct",
      "api_url": "https://openrouter.ai/api/v1"
    }
  },
  "frames": {
    "per_minute": 60,
    "analysis_threshold": 10.0,
    "min_difference": 5.0,
    "max_count": 30
  },
  "audio": {
    "whisper_model": "medium",
    "language": "en",
    "device": "cpu"
  }
}
```

### 配置加载优先级

1. **命令行参数**（最高）
2. **用户配置**：`config/config.json`
3. **默认配置**：`config/default_config.json`（包内）

---

## 数据模型

### Frame（帧数据类）

```python
@dataclass
class Frame:
    number: int          # 帧序号
    path: Path           # 图像文件路径
    timestamp: float     # 时间戳（秒）
    score: float         # 差异分数
```

### AudioTranscript（音频转录）

```python
@dataclass
class AudioTranscript:
    text: str                      # 完整转录文本
    segments: List[Dict[str, Any]] # 分段信息（时间戳、词级别）
    language: str                  # 检测到的语言
```

### 输出格式（analysis.json）

```json
{
  "metadata": {
    "client": "ollama",
    "model": "llama3.2-vision",
    "whisper_model": "medium",
    "frames_per_minute": 60,
    "duration_processed": 120.5,
    "frames_extracted": 120,
    "frames_processed": 30,
    "start_stage": 1,
    "audio_language": "en",
    "transcription_successful": true
  },
  "transcript": {
    "text": "完整转录文本...",
    "segments": [...]
  },
  "frame_analyses": [
    {
      "response": "帧分析描述..."
    }
  ],
  "video_description": {
    "response": "完整视频描述..."
  }
}
```

---

## 核心组件详解

### 1. VideoProcessor（帧处理器）

**文件**：`frame.py`

**职责**：
- 使用 OpenCV 提取视频帧
- 计算帧间差异识别关键帧
- 自适应采样算法

**关键方法**：
```python
def extract_keyframes(
    frames_per_minute: int = 10,
    duration: Optional[float] = None,
    max_frames: Optional[int] = None
) -> List[Frame]
```

**算法流程**：
1. 计算目标帧数：`(视频时长/60) * frames_per_minute`
2. 自适应采样间隔：`总帧数 / (目标帧数 * 2)`
3. 帧差异分析：使用灰度图 `cv2.absdiff`
4. 选择差异最大的帧
5. 如果指定 `max_frames`，均匀采样

### 2. AudioProcessor（音频处理器）

**文件**：`audio_processor.py`

**职责**：
- 使用 FFmpeg 提取音频
- 使用 faster-whisper 转录
- VAD 过滤和质量检查

**关键方法**：
```python
def extract_audio(video_path: Path, output_dir: Path) -> Optional[Path]
def transcribe(audio_path: Path) -> Optional[AudioTranscript]
```

**特性**：
- 自动语言检测
- VAD（语音活动检测）过滤静音
- 词级别时间戳
- 置信度评分

### 3. VideoAnalyzer（视频分析器）

**文件**：`analyzer.py`

**职责**：
- 逐帧分析（包含上下文）
- 视频重建与描述生成
- 提示词管理

**关键方法**：
```python
def analyze_frame(frame: Frame) -> Dict[str, Any]
def reconstruct_video(
    frame_analyses: List[Dict[str, Any]],
    frames: List[Frame],
    transcript: Optional[AudioTranscript] = None
) -> Dict[str, Any]
```

**上下文管理**：
- 维护 `previous_analyses` 列表
- 每次分析包含前序帧信息
- 使用 `{PREVIOUS_FRAMES}` 占位符注入上下文

### 4. LLM 客户端（clients/）

**基类**：`llm_client.py`

```python
class LLMClient(ABC):
    def encode_image(self, image_path: str) -> str:
        # Base64 编码图像

    @abstractmethod
    def generate(
        prompt: str,
        image_path: Optional[str] = None,
        model: str = "llama3.2-vision",
        temperature: float = 0.2,
        num_predict: int = 256
    ) -> Dict[Any, Any]:
        pass
```

**实现类**：

- **OllamaClient**（`ollama.py`）：
  - 本地 Ollama API
  - 图像作为 base64 数组发送
  - 无需 API 密钥

- **GenericOpenAIAPIClient**（`generic_openai_api.py`）：
  - OpenAI 兼容 API（OpenRouter、OpenAI）
  - 图像作为 `image_url` 内容发送
  - 支持重试和速率限制处理

### 5. 配置系统（config.py）

**类**：`Config`

**职责**：
- 加载和管理配置
- 命令行参数覆盖
- 配置级联

**关键方法**：
```python
def load_config()  # 加载配置文件
def get(key: str, default: Any = None) -> Any  # 获取配置值
def update_from_args(args: argparse.Namespace)  # 从 CLI 更新
```

### 6. 提示词加载器（prompt.py）

**类**：`PromptLoader`

**职责**：
- 从包资源或用户目录加载提示词
- 支持开发模式即时修改
- 路径解析优先级

**路径解析顺序**：
1. 包资源（pkg_resources）
2. 包目录（开发模式）
3. 用户指定目录（绝对/相对路径）

**提示词占位符**：
- `{PREVIOUS_FRAMES}`：前序帧分析
- `{FRAME_NOTES}`：所有帧笔记
- `{TRANSCRIPT}`：音频转录
- `{FIRST_FRAME}`：首帧分析
- `{prompt}`：用户自定义问题

---

## 测试与质量

### 现有测试

**文件**：`/test_prompt_loading.py`

```python
# 测试包提示词加载
# 测试自定义提示词目录
```

### 测试建议

1. **单元测试**：
   - `test_frame_extraction.py`：测试帧提取算法
   - `test_audio_processing.py`：测试音频转录
   - `test_config_cascade.py`：测试配置优先级
   - `test_llm_clients.py`：模拟 API 响应

2. **集成测试**：
   - 端到端视频分析流程
   - 不同视频格式和质量
   - 多语言音频处理

3. **性能测试**：
   - 大文件处理
   - 内存使用监控
   - 帧提取速度

---

## 常见问题 (FAQ)

### Q: 如何添加新的 LLM 提供商？

1. 继承 `LLMClient` 基类
2. 实现 `generate()` 方法
3. 在 `cli.py` 的 `create_client()` 中添加分支
4. 更新 `default_config.json`

### Q: 如何自定义提示词？

1. 创建自定义提示词目录
2. 复制 `prompts/frame_analysis/` 结构
3. 修改提示词文件
4. 在配置中设置 `prompt_dir`

### Q: 为什么音频提取失败？

- 检查 FFmpeg 是否安装：`ffmpeg -version`
- 确认视频包含音频流
- 查看日志：`--log-level DEBUG`

### Q: 如何优化内存使用？

- 减少 `frames_per_minute`
- 使用 `--max-frames` 限制处理帧数
- 不使用 `--keep-frames`
- 选择较小的 Whisper 模型（tiny/base/small）

### Q: 如何从中断处继续？

使用 `--start-stage` 参数：
- `--start-stage 2`：跳过帧提取，从分析开始
- `--start-stage 3`：跳过提取和分析，仅重建描述

---

## 相关文件清单

### 核心文件

```
video_analyzer/
├── __init__.py              # 包初始化
├── cli.py                   # CLI 入口（223 行）
├── config.py                # 配置管理（129 行）
├── analyzer.py              # 视频分析器（125 行）
├── audio_processor.py       # 音频处理（158 行）
├── frame.py                 # 帧提取（114 行）
├── prompt.py                # 提示词加载（101 行）
├── clients/
│   ├── __init__.py
│   ├── llm_client.py        # 客户端基类（19 行）
│   ├── ollama.py            # Ollama 客户端（59 行）
│   └── generic_openai_api.py # OpenAI API 客户端（131 行）
├── config/
│   └── default_config.json  # 默认配置
└── prompts/
    └── frame_analysis/
        ├── frame_analysis.txt  # 帧分析提示词
        └── describe.txt        # 视频描述提示词
```

### 配置文件

- `config/default_config.json`：默认配置（包内）
- `config/config.json`：用户配置（可选）

### 提示词文件

- `prompts/frame_analysis/frame_analysis.txt`：逐帧分析指令
- `prompts/frame_analysis/describe.txt`：视频重建指令

---

## 开发注意事项

### 代码规范

- 单文件不超过 400 行（当前最大：cli.py 223 行）
- 使用类型提示
- 添加 docstring
- 使用 logging 而非 print

### 依赖管理

- 核心依赖保持最小化
- 可选依赖通过 try-except 处理
- FFmpeg 作为外部依赖

### 错误处理

- 使用 try-except 捕获异常
- 记录详细错误日志
- 提供有用的错误消息
- 支持优雅降级（如音频提取失败时继续）

### 性能考虑

- 帧提取使用自适应采样
- 音频转录支持 VAD 过滤
- LLM 调用支持重试机制
- 临时文件自动清理

---

## 下一步改进建议

1. **测试覆盖**：
   - 添加完整的单元测试套件
   - 集成测试自动化
   - 性能基准测试

2. **功能增强**：
   - 支持批量视频处理
   - 添加进度条显示
   - 支持视频流输入
   - 缓存机制避免重复处理

3. **文档完善**：
   - API 文档生成（Sphinx）
   - 更多使用示例
   - 故障排除指南

4. **性能优化**：
   - 并行帧分析
   - GPU 加速音频处理
   - 增量处理大文件
