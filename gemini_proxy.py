import threading
import json
import requests
from flask import Flask, request, jsonify
from collections import deque
import logging
from typing import List, Dict, Optional, Tuple
import re
from urllib.parse import urlencode
import time

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class GeminiProxy:
    def __init__(self, proxy_urls_file: str, api_keys_file: str, proxy_key: str):
        # 读取代理URL列表
        with open(proxy_urls_file, 'r') as f:
            self.proxy_urls = deque([line.strip() for line in f if line.strip()])
        
        # 读取API密钥列表
        with open(api_keys_file, 'r') as f:
            self.api_keys = deque([line.strip() for line in f if line.strip()])
        
        self.proxy_key = proxy_key  # 代理程序的认证密钥
        self.current_proxy_url = self.proxy_urls[0] if self.proxy_urls else None
        self.current_api_key = self.api_keys[0] if self.api_keys else None
        
        # 用于线程安全的锁
        self.proxy_lock = threading.Lock()
        self.key_lock = threading.Lock()
        
        logger.info(f"初始化完成: {len(self.proxy_urls)} 个代理URL, {len(self.api_keys)} 个API密钥")
    
    def rotate_proxy(self) -> Optional[str]:
        """轮换到下一个代理URL"""
        with self.proxy_lock:
            if not self.proxy_urls:
                return None
            
            self.proxy_urls.rotate(-1)
            self.current_proxy_url = self.proxy_urls[0]
            logger.info(f"切换到新代理URL: {self.current_proxy_url}")
            return self.current_proxy_url
    
    def rotate_key(self, remove_current: bool = False) -> Optional[str]:
        """轮换到下一个API密钥，可选择删除当前密钥"""
        with self.key_lock:
            if not self.api_keys:
                return None
            
            if remove_current and self.current_api_key in self.api_keys:
                self.api_keys.remove(self.current_api_key)
                logger.info(f"移除无效密钥: {self.current_api_key}")
            
            if not self.api_keys:
                return None
                
            self.api_keys.rotate(-1)
            self.current_api_key = self.api_keys[0]
            logger.info(f"切换到新API密钥: {self.current_api_key}")
            return self.current_api_key
    
    def make_request(self, endpoint: str, data: Dict, headers: Dict) -> Tuple[Optional[Dict], int]:
        """向Gemini API发送请求，循环尝试直到成功"""
        max_retries = len(self.proxy_urls) * len(self.api_keys)
        retry_count = 0
        original_proxy = self.current_proxy_url
        original_key = self.current_api_key
        
        while retry_count < max_retries:
            if not self.current_proxy_url or not self.current_api_key:
                return {"error": "没有可用的代理URL或API密钥"}, 503
            
            # 构建URL，将API密钥作为查询参数
            base_url = f"{self.current_proxy_url.rstrip('/')}/{endpoint.lstrip('/')}"
            
            # 准备请求头 - 只保留必要的头
            api_headers = {}
            for key, value in headers.items():
                if key.lower() in ['content-type', 'accept', 'user-agent']:
                    api_headers[key] = value
            
            # 添加API密钥作为查询参数
            params = {'key': self.current_api_key}
            url = f"{base_url}?{urlencode(params)}"
            
            try:
                logger.info(f"尝试请求: {url}")
                response = requests.post(
                    url,
                    json=data,
                    headers=api_headers,
                    timeout=30
                )
                
                # 处理响应
                if response.status_code == 200:
                    try:
                        logger.info(f"请求成功: {self.current_proxy_url} + {self.current_api_key}")
                        return response.json(), 200
                    except json.JSONDecodeError:
                        logger.error(f"响应不是有效的JSON: {response.text}")
                        # 即使JSON解析失败，我们也返回这个响应
                        return {"raw_response": response.text}, 200
                
                # 处理错误
                elif response.status_code == 429:
                    logger.warning(f"API密钥额度已用完: {self.current_api_key}")
                    self.rotate_key(remove_current=False)
                    retry_count += 1
                    continue
                
                elif response.status_code in [400, 401, 403]:
                    logger.warning(f"API密钥无效: {self.current_api_key}, 状态码: {response.status_code}")
                    self.rotate_key(remove_current=True)
                    retry_count += 1
                    continue
                
                elif response.status_code == 404:
                    logger.warning(f"代理URL不可用: {self.current_proxy_url}")
                    self.rotate_proxy()
                    retry_count += 1
                    continue
                
                else:
                    logger.error(f"未知错误: {response.status_code}, {response.text}")
                    # 默认切换到下一个代理
                    self.rotate_proxy()
                    retry_count += 1
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常: {str(e)}")
                self.rotate_proxy()
                retry_count += 1
                continue
        
        # 如果所有尝试都失败，恢复原始设置并返回错误
        self.current_proxy_url = original_proxy
        self.current_api_key = original_key
        return {"error": "所有代理和密钥组合都尝试失败"}, 503

