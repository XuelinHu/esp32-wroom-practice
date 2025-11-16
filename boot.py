# 在上电启动时执行：把 /base 和 /examples 放进模块搜索路径
import sys
for p in ("/base", "/examples"):
    if p not in sys.path:
        sys.path.append(p)
        print(f"load module {p} done")
import esp
esp.osdebug(None)  # 关掉调试输出，可选

print("Boot OK")
