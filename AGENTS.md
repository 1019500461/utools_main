# 项目约束

完成修改后，需使用本地 Python 环境中的 Playwright 执行校验，确保相关功能可正常运行。
ython Playwright 的 to_have_url 用字符串或 re.compile，不要用 lambda。
Naive UI 弹窗和页面常有重复 placeholder，测试定位要限定到 dialog/table 等作用域。
Mock API 解析查询参数要 URL decode，尤其是中文角色名。
Windows 后台启动 Vite 优先用 Start-Job；Start-Process 可能被 PATH/path 环境变量冲突卡住。



# fastapi项目结构 
fastapi_project/
├── app/
│   ├── __init__.py
│   ├── main.py                # 项目入口
│   ├── core/                  # 全局核心配置
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── security.py
│   │   └── exceptions.py
│   │   ├── .env
│   ├── db/                    # 数据库连接与会话
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── session.py
│   ├── common/                # 公共工具、通用依赖
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   └── utils.py
│   └── modules/               # 业务模块聚合目录
│       ├── __init__.py
│       ├── user/              # 用户模块
│       │   ├── __init__.py
│       │   ├── api.py         # 接口路由
│       │   ├── models.py      # 数据库模型
│       │   ├── schemas.py     # 请求响应校验
│       │   └── service.py     # 业务逻辑
│       └── role/             # 商品模块，按需新增
│           ├── __init__.py
│           ├── api.py
│           ├── models.py
│           ├── schemas.py
│           └── service.py

├── requirements.txt
└── README.md