本地YOLO API服务是牧野系统的核心推理引擎，提供高性能害虫识别能力。该服务采用FastAPI框架构建，集成了Ultralytics YOLO模型，支持批量图像处理、多维度安全控制和流量限制机制，通过标准化REST接口为上游决策层提供可靠的视觉识别能力。

## 服务架构与核心组件

```mermaid
graph TB
    subgraph "客户端层"
        A[ImageProcessor<br/>图像处理器]
    end
    
    subgraph "API网关层"
        B[FastAPI Application<br/>/detect /health]
        C[InMemoryRateLimiter<br/>限流器]
        D[IP Whitelist<br/>IP白名单]
        E[API Key Auth<br/>密钥认证]
    end
    
    subgraph "服务层"
        F[LocalYoloApiService<br/>核心服务]
        G[Threading.Lock<br/>推理锁]
    end
    
    subgraph "推理层"
        H[UltralyticsPredictor<br/>预测器封装]
        I[YOLO Model<br/>Ultralytics引擎]
    end
    
    subgraph "配置层"
        J[yolo_config.yaml<br/>配置文件]
        K[环境变量<br/>.env]
    end
    
    A -->|HTTP POST| B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    J --> F
    K --> F
```

服务架构遵循分层设计原则，从客户端请求到模型推理形成清晰的调用链路。**InMemoryRateLimiter**基于滑动时间窗口算法实现请求频率控制，防止突发流量冲击推理引擎；**IP白名单与API Key双重认证机制**确保只有授权客户端能够访问服务；**线程锁（Threading.Lock）**将YOLO推理序列化，避免多线程并发导致的GPU资源竞争和内存溢出问题。

Sources: [modules/local_yolo_api.py](modules/local_yolo_api.py#L133-L276)

## 配置管理与环境变量

配置系统采用分层加载策略：YAML文件提供基础默认值，环境变量实现运行时覆盖，两者通过`load_local_yolo_settings()`函数合并为最终的`LocalYoloSettings`数据类实例。这种设计既保证了开发环境的配置简洁性，又满足生产环境的灵活定制需求。

| 配置项 | YAML路径 | 环境变量 | 默认值 | 说明 |
|--------|----------|----------|--------|------|
| 监听地址 | `local_api.host` | `YOLO_LOCAL_HOST` | `127.0.0.1` | API服务绑定地址 |
| 监听端口 | `local_api.port` | `YOLO_LOCAL_PORT` | `8010` | API服务监听端口 |
| 模型路径 | `local_api.model_path` | `YOLO_LOCAL_MODEL_PATH` | `models/best.pt` | YOLO权重文件路径 |
| 计算设备 | `local_api.device` | `YOLO_LOCAL_DEVICE` | `auto` | CPU/cuda/auto |
| 批量大小 | `local_api.max_batch_size` | - | `4` | 单次最大图片数量 |
| API密钥 | - | `YOLO_API_KEY` | 空字符串 | 为空则禁用认证 |
| IP白名单 | - | `YOLO_ALLOWED_IPS` | 空列表 | 逗号分隔，支持CIDR |
| 限流阈值 | - | `YOLO_RATE_LIMIT_PER_MINUTE` | `120` | 每分钟最大请求数 |

环境变量优先级高于YAML配置，这允许运维人员在容器编排平台（如Kubernetes）中通过ConfigMap或Secret动态注入配置，无需修改代码或重建镜像。**IP白名单支持CIDR格式**（如`192.168.1.0/24`），适合内网部署场景；**API Key为空时自动跳过认证检查**，简化开发环境启动流程。

Sources: [config/yolo_config.yaml](config/yolo_config.yaml#L1-L13), [.env.example](.env.example#L1-L8), [modules/local_yolo_api.py](modules/local_yolo_api.py#L234-L259)

## 安全认证机制

服务实现了三层安全防护：**IP白名单过滤**、**API Key认证**、**请求限流**。三层检查按顺序执行，任一层失败立即返回HTTP错误响应，避免不必要的计算资源消耗。

```python
# IP白名单验证逻辑（支持单IP和CIDR网段）
def ensure_ip_allowed(self, client_ip: str) -> None:
    if not self.settings.allowed_ips:
        return  # 白名单为空则允许所有IP
    address = ipaddress.ip_address(client_ip)
    for item in self.settings.allowed_ips:
        if "/" in item:
            if address in ipaddress.ip_network(item, strict=False):
                return  # CIDR匹配成功
        elif address == ipaddress.ip_address(item):
            return  # 精确匹配成功
    raise HTTPException(status_code=403, detail=f"客户端 IP {client_ip} 不在白名单中")
```

API Key认证支持两种传递方式：**HTTP Authorization头**（Bearer Token格式）和**X-API-Key自定义头**。这种双通道设计兼容不同客户端库的认证习惯——Web前端通常使用Authorization头，而服务端脚本可能更倾向于简洁的X-API-Key头。**限流器基于滑动窗口算法**，每个客户端IP维护独立的请求时间戳队列，窗口外的时间戳自动清理，超出限制立即返回429状态码。

Sources: [modules/local_yolo_api.py](modules/local_yolo_api.py#L206-L231), [modules/local_yolo_api.py](modules/local_yolo_api.py#L50-L64)

## 推理流程与批量处理

```mermaid
flowchart TD
    A[客户端 POST /detect] --> B{验证图片数量}
    B -->|超过限制| C[返回 400 错误]
    B -->|数量合法| D[创建临时目录]
    D --> E[持久化上传文件]
    E --> F[调用 predictor.predict]
    F --> G{Ultralytics推理}
    G --> H[序列化检测结果]
    H --> I[清理临时文件]
    I --> J[返回JSON响应]
    G -->|推理失败| K[异常向上传播]
```

核心推理方法`detect()`采用**临时目录隔离策略**：每次请求创建独立的临时文件夹（前缀`muye_yolo_`），持久化上传的图片文件，推理完成后由操作系统自动清理。这种设计避免了文件名冲突和内存溢出风险，特别适合处理大尺寸无人机图像。**批量处理受`max_batch_size`限制**（默认4张），防止单次请求占用过多GPU显存导致OOM错误。

UltralyticsPredictor封装了YOLO模型的复杂初始化逻辑和结果序列化过程。**推理参数动态配置**：`confidence_threshold`控制检测置信度过滤，`device`参数指定计算设备（auto/cpu/cuda:0），`verbose=False`关闭控制台输出以提升性能。检测结果标准化为包含`pest_type`（害虫类型）、`confidence`（置信度）、`position`（边界框坐标）的字典列表，确保上游消费者无需关心底层模型实现细节。

Sources: [modules/local_yolo_api.py](modules/local_yolo_api.py#L146-L184), [modules/local_yolo_api.py](modules/local_yolo_api.py#L66-L131)

## API接口规范

服务暴露两个REST端点：**健康检查**和**害虫检测**。健康检查接口用于容器编排平台的存活探针和就绪探针，害虫检测接口是核心业务入口。

### 健康检查接口

```http
GET /health HTTP/1.1
Host: 127.0.0.1:8010

# 响应示例
{
  "status": "ok",
  "model_path": "models/best.pt",
  "max_batch_size": 4
}
```

### 害虫检测接口

```http
POST /detect HTTP/1.1
Host: 127.0.0.1:8010
Authorization: Bearer muye-local-yolo-token
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="images"; filename="leaf1.jpg"
Content-Type: image/jpeg

[binary image data]
------WebKitFormBoundary
Content-Disposition: form-data; name="images"; filename="leaf2.jpg"
Content-Type: image/jpeg

[binary image data]
------WebKitFormBoundary
Content-Disposition: form-data; name="confidence_threshold"

0.35
------WebKitFormBoundary--

# 响应示例
{
  "request_id": "req-20240115-abc123",
  "model_path": "models/best.pt",
  "results": [
    {
      "image": "leaf1.jpg",
      "detections": [
        {
          "pest_type": "rice-planthopper",
          "confidence": 0.9124,
          "position": {"x1": 120.5, "y1": 85.3, "x2": 245.8, "y2": 198.6}
        }
      ]
    },
    {
      "image": "leaf2.jpg",
      "detections": []
    }
  ]
}
```

请求参数支持**多文件并发上传**（通过`images`字段重复提交）和**动态置信度阈值**（`confidence_threshold`，默认0.25）。响应结构包含请求追踪ID、模型路径和标准化检测结果数组。**空检测结果返回空数组**而非null，保证上游消费者的一致性处理逻辑。

Sources: [modules/local_yolo_api.py](modules/local_yolo_api.py#L279-L301)

## 与图像处理器的集成

ImageProcessor模块作为本地YOLO API的标准客户端，封装了HTTP请求构建、响应解析和错误处理逻辑。**分块批量提交机制**（`chunked`函数）自动将大批量图片拆分为多个小批次，每批次不超过`batch_size`配置值，平衡网络传输效率和服务端处理压力。

```python
# ImageProcessor 的批量检测流程
async def detect_pests_batch(self, image_paths, request_id, client_ip):
    results = {str(path): [] for path in image_paths}
    for batch in chunked(targets, self.batch_size):
        batch_result = await self._submit_batch(batch, request_id, client_ip)
        results.update(batch_result)
    return results
```

响应规范化逻辑（`_normalize_payload`方法）兼容多种返回格式：标准`{"results": [...]}`结构、简化的`{"detections": [...]}`单图格式、以及直接的数组格式。**字段映射容错机制**支持`pest_type`/`label`/`class_name`/`name`等多种害虫类型字段名，`position`/`bbox`/`box`等边界框字段名，确保与不同版本YOLO服务的兼容性。

Sources: [modules/image_processor.py](modules/image_processor.py#L50-L127), [modules/image_processor.py](modules/image_processor.py#L128-L185)

## 服务启动与部署

服务通过`yolo_api.py`入口脚本启动，支持命令行参数覆盖配置文件。**Uvicorn ASGI服务器**提供高性能异步处理能力，适合I/O密集型的图像上传场景。

```bash
# 使用默认配置启动
python yolo_api.py

# 通过命令行参数覆盖配置
python yolo_api.py --host 0.0.0.0 --port 9000

# 通过环境变量定制配置
export YOLO_LOCAL_HOST=0.0.0.0
export YOLO_LOCAL_PORT=9000
export YOLO_API_KEY=secure-production-token
export YOLO_ALLOWED_IPS=10.0.0.0/8,172.16.0.0/12
python yolo_api.py
```

生产部署建议：**使用进程管理器**（如systemd、supervisor）守护进程；**配置反向代理**（Nginx）处理SSL终止和请求路由；**设置GPU资源限制**（Docker GPU调度）避免资源争抢；**监控健康检查端点**实现自动故障恢复。模型文件应放置在`models/`目录下，首次启动会加载模型到内存，后续推理复用已加载的模型实例。