# 独立后端启动入口：只读取本目录配置，不依赖前端、pnpm 或源仓库。
from pathlib import Path
import sys,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import ROOT
if __name__=="__main__":
    import uvicorn
    uvicorn.run("app.main:app",host=os.getenv("API_HOST","0.0.0.0"),port=int(os.getenv("PORT","3100")),reload="--reload" in sys.argv,app_dir=str(ROOT))