# 初始化代理
proxy_urls_file = "proxy_urls.txt"
api_keys_file = "api_keys.txt"
proxy_key = "your_proxy_secret_key"  # 请更改为安全的密钥

gemini_proxy = GeminiProxy(proxy_urls_file, api_keys_file, proxy_key)

def validate_proxy_key():
    """验证代理密钥"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False
    
    provided_key = auth_header[7:]  # 去掉 "Bearer " 前缀
    return provided_key == proxy_key

@app.route('/v1/models', methods=['GET'])
@app.route('/v1/models/<model_id>', methods=['GET'])
def models_endpoint(model_id=None):
    """处理模型列表请求"""
    # 验证代理密钥
    if not validate_proxy_key():
        return jsonify({"error": "未授权访问"}), 404
    
    # 转发请求到Gemini API
    endpoint = f"v1/models/{model_id}" if model_id else "v1/models"
    result, status_code = gemini_proxy.make_request(endpoint, {}, dict(request.headers))
    return jsonify(result), status_code

@app.route('/v1/models/<model_name>:generateContent', methods=['POST'])
@app.route('/v1/models/<model_name>/generateContent', methods=['POST'])
def generate_content_endpoint(model_name):
    """处理内容生成请求"""
    # 验证代理密钥
    if not validate_proxy_key():
        return jsonify({"error": "未授权访问"}), 404
    
    # 获取请求数据
    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({"error": "无效的JSON数据"}), 400
    
    # 转发请求到Gemini API
    endpoint = f"v1/models/{model_name}:generateContent"
    result, status_code = gemini_proxy.make_request(endpoint, data, dict(request.headers))
    return jsonify(result), status_code

@app.route('/v1/models/<model_name>:streamGenerateContent', methods=['POST'])
@app.route('/v1/models/<model_name>/streamGenerateContent', methods=['POST'])
def stream_generate_content_endpoint(model_name):
    """处理流式内容生成请求"""
    # 验证代理密钥
    if not validate_proxy_key():
        return jsonify({"error": "未授权访问"}), 404
    
    # 获取请求数据
    try:
        data = request.get_json()
    except Exception as e:
        return jsonify({"error": "无效的JSON数据"}), 400
    
    # 转发请求到Gemini API
    endpoint = f"v1/models/{model_name}:streamGenerateContent"
    result, status_code = gemini_proxy.make_request(endpoint, data, dict(request.headers))
    return jsonify(result), status_code

# 处理其他可能的端点
@app.route('/v1/<path:subpath>', methods=['POST', 'GET'])
def catch_all_endpoint(subpath):
    """处理其他API端点"""
    # 验证代理密钥
    if not validate_proxy_key():
        return jsonify({"error": "未授权访问"}), 404
    
    # 获取请求数据（如果是POST请求）
    data = {}
    if request.method == 'POST':
        try:
            data = request.get_json()
        except Exception as e:
            return jsonify({"error": "无效的JSON数据"}), 400
    
    # 转发请求到Gemini API
    endpoint = f"v1/{subpath}"
    result, status_code = gemini_proxy.make_request(endpoint, data, dict(request.headers))
    return jsonify(result), status_code

# 处理根路径和非法路径
@app.route('/', methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def invalid_path(path=None):
    """处理非法路径"""
    return jsonify({"error": "未找到路径"}), 404

if __name__ == '__main__':
    # 启动Flask应用，监听8000端口
    app.run(host='0.0.0.0', port=8000, threaded=True)
