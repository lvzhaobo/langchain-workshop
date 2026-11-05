from fastapi.staticfiles import StaticFiles
import os

# 在 main.py 中添加静态文件服务
# 将以下代码添加到 main.py 的 app 创建之后

# 获取前端目录路径
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

# 如果前端目录存在，挂载静态文件
if os.path.exists(frontend_path):
    app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")

# 访问地址：http://localhost:8000/frontend/index.html