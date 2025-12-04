[根目录](/home/nano/桌面/openProject/video-analyzer/CLAUDE.md) > **video-analyzer-ui**

# video-analyzer-ui Web 界面模块

## 变更记录 (Changelog)

### 2025-12-04
- 初始化 UI 模块文档
- 完成组件分析

---

## 模块职责

video-analyzer-ui 是 video-analyzer 的 Web 界面，提供：
- 友好的视频上传界面
- 实时分析进度显示
- 参数配置表单
- 结果下载功能
- 会话管理与清理

---

## 入口与启动

### 主入口点

**文件**：`video_analyzer_ui/server.py`
**命令**：`video-analyzer-ui`（通过 pyproject.toml 注册）

```python
# 入口函数
def main():
    # 1. 解析命令行参数
    # 2. 配置日志
    # 3. 检查 video-analyzer 是否安装
    # 4. 启动 Flask 服务器
```

### 启动命令

```bash
# 开发模式
video-analyzer-ui --dev

# 生产模式
video-analyzer-ui --host 0.0.0.0 --port 5000

# 带日志文件
video-analyzer-ui --dev --log-file debug.log
```

**命令行参数**：
- `--host`：绑定地址（默认：localhost）
- `--port`：端口号（默认：5000）
- `--dev`：开发模式（自动重载、调试日志）
- `--log-file`：日志文件路径

---

## 对外接口

### HTTP API 端点

#### 1. 主页

```
GET /
返回：HTML 页面（index.html）
```

#### 2. 上传视频

```
POST /upload
Content-Type: multipart/form-data

参数：
  - video: 视频文件（.mp4, .avi, .mov, .mkv）

返回：
{
  "session_id": "uuid",
  "message": "File uploaded successfully"
}

错误：
  400 - 无文件/文件类型无效
  500 - 服务器错误
```

#### 3. 开始分析

```
POST /analyze/<session_id>
Content-Type: application/x-www-form-urlencoded

参数（所有可选）：
  - client: ollama | openai_api
  - model: 模型名称
  - api-key: API 密钥
  - api-url: API URL
  - whisper-model: Whisper 模型大小
  - prompt: 自定义问题
  - max-frames: 最大帧数
  - keep-frames: 保留帧（标志）
  - log-level: 日志级别

返回：
{
  "message": "Analysis started"
}

错误：
  404 - 会话不存在
```

#### 4. 流式输出

```
GET /analyze/<session_id>/stream
返回：Server-Sent Events (SSE)

事件格式：
data: 日志行\n\n
data: Analysis completed successfully\n\n
data: Analysis failed\n\n

错误：
  404 - 会话不存在
  400 - 分析未启动
```

#### 5. 获取结果

```
GET /results/<session_id>
返回：application/json（下载 analysis.json）

错误：
  404 - 会话不存在/结果文件不存在
  500 - 文件访问错误
```

#### 6. 清理会话

```
POST /cleanup/<session_id>
返回：
{
  "message": "Session cleaned up successfully"
}

错误：
  404 - 会话不存在
  500 - 清理错误
```

---

## 关键依赖与配置

### 外部依赖

```toml
[project.dependencies]
flask>=3.0.0              # Web 框架
video-analyzer>=0.1.0     # 核心分析引擎
werkzeug>=3.0.0           # WSGI 工具库
```

### 系统要求

- Python 3.8+
- video-analyzer 包已安装
- FFmpeg（video-analyzer 依赖）

### 目录结构

```
video-analyzer-ui/
├── video_analyzer_ui/
│   ├── __init__.py
│   ├── server.py           # Flask 服务器（300 行）
│   ├── templates/
│   │   └── index.html      # 主页模板
│   └── static/
│       ├── css/
│       │   └── styles.css  # 样式表
│       └── js/
│           └── main.js     # 前端逻辑
├── pyproject.toml          # 项目配置
├── requirements.txt        # 依赖列表
├── README.md              # 模块文档
└── MANIFEST.in            # 打包清单
```

---

## 数据模型

### 会话数据结构

```python
sessions = {
    "session_id": {
        "video_path": str,      # 上传视频路径
        "results_dir": str,     # 结果目录
        "filename": str,        # 原始文件名
        "output_dir": str,      # 输出目录（分析后设置）
        "cmd": List[str]        # 执行的命令（分析后设置）
    }
}
```

### 临时文件管理

```
/tmp/video-analyzer-ui/
├── uploads/
│   └── <session_id>/
│       └── <filename>      # 上传的视频
└── results/
    └── <session_id>/
        └── analysis.json   # 分析结果
```

