# main.py
# 选择要运行的示例：distance / rotary / laser / light / lcd1602 / gear
DEMO = "phonotelemeter"

if DEMO == "phonotelemeter":
    import examples.phonotelemeter as app
elif DEMO == "rotary":
    import examples.rotary as app
# ... 省略其它分支

# app 模块 import 后即进入循环；如需统一入口，可在各示例末尾提供 run() 函数再调用
# app.run()