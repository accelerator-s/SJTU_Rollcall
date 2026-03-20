# 上海交通大学签到助手

SJTU 签到助手 —— 基于 FastAPI + Vue 3 + Element Plus 构建的二维码扫描签到工具。

## 功能概览

- **摄像头扫码** —— 浏览器调用摄像头实时扫描签到二维码
- **自动签到** —— 扫描到有效二维码后自动完成 jAccount 登录和签到流程
- **签到记录** —— 当前会话内的签到历史，成功/失败一目了然
- **统计面板** —— 实时统计签到成功、失败和扫码总数
- **配置文件** —— 在 JSON 配置文件中预设 jAccount 账号密码，无需每次输入

## 工作原理

1. 前端通过浏览器摄像头 API 实时扫描二维码
2. 检测到 `mlearning.sjtu.edu.cn` 签到链接后，将 URL 发送至后端
3. 后端使用预配置的 jAccount 凭据自动完成：
   - 访问签到链接，触发 jAccount 登录重定向
   - 获取并 OCR 识别验证码
   - 提交登录表单，获取 JWT 令牌
   - 调用签到 API 完成签到
4. 将签到结果返回前端展示

## 环境要求

- Python 3.11+
- pip
- 支持摄像头的浏览器（Chrome / Edge / Firefox）

## 安装

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Linux / macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

## 配置

编辑 `config/default_config.json`：

```json
{
    "jaccount": "your_jaccount",
    "password": "your_password",
    "service_port": 5000,
    "host": "0.0.0.0",
    "sign_domain": "https://mlearning.sjtu.edu.cn",
    "qr_url_prefix": "https://mlearning.sjtu.edu.cn/lms/mobile2/forscan/"
}
```

| 字段             | 默认值                                                         | 说明                     |
| ---------------- | -------------------------------------------------------------- | ------------------------ |
| `jaccount`       | `""`                                                           | jAccount 账号            |
| `password`       | `""`                                                           | jAccount 密码            |
| `service_port`   | `5000`                                                         | Web 服务端口             |
| `host`           | `"0.0.0.0"`                                                    | 监听地址                 |
| `sign_domain`    | `"https://mlearning.sjtu.edu.cn"`                              | 签到服务域名             |
| `qr_url_prefix`  | `"https://mlearning.sjtu.edu.cn/lms/mobile2/forscan/"`         | 有效签到链接前缀         |

## 启动

```bash
python -m backend.run
```

服务启动后，浏览器访问 `http://localhost:5000`。

## 使用方式

1. 在 `config/default_config.json` 中填入 jAccount 账号和密码
2. 启动服务
3. 浏览器打开应用，点击「开始扫码」按钮
4. 允许浏览器访问摄像头
5. 将摄像头对准签到二维码，系统自动完成签到

## 项目结构

```
SJTU_Rollcall/
├── backend/
│   ├── __init__.py
│   ├── app.py           # FastAPI 应用及签到逻辑
│   └── run.py            # 启动入口
├── config/
│   └── default_config.json   # 账号密码配置
├── frontend/
│   ├── index.html
│   ├── css/
│   │   ├── variables.css     # CSS 变量定义
│   │   ├── base.css          # 基础样式与动画
│   │   ├── layout.css        # 布局与组件样式
│   │   ├── scanner.css       # 扫码器样式
│   │   └── responsive.css    # 响应式适配
│   └── js/
│       ├── api.js            # Axios API 封装
│       └── app.js            # Vue 根实例
├── requirements.txt
└── README.md
```

## 技术栈

| 层级   | 技术                      |
| ------ | ------------------------- |
| 前端   | Vue 3 + Element Plus      |
| 后端   | FastAPI + Uvicorn         |
| 扫码   | html5-qrcode              |
| 验证码 | ddddocr                   |
| HTTP   | Requests + BeautifulSoup  |

## 注意事项

- 摄像头扫码需要 HTTPS 或 localhost 环境（浏览器安全策略限制）
- 验证码 OCR 存在识别失败的概率，失败时系统会自动提示，再次扫描即可重试
- 请妥善保管配置文件中的账号密码信息
