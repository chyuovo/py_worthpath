# 显式初始化内置图标；固定 ID 与原项目一致，不触碰用户财务数据。
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import ROOT
from app.database import transaction
from app.models import Icon
from app.icons import persist,normalize
def seed():
    manifest=json.loads((ROOT/"assets/icons/sources.json").read_text(encoding="utf8"))
    with transaction() as s:
        for item in manifest:
            data=normalize((ROOT/"assets/icons"/item["file"]).read_bytes(),item.get("preserveWhite") is True)
            h=hashlib.sha256(("worthpath-builtin:"+item["name"]).encode()).hexdigest()
            id=h[:8]+"-"+h[8:12]+"-4"+h[13:16]+"-a"+h[17:20]+"-"+h[20:32]
            image_hash=hashlib.sha256(data).hexdigest()
            icon=s.get(Icon,id)
            if not icon:s.add(Icon(id=id,name=item["name"],shared=True,data=data,hash=image_hash))
            else:icon.data=data;icon.hash=image_hash
            persist(image_hash,data)
    print("Shared icon catalog ready:",len(manifest),"icons")
if __name__=="__main__":
    try:seed()
    except Exception:
        print("图标初始化失败，请检查本地配置、数据库及图片目录权限。")
        raise SystemExit(1)
