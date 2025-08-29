# Gemini API 代理服务
gemini api agent services

>gemini轮询密钥及轮询公共代理服务\
>Gemini Polling Key and Polling Public Proxy Service

一个高性能的 Gemini API 代理服务，支持代理地址和 API 密钥的自动轮询与故障转移。\
a high performance gemini api proxy service that supports automatic polling and failover of proxy addresses and api keys

## 功能特性

- 🔄 **自动轮询**：支持代理地址和 API 密钥的自动轮询
- 🔧 **故障转移**：遇到错误时自动切换到可用的代理和密钥组合
- 🛡️ **认证保护**：通过代理密钥限制访问权限
- 📊 **智能错误处理**：根据不同的错误类型采取不同的处理策略
- 📝 **详细日志**：提供详细的运行日志，便于监控和调试
- 🔄 **无缝切换**：在遇到错误时自动尝试所有可能的组合，直到成功

## 安装要求

- Python 3.7+
- Flask
- Requests

## 安装步骤

1. 克隆或下载本项目文件

2. 安装依赖：
```bash
pip install flask requests
```

3. 准备配置文件：
   - 创建 `proxy_urls.txt` 文件，每行一个代理 URL
   - 创建 `api_keys.txt` 文件，每行一个 Gemini API 密钥

4. 修改代码中的代理密钥（可选）：
   在代码中找到 `proxy_key = "your_proxy_secret_key"` 并更改为您自己的安全密钥

## 配置说明

### 代理 URL 文件格式 (proxy_urls.txt)
```
https://proxy1.example.com
https://proxy2.example.com
https://proxy3.example.com
```

### API 密钥文件格式 (api_keys.txt)
```
your_gemini_api_key_1
your_gemini_api_key_2
your_gemini_api_key_3
```

### 环境变量配置（可选）
您可以通过修改代码中的以下变量来定制代理程序：
- `proxy_urls_file`：代理 URL 文件路径
- `api_keys_file`：API 密钥文件路径
- `proxy_key`：代理程序的认证密钥

## 运行服务

```bash
python gemini_proxy.py
```

服务将在 `0.0.0.0:8000` 上启动。

## 客户端使用示例

### Python 客户端示例
```python
import requests

# 设置代理程序地址和密钥
PROXY_URL = "http://your-proxy-server:9000"
PROXY_KEY = "your_proxy_secret_key"

# 调用示例
response = requests.post(
    f"{PROXY_URL}/v1/models/gemini-pro:generateContent",
    json={
        "contents": [{
            "parts": [{
                "text": "写一个关于人工智能的简短段落"
            }]
        }]
    },
    headers={
        "Authorization": f"Bearer {PROXY_KEY}",
        "Content-Type": "application/json"
    }
)

print(response.json())
```

### cURL 示例
```bash
curl -X POST \
  http://your-proxy-server:9000/v1/models/gemini-pro:generateContent \
  -H "Authorization: Bearer your_proxy_secret_key" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{
      "parts": [{
        "text": "写一个关于人工智能的简短段落"
      }]
    }]
  }'
```

## API 端点

代理程序完全模拟 Gemini API 的接口，支持以下端点：

- `GET /v1/models` - 获取模型列表
- `GET /v1/models/{model_id}` - 获取特定模型信息
- `POST /v1/models/{model_name}:generateContent` - 生成内容
- `POST /v1/models/{model_name}:streamGenerateContent` - 流式生成内容

## 本代理程序错误处理策略

代理程序根据不同的错误类型采取不同的处理策略：

| 错误代码 | 处理方式 | 说明 |
|---------|---------|------|
| 200 | 成功返回 | 请求成功 |
| 429 | 切换密钥 | API 密钥额度用完，保留密钥但切换到下一个 |
| 400/401/403 | 删除并切换密钥 | API 密钥无效，删除当前密钥并切换到下一个 |
| 404 | 切换代理 | 代理 URL 不可用，切换到下一个代理 |
| 其他错误 | 切换代理 | 未知错误，默认切换到下一个代理 |

## 日志说明

代理程序提供详细的日志输出，包括：
- 初始化信息（代理 URL 和 API 密钥数量）
- 每次请求的详细信息
- 错误信息和处理过程
- 代理和密钥的切换记录

## 性能优化

- 使用线程安全的锁机制确保多线程环境下的安全操作
- 设置最大重试次数限制，防止无限循环
- 优化请求头处理，只保留必要的头部信息

## 故障排除

1. **401 认证错误**：检查代理密钥是否正确设置
2. **503 服务不可用**：检查代理 URL 和 API 密钥文件是否正确配置
3. **JSON 解析错误**：检查 Gemini API 返回的数据格式

## 注意事项

- 请确保代理 URL 是有效的 Gemini API 代理端点
- 定期检查 API 密钥文件，移除已失效的密钥
- 在生产环境中建议使用 WSGI 服务器（如 Gunicorn）部署

## 许可证

本项目采用 CC BY-NC 4.0 许可证。
