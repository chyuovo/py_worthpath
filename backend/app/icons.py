# 图标处理：兼容静态图片、白底透明化、私有共享权限和本地持久化。
import io,hashlib,os,re
from pathlib import Path
from PIL import Image,ImageOps
from sqlalchemy import select,or_,func
from fastapi.responses import Response
from .common import *
from .models import Icon
from .config import ROOT
def normalize(data,preserve_white=False):
    if not data or len(data)>2*1024*1024:fail("图标不能超过 2 MB")
    try:
        image=Image.open(io.BytesIO(data))
        if image.format not in ("PNG","JPEG","WEBP") or getattr(image,"n_frames",1)>1 or image.width*image.height>16000000:raise ValueError()
        image=ImageOps.exif_transpose(image);image.thumbnail((256,256),Image.Resampling.LANCZOS);image=image.convert("RGBA")
        if not preserve_white:
            image.putdata([(r,g,b,0 if min(r,g,b)>=245 and max(r,g,b)-min(r,g,b)<=8 else a) for r,g,b,a in image.getdata()])
        output=io.BytesIO();image.save(output,format="PNG");return output.getvalue()
    except Exception:fail("请选择有效的静态 PNG、JPG 或 WebP 图片")
def persist(hash,data):
    folder=os.getenv("ICON_STORAGE_DIR","").strip()
    if not folder:return
    path=Path(folder)
    if not path.is_absolute():path=ROOT/path
    path.mkdir(parents=True,exist_ok=True)
    target=path/(hash+".png")
    if not target.exists() or target.read_bytes()!=data:
        temp=path/(hash+".tmp");temp.write_bytes(data);temp.replace(target)
def upload(s,r,body):
    raw=body.get("_file")
    name=body.get("name","").strip();shared=body.get("shared","false")
    if set(body)-{"_file","name","shared","confirmed"} or not 1<=len(name)<=100 or shared not in ("true","false"):fail("图标参数无效")
    shared=shared=="true"
    if shared and (not re.search(r"[\u3400-\u9fff]",name) or body.get("confirmed")!="true"):fail("共享图标须填写中文名称并明确确认公开给所有用户")
    if not raw:fail("请选择图标文件")
    data=normalize(raw);hash=hashlib.sha256(data).hexdigest();persist(hash,data)
    icon=one(s,Icon,ownerId=r.userId,hash=hash,shared=shared)
    if not icon:icon=Icon(ownerId=r.userId,hash=hash,shared=shared,name=name,data=data);s.add(icon);s.flush()
    return dict(id=icon.id,name=icon.name,shared=icon.shared)
def visible(s,r,id):
    icon=s.scalar(select(Icon).where(Icon.id==id,or_(Icon.shared.is_(True),Icon.ownerId==r.userId)))
    if not icon:fail("图标不存在",404)
    return icon
def dispatch(s,r,request,response,body):
    path=request.scope["route"].path
    if path=="/api/icons":
        q=request.query_params.get("q","").strip()
        try:page=int(request.query_params.get("page",1));assert 1<=page<=100000 and len(q)<=100
        except (ValueError,AssertionError):fail("图标查询参数无效")
        where=[or_(Icon.shared.is_(True),Icon.ownerId==r.userId),Icon.name.contains(q,autoescape=True)]
        items=s.scalars(select(Icon).where(*where).order_by(Icon.name,Icon.id).offset((page-1)*60).limit(60))
        return dict(items=[dict(id=i.id,name=i.name,shared=i.shared) for i in items],total=s.scalar(select(func.count()).select_from(Icon).where(*where)),page=page)
    if path=="/api/icons/{id}/image":
        icon=visible(s,r,request.path_params["id"]);persist(icon.hash,bytes(icon.data));return Response(bytes(icon.data),media_type="image/png",headers={"X-Content-Type-Options":"nosniff"})
    if path=="/api/icons/upload":return upload(s,r,body)
    return NotImplemented
