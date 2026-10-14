from pathlib import Path
import re
from urllib.parse import urlsplit
source=Path('E:/WorthPath')
env=(source/'apps/api/.env').read_text(encoding='utf-8-sig')
value=re.search(r'^DATABASE_URL=(.*)$',env,re.M).group(1).strip().strip(chr(34)).strip(chr(39))
u=urlsplit(value)
print({'database_has_test_marker':bool(re.search('test|dev|local',u.path,re.I)),'loopback':u.hostname in ('localhost','127.0.0.1'),'development':bool(re.search(r'^NODE_ENV=development\s*$',env,re.M))})