---

## 核心组件详解

### VideoAnalyzerUI 类

**文件**：`server.py`

**职责**：
- Flask 应用管理
- 路由注册
- 会话管理
- 临时文件处理

**初始化**：
```python
def __init__(self, host='localhost', port=5000, dev_mode=False):
    self.app = Flask(__name__)
    self.host = host
    self.port = port
    self.dev_mode = dev_mode
    self.sessions = {}  # 会话字典

    # 临时目录
    self.tmp_root = Path(tempfile.gettempdir()) / 'video-analyzer-ui'
    self.uploads_dir = self.tmp_root / 'uploads'
    self.results_dir = self.tmp_root / 'results'
```

### 关键方法

#### 1. 文件上传处理

```python
@self.app.route('/upload', methods=['POST'])
def upload_file():
    # 1. 验证文件存在和类型
    # 2. 创建会话 ID（UUID）
    # 3. 创建会话目录
    # 4. 保存文件（使用 secure_filename）
    # 5. 存储会话信息
    # 6. 返回会话 ID
```

**安全措施**：
- 使用 `secure_filename()` 防止路径遍历
- 文件类型白名单验证
- 会话隔离目录

#### 2. 分析执行

```python
@self.app.route('/analyze/<session_id>', methods=['POST'])
def analyze(session_id):
    # 1. 验证会话存在
    # 2. 构建 video-analyzer 命令
    # 3. 添加表单参数
    # 4. 设置输出目录
    # 5. 存储命令到会话
    # 6. 返回成功响应
```

**命令构建**：
```python
cmd = ['video-analyzer', session['video_path']]

# 添加参数
for param, value in request.form.items():
    if value:
        if param in ['keep-frames', 'dev']:
            cmd.append(f'--{param}')
        else:
            cmd.extend([f'--{param}', value])

# 添加输出目录
cmd.extend(['--output', str(results_dir)])
```

#### 3. 实时输出流

```python
@self.app.route('/analyze/<session_id>/stream')
def stream_output(session_id):
    def generate_output():
        # 1. 启动 subprocess
        # 2. 逐行读取 stdout
        # 3. 以 SSE 格式发送
        # 4. 处理完成/错误状态

        process = subprocess.Popen(
            session['cmd'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        for line in process.stdout:
            yield f"data: {line.strip()}\n\n"

    return Response(
        generate_output(),
        mimetype='text/event-stream'
    )
```

**SSE（Server-Sent Events）**：
- 单向服务器推送
- 自动重连
- 文本格式：`data: <message>\n\n`

#### 4. 结果下载

```python
@self.app.route('/results/<session_id>')
def get_results(session_id):
    # 1. 验证会话和结果目录
    # 2. 查找 analysis.json
    # 3. 处理默认 output/ 目录（兼容性）
    # 4. 使用 send_file 返回
```

**文件查找逻辑**：
1. 检查会话结果目录
2. 检查默认 `output/` 目录
3. 如果在默认目录找到，移动到会话目录

#### 5. 会话清理

```python
@self.app.route('/cleanup/<session_id>', methods=['POST'])
def cleanup_session(session_id):
    # 1. 删除上传目录及文件
    # 2. 删除结果目录及文件
    # 3. 删除默认 output/ 目录（如果存在）
    # 4. 从会话字典移除
```

---

## 前端架构

### HTML 模板（templates/index.html）

**主要区域**：
1. 文件上传区（拖放支持）
2. 参数配置表单
3. 实时日志输出
4. 结果下载按钮

### JavaScript（static/js/main.js）

**核心功能**：
```javascript
// 1. 文件上传
async function uploadVideo(file) {
    const formData = new FormData();
    formData.append('video', file);
    const response = await fetch('/upload', {
        method: 'POST',
        body: formData
    });
    return response.json();
}

// 2. 开始分析
async function startAnalysis(sessionId, params) {
    const formData = new URLSearchParams(params);
    await fetch(`/analyze/${sessionId}`, {
        method: 'POST',
        body: formData
    });
}

// 3. 监听输出流
function streamOutput(sessionId) {
    const eventSource = new EventSource(`/analyze/${sessionId}/stream`);
    eventSource.onmessage = (event) => {
        appendLog(event.data);
    };
}

// 4. 下载结果
function downloadResults(sessionId) {
    window.location.href = `/results/${sessionId}`;
}

// 5. 清理会话
async function cleanup(sessionId) {
    await fetch(`/cleanup/${sessionId}`, {
        method: 'POST'
    });
}
```

