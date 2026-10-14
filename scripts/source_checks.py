from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parents[1]
results={}
for name,args in [("source-typecheck",["pnpm.cmd","typecheck"]),("source-unit-tests",["pnpm.cmd","test"])]:
    with (root/"logs"/(name+".log")).open("w",encoding="utf8") as out:
        p=subprocess.run(args,cwd="E:/WorthPath",stdout=out,stderr=subprocess.STDOUT)
    results[name]={"exitCode":p.returncode,"log":"logs/"+name+".log"}
(root/"docs/source-checks.json").write_text(json.dumps(results,indent=2))
print(results)