### CSS 样式（static/css/styles.css）

**设计特点**：
- 响应式布局
- 拖放区域高亮
- 日志滚动显示
- 加载状态指示

---

## 测试与质量

### 手动测试流程

1. **上传测试**：
   ```bash
   curl -X POST -F "video=@test.mp4" http://localhost:5000/upload
   ```

2. **分析测试**：
   ```bash
   curl -X POST http://localhost:5000/analyze/<session_id> \
        -d "client=ollama&model=llama3.2-vision"
   ```

3. **流式输出测试**：
   ```bash
   curl -N http://localhost:5000/analyze/<session_id>/stream
   ```

4. **结果下载测试**：
   ```bash
   curl -O http://localhost:5000/results/<session_id>
   ```

### 测试建议

1. **单元测试**：
   - 路由处理函数
   - 会话管理逻辑
   - 文件验证

2. **集成测试**：
   - 完整上传-分析-下载流程
   - 错误处理（无效文件、会话不存在）
   - 并发会话

3. **前端测试**：
   - 拖放上传
   - 表单验证
   - SSE 连接

---

## 常见问题 (FAQ)

### Q: 如何在生产环境部署？

**不推荐直接使用 Flask 开发服务器**，应使用 WSGI 服务器：

```bash
# 使用 Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 video_analyzer_ui.server:app

# 使用 uWSGI
pip install uwsgi
uwsgi --http 0.0.0.0:5000 --module video_analyzer_ui.server:app
```

### Q: 如何配置 Nginx 反向代理？

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

### Q: 临时文件何时清理？

- **手动清理**：用户点击清理按钮
- **自动清理**：需要实现定时任务（当前未实现）

**建议添加**：
```python
# 定期清理超过 24 小时的会话
import threading
import time

def cleanup_old_sessions():
    while True:
        time.sleep(3600)  # 每小时检查
        # 清理逻辑
```

### Q: 如何限制上传文件大小？

```python
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large'}), 413
```

### Q: 如何支持多用户并发？

当前实现支持多会话，但需要注意：
- 每个会话独立目录
- 资源限制（CPU、内存、磁盘）
- 考虑使用任务队列（Celery）

---

## 相关文件清单

```
video-analyzer-ui/
├── video_analyzer_ui/
│   ├── __init__.py              # 包初始化
│   ├── server.py                # Flask 服务器（300 行）
│   ├── templates/
│   │   └── index.html           # 主页模板
│   └── static/
│       ├── css/
│       │   └── styles.css       # 样式表
│       └── js/
│           └── main.js          # 前端逻辑
├── pyproject.toml               # 项目配置
├── requirements.txt             # 依赖列表
├── README.md                    # 模块文档
├── MANIFEST.in                  # 打包清单
└── .gitignore                   # Git 忽略规则
```

---

## 开发注意事项

### 安全考虑

1. **文件上传**：
   - 使用 `secure_filename()` 清理文件名
   - 文件类型白名单验证
   - 文件大小限制

2. **会话管理**：
   - 使用 UUID 防止会话 ID 猜测
   - 会话隔离目录
   - 定期清理过期会话

3. **命令执行**：
   - 参数验证
   - 使用 subprocess 而非 shell
   - 限制可执行命令

### 性能优化

1. **异步处理**：
   - 分析任务在后台运行
   - SSE 实时反馈进度

2. **资源管理**：
   - 限制并发分析数量
   - 临时文件自动清理
   - 磁盘空间监控

3. **缓存策略**：
   - 静态资源缓存
   - 结果文件缓存

### 错误处理

- 所有路由添加 try-except
- 详细日志记录
- 友好的错误消息
- 适当的 HTTP 状态码

---

## 下一步改进建议

1. **功能增强**：
   - 用户认证与授权
   - 历史记录查看
   - 批量上传处理
   - 实时进度百分比

2. **UI 改进**：
   - 更丰富的参数配置界面
   - 结果可视化（帧预览、时间轴）
   - 深色模式支持
   - 国际化（i18n）

3. **部署优化**：
   - Docker 容器化
   - Kubernetes 部署配置
   - 自动扩展支持
   - 健康检查端点

4. **监控与日志**：
   - 集成 Prometheus 指标
   - 结构化日志（JSON）
   - 错误追踪（Sentry）
   - 性能监控

5. **测试完善**：
   - 自动化测试套件
   - 端到端测试
   - 负载测试
   - 安全测试
