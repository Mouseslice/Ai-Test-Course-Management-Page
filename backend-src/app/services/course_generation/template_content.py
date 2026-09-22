"""模板内置内容库：本地生成器的语料来源。

替代原「多智能体 + LLM」生成链路的内容来源。每个模板内置：
  - course 元信息（标题/简介/课程类型/判题运行时）；
  - 5 章章节语料（每章 2 个小节，小节正文为 markdown，构成一个 block）；
  - 每章一道测试题（description_md / start_code / checkpoints，按模板范式）；
  - 全局知识图谱（章节节点 + 知识点节点 + 前置依赖边）。

本地生成器（local_generator.py）从 learning_path 提取章节标题，优先覆盖
这里的默认标题；语料与测试题则固定取自本库，保证输出确定、秒级完成。
"""
from typing import Any, Dict, List

# ---------------------------------------------------------------- web-frontend

_WEB_FRONTEND: Dict[str, Any] = {
    "title": "Web 前端开发入门",
    "description": "从 HTML 结构、CSS 样式到 JavaScript 交互，零基础掌握网页开发核心技能。",
    "course_type": "web",
    "allowed_runtimes": ["web"],
    "chapters": [
        {
            "key": "ch1",
            "title": "HTML 基础入门",
            "description": "认识 HTML 文档结构与常用标签。",
            "sections": [
                {
                    "title": "HTML 文档结构",
                    "body_md": (
                        "HTML（超文本标记语言）是网页的骨架。一个完整的 HTML 文档以 `<!DOCTYPE html>` "
                        "声明开头，由 `<html>` 包裹，内部包含 `<head>`（元信息）与 `<body>`（页面内容）两部分。\n\n"
                        "```html\n<!DOCTYPE html>\n<html lang=\"zh-CN\">\n  <head>\n"
                        "    <meta charset=\"UTF-8\">\n    <title>我的第一个网页</title>\n  </head>\n"
                        "  <body>\n    <h1>你好，世界！</h1>\n  </body>\n</html>\n```\n\n"
                        "`<head>` 里的 `<meta charset>` 声明字符编码，`<title>` 显示在浏览器标签页；"
                        "用户在页面上看到的所有内容都写在 `<body>` 中。"
                    ),
                },
                {
                    "title": "常用 HTML 标签",
                    "body_md": (
                        "内容型标签负责组织页面信息：`<h1>`~`<h6>` 是分级标题，`<p>` 是段落，`<a>` 是超链接，"
                        "`<img>` 是图片，`<ul>/<ol>/<li>` 是无序/有序列表。\n\n"
                        "```html\n<h2>前端三件套</h2>\n<ul>\n  <li>HTML：结构</li>\n  <li>CSS：样式</li>\n"
                        "  <li>JavaScript：行为</li>\n</ul>\n<a href=\"https://developer.mozilla.org\">MDN 文档</a>\n```\n\n"
                        "标签可以嵌套，浏览器按标签语义渲染，语义清晰的页面也更利于搜索引擎与无障碍阅读。"
                    ),
                },
            ],
            "test": {
                "title": "HTML 基础测验",
                "description_md": "补全页面，使其包含一个一级标题「我的网页」和一个段落「欢迎学习前端开发」。",
                "start_code": "<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset=\"UTF-8\">\n"
                              "    <title>我的网页</title>\n  </head>\n  <body>\n    <!-- 在此编写标题与段落 -->\n"
                              "  </body>\n</html>",
                "checkpoints": [
                    {
                        "name": "存在一级标题",
                        "type": "assert_element",
                        "selector": "h1",
                        "assertion_type": "exists",
                        "feedback": "需要添加 <h1> 标签",
                    },
                    {
                        "name": "标题文本正确",
                        "type": "assert_text_content",
                        "selector": "h1",
                        "assertion_type": "equals",
                        "value": "我的网页",
                        "feedback": "一级标题内容应为「我的网页」",
                    },
                    {
                        "name": "存在段落",
                        "type": "assert_element",
                        "selector": "p",
                        "assertion_type": "exists",
                        "feedback": "需要添加 <p> 段落标签",
                    },
                ],
            },
        },
        {
            "key": "ch2",
            "title": "HTML 表单与语义化",
            "description": "掌握表单元素与语义化标签，构建可用的页面结构。",
            "sections": [
                {
                    "title": "表单元素",
                    "body_md": (
                        "表单用于收集用户输入。`<form>` 是容器，内部常用的控件有：`<input>`（文本框/密码/单选框等）、"
                        "`<textarea>`（多行文本）、`<select>/<option>`（下拉框）、`<button>`（按钮）。\n\n"
                        "```html\n<form>\n  <label>用户名：<input type=\"text\" name=\"username\"></label>\n"
                        "  <label>密码：<input type=\"password\" name=\"password\"></label>\n"
                        "  <button type=\"submit\">登录</button>\n</form>\n```\n\n"
                        "`<label>` 与控件关联后可扩大点击区域，`type` 属性决定输入框的表现形态。"
                    ),
                },
                {
                    "title": "语义化标签",
                    "body_md": (
                        "HTML5 提供了一组表达「区域含义」的标签：`<header>` 页头、`<nav>` 导航、`<main>` 主内容、"
                        "`<section>` 区块、`<footer>` 页脚。它们让页面结构对开发者与机器都更可读。\n\n"
                        "```html\n<header><h1>网站标题</h1></header>\n<nav><a href=\"#\">首页</a></nav>\n"
                        "<main><section><h2>文章</h2></section></main>\n<footer>版权所有</footer>\n```"
                    ),
                },
            ],
            "test": {
                "title": "注册表单测验",
                "description_md": "创建一个注册表单，包含用户名输入框和提交按钮。",
                "start_code": "<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset=\"UTF-8\">\n    <title>注册</title>\n"
                              "  </head>\n  <body>\n    <!-- 在此编写表单 -->\n  </body>\n</html>",
                "checkpoints": [
                    {
                        "name": "存在表单",
                        "type": "assert_element",
                        "selector": "form",
                        "assertion_type": "exists",
                        "feedback": "需要 <form> 表单容器",
                    },
                    {
                        "name": "存在用户名输入框",
                        "type": "assert_attribute",
                        "selector": "input[name=\"username\"]",
                        "attribute": "type",
                        "assertion_type": "equals",
                        "value": "text",
                        "feedback": "需要 type=\"text\" 的用户名输入框",
                    },
                    {
                        "name": "存在提交按钮",
                        "type": "assert_element",
                        "selector": "button[type=\"submit\"]",
                        "assertion_type": "exists",
                        "feedback": "需要提交按钮",
                    },
                ],
            },
        },
        {
            "key": "ch3",
            "title": "CSS 基础与选择器",
            "description": "用 CSS 为页面设置颜色、字体与盒子样式。",
            "sections": [
                {
                    "title": "CSS 引入与选择器",
                    "body_md": (
                        "CSS（层叠样式表）描述元素如何呈现。引入方式有三种：行内 `style`、页面内 `<style>`、外部 `link` 引入，"
                        "推荐外部引入便于复用。选择器决定「给谁加样式」。\n\n"
                        "```css\n/* 标签选择器 */\nh1 { color: #2c3e50; }\n/* 类选择器 */\n.card { border: 1px solid #ddd; }\n"
                        "/* id 选择器 */\n#banner { background: #3498db; }\n```\n\n"
                        "类选择器 `.card` 可被多个元素复用，id 选择器 `#banner` 全页唯一，属性与子代选择器可组合出更精确的定位。"
                    ),
                },
                {
                    "title": "盒模型",
                    "body_md": (
                        "每个元素都是一只盒子：从内到外依次是内容 content、内边距 padding、边框 border、外边距 margin。\n\n"
                        "```css\n.box {\n  width: 200px;\n  padding: 12px;\n  border: 1px solid #ccc;\n"
                        "  margin: 8px;\n  background: #f8f9fa;\n}\n```\n\n"
                        "默认 `box-sizing: content-box` 时宽度不含 padding/border；设置 `box-sizing: border-box` 后，"
                        "声明的宽度即盒子的最终宽度，布局更易预测。"
                    ),
                },
            ],
            "test": {
                "title": "卡片样式测验",
                "description_md": "给 `.card` 元素设置 1px 灰色边框、8px 内边距和浅灰背景。",
                "start_code": "<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset=\"UTF-8\">\n    <style>\n"
                              "      /* 在此编写样式 */\n    </style>\n  </head>\n  <body>\n"
                              "    <div class=\"card\">卡片内容</div>\n  </body>\n</html>",
                "checkpoints": [
                    {
                        "name": "存在卡片元素",
                        "type": "assert_element",
                        "selector": ".card",
                        "assertion_type": "exists",
                        "feedback": "需要 class=\"card\" 的元素",
                    },
                    {
                        "name": "卡片有边框",
                        "type": "assert_style",
                        "selector": ".card",
                        "css_property": "border",
                        "assertion_type": "equals",
                        "value": "1px solid #ccc",
                        "feedback": "边框应为 1px solid #ccc",
                    },
                    {
                        "name": "卡片有内边距",
                        "type": "assert_style",
                        "selector": ".card",
                        "css_property": "padding",
                        "assertion_type": "equals",
                        "value": "8px",
                        "feedback": "内边距应为 8px",
                    },
                ],
            },
        },
        {
            "key": "ch4",
            "title": "CSS 布局",
            "description": "用 Flexbox 与 Grid 实现现代网页布局。",
            "sections": [
                {
                    "title": "Flexbox 弹性布局",
                    "body_md": (
                        "Flexbox 适合一维排列（一行或一列）。在容器上声明 `display: flex`，主轴方向由 `flex-direction` 控制，"
                        "子项沿主轴排列。\n\n"
                        "```css\n.nav { display: flex; gap: 12px; }\n.nav .item { flex: 1; text-align: center; }\n```\n\n"
                        "`justify-content` 控制主轴对齐（如 `space-between` 两端对齐），`align-items` 控制交叉轴对齐；"
                        "`gap` 直接设置子项间距，无需再写外边距。"
                    ),
                },
                {
                    "title": "Grid 网格布局",
                    "body_md": (
                        "Grid 适合二维布局（行与列）。用 `grid-template-columns` 定义列宽，`grid-template-rows` 定义行高，"
                        "子项自动填充网格。\n\n"
                        "```css\n.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }\n```\n\n"
                        "`1fr` 表示按比例瓜分剩余空间，`repeat(3, 1fr)` 即三等分；`grid-column` / `grid-row` 可让某个子项"
                        "跨越多列或多行，适合搭建卡片墙、仪表盘等复杂版面。"
                    ),
                },
            ],
            "test": {
                "title": "两栏布局测验",
                "description_md": "使用 Flexbox 让 `.container` 下的两个 `.col` 子元素并排显示。",
                "start_code": "<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset=\"UTF-8\">\n    <style>\n"
                              "      /* 在此编写布局 */\n    </style>\n  </head>\n  <body>\n"
                              "    <div class=\"container\">\n      <div class=\"col\">左栏</div>\n"
                              "      <div class=\"col\">右栏</div>\n    </div>\n  </body>\n</html>",
                "checkpoints": [
                    {
                        "name": "容器为弹性布局",
                        "type": "assert_style",
                        "selector": ".container",
                        "css_property": "display",
                        "assertion_type": "equals",
                        "value": "flex",
                        "feedback": "container 需要 display: flex",
                    },
                    {
                        "name": "两栏等宽",
                        "type": "assert_style",
                        "selector": ".col",
                        "css_property": "flex",
                        "assertion_type": "matches_regex",
                        "value": r"1.*|0 1 1",
                        "feedback": "每栏应可伸缩（flex: 1 或类似）",
                    },
                ],
            },
        },
        {
            "key": "ch5",
            "title": "JavaScript 交互",
            "description": "用 JavaScript 操作页面元素并响应事件。",
            "sections": [
                {
                    "title": "DOM 操作",
                    "body_md": (
                        "DOM（文档对象模型）把页面解析为一棵节点树，JavaScript 通过它读写页面。常用入口：\n\n"
                        "```js\nconst box = document.querySelector('#box');   // 按选择器取元素\n"
                        "box.textContent = '新内容';                    // 改文本\n"
                        "box.style.color = 'red';                      // 改样式\n"
                        "box.classList.add('active');                  // 改类名\n```\n\n"
                        "`querySelector` 返回第一个匹配元素，`querySelectorAll` 返回全部；新增节点可用 "
                        "`document.createElement` 配合 `appendChild` 动态插入。"
                    ),
                },
                {
                    "title": "事件处理",
                    "body_md": (
                        "事件让页面「动」起来。用 `addEventListener` 给元素绑定事件，最常见的类型有 "
                        "`click`（点击）、`input`（输入）、`submit`（提交）、`keydown`（按键）。\n\n"
                        "```js\nconst btn = document.querySelector('#btn');\nconst counter = document.querySelector('#count');\n"
                        "let n = 0;\nbtn.addEventListener('click', () => {\n  n += 1;\n  counter.textContent = n;\n});\n```\n\n"
                        "事件回调里 `this` 指向绑定元素；需要移除监听时保存函数引用并调用 `removeEventListener`。"
                    ),
                },
            ],
            "test": {
                "title": "点击切换测验",
                "description_md": "点击按钮后，将 `#status` 元素的文本切换为「已激活」。",
                "start_code": "<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset=\"UTF-8\">\n  </head>\n"
                              "  <body>\n    <button id=\"btn\">点击</button>\n    <span id=\"status\">未激活</span>\n"
                              "    <script>\n      // 在此编写交互逻辑\n    </script>\n  </body>\n</html>",
                "checkpoints": [
                    {
                        "name": "初始状态存在",
                        "type": "assert_element",
                        "selector": "#status",
                        "assertion_type": "exists",
                        "feedback": "需要 #status 元素",
                    },
                    {
                        "name": "按钮绑定点击",
                        "type": "interaction_and_assert",
                        "selector": "#btn",
                        "action_selector": "#btn",
                        "assertion_type": "equals",
                        "value": "已激活",
                        "feedback": "点击按钮后 #status 应变为「已激活」",
                    },
                ],
            },
        },
    ],
    "knowledge_graph": {
        "nodes": [
            {"data": {"id": "ch1", "label": "HTML 基础入门", "type": "chapter"}},
            {"data": {"id": "ch1_s1", "label": "HTML 文档结构", "type": "knowledge"}},
            {"data": {"id": "ch1_s2", "label": "常用 HTML 标签", "type": "knowledge"}},
            {"data": {"id": "ch2", "label": "HTML 表单与语义化", "type": "chapter"}},
            {"data": {"id": "ch2_s1", "label": "表单元素", "type": "knowledge"}},
            {"data": {"id": "ch2_s2", "label": "语义化标签", "type": "knowledge"}},
            {"data": {"id": "ch3", "label": "CSS 基础与选择器", "type": "chapter"}},
            {"data": {"id": "ch3_s1", "label": "CSS 引入与选择器", "type": "knowledge"}},
            {"data": {"id": "ch3_s2", "label": "盒模型", "type": "knowledge"}},
            {"data": {"id": "ch4", "label": "CSS 布局", "type": "chapter"}},
            {"data": {"id": "ch4_s1", "label": "Flexbox 弹性布局", "type": "knowledge"}},
            {"data": {"id": "ch4_s2", "label": "Grid 网格布局", "type": "knowledge"}},
            {"data": {"id": "ch5", "label": "JavaScript 交互", "type": "chapter"}},
            {"data": {"id": "ch5_s1", "label": "DOM 操作", "type": "knowledge"}},
            {"data": {"id": "ch5_s2", "label": "事件处理", "type": "knowledge"}},
        ],
        "edges": [
            {"data": {"source": "ch1", "target": "ch1_s1"}},
            {"data": {"source": "ch1", "target": "ch1_s2"}},
            {"data": {"source": "ch1", "target": "ch2"}},
            {"data": {"source": "ch2", "target": "ch2_s1"}},
            {"data": {"source": "ch2", "target": "ch2_s2"}},
            {"data": {"source": "ch2", "target": "ch3"}},
            {"data": {"source": "ch3", "target": "ch3_s1"}},
            {"data": {"source": "ch3", "target": "ch3_s2"}},
            {"data": {"source": "ch3", "target": "ch4"}},
            {"data": {"source": "ch4", "target": "ch4_s1"}},
            {"data": {"source": "ch4", "target": "ch4_s2"}},
            {"data": {"source": "ch4", "target": "ch5"}},
            {"data": {"source": "ch5", "target": "ch5_s1"}},
            {"data": {"source": "ch5", "target": "ch5_s2"}},
            {"data": {"source": "ch1_s2", "target": "ch2_s1"}},
            {"data": {"source": "ch3_s2", "target": "ch4_s1"}},
            {"data": {"source": "ch4_s2", "target": "ch5_s1"}},
        ],
    },
}

# ---------------------------------------------------------------- python-basic

_PYTHON_BASIC: Dict[str, Any] = {
    "title": "Python 编程基础",
    "description": "从环境搭建到函数与列表，用示例驱动的方式掌握 Python 核心语法。",
    "course_type": "code",
    "allowed_runtimes": ["python3"],
    "chapters": [
        {
            "key": "ch1",
            "title": "Python 环境与基础语法",
            "description": "搭建运行环境，认识变量、数据类型与输入输出。",
            "sections": [
                {
                    "title": "变量与数据类型",
                    "body_md": (
                        "Python 是动态类型语言，变量无需声明类型，直接赋值即可。内置的常用类型：\n\n"
                        "```python\nage = 18          # int 整数\nprice = 9.9       # float 浮点数\n"
                        "name = \"Alice\"    # str 字符串\nis_ok = True      # bool 布尔\n"
                        "scores = [90, 85]  # list 列表\n```\n\n"
                        "用 `type()` 可以查看变量的类型；变量名区分大小写，建议使用小写加下划线的命名风格（如 `user_age`）。"
                    ),
                },
                {
                    "title": "输入与输出",
                    "body_md": (
                        "`print()` 向屏幕输出内容，多个参数用逗号分隔；`input()` 读取用户输入，返回值总是字符串。\n\n"
                        "```python\nname = input(\"请输入姓名：\")\nprint(\"你好，\" + name)\n\n"
                        "# 输入的数字是字符串，需要 int() 转换才能参与运算\n"
                        "num = int(input(\"请输入一个整数：\"))\nprint(num * 2)\n```"
                    ),
                },
            ],
            "test": {
                "title": "基础语法测验",
                "description_md": "读取一个整数，输出它的两倍。",
                "start_code": "# 在此编写代码\nnum = int(input())\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "输出两倍值",
                        "input": "21",
                        "expected_output": "42",
                        "description": "输入 21 应输出 42",
                        "hint": "对输入取整后乘 2",
                    },
                    {
                        "type": "code_io",
                        "name": "再次验证",
                        "input": "-3",
                        "expected_output": "-6",
                        "description": "输入 -3 应输出 -6",
                        "hint": "注意负数处理",
                    },
                ],
            },
        },
        {
            "key": "ch2",
            "title": "条件与循环",
            "description": "用条件分支与循环控制程序执行流程。",
            "sections": [
                {
                    "title": "条件分支",
                    "body_md": (
                        "`if / elif / else` 按条件执行不同分支。条件表达式用比较运算符（`==` `>` `<`）与逻辑运算符"
                        "（`and` `or` `not`）组合。\n\n"
                        "```python\nscore = int(input())\nif score >= 90:\n    print(\"优秀\")\n"
                        "elif score >= 60:\n    print(\"及格\")\nelse:\n    print(\"不及格\")\n```\n\n"
                        "注意 Python 用缩进（通常 4 个空格）表示代码块，不要混用制表符与空格。"
                    ),
                },
                {
                    "title": "循环",
                    "body_md": (
                        "`for` 遍历可迭代对象，`while` 在条件成立时反复执行。常与 `range()` 配合生成等差数列。\n\n"
                        "```python\nfor i in range(1, 6):     # 1..5\n    print(i)\n\ntotal = 0\nfor n in range(1, 101):   # 累加 1..100\n    total += n\nprint(total)              # 5050\n```\n\n"
                        "`break` 提前结束循环，`continue` 跳过本轮进入下一轮。"
                    ),
                },
            ],
            "test": {
                "title": "条件循环测验",
                "description_md": "读取正整数 n，输出 1 到 n 的和。",
                "start_code": "# 在此编写代码\nn = int(input())\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "前 100 项和",
                        "input": "100",
                        "expected_output": "5050",
                        "description": "1 到 100 的和应为 5050",
                        "hint": "可用 range 累加",
                    },
                    {
                        "type": "code_io",
                        "name": "单元素",
                        "input": "1",
                        "expected_output": "1",
                        "description": "1 到 1 的和为 1",
                        "hint": "边界情况也要正确",
                    },
                ],
            },
        },
        {
            "key": "ch3",
            "title": "函数与模块",
            "description": "用函数封装逻辑，用模块复用代码。",
            "sections": [
                {
                    "title": "函数定义",
                    "body_md": (
                        "函数用 `def` 定义，可带参数与返回值。默认参数提供缺省值，关键字参数让调用更清晰。\n\n"
                        "```python\ndef greet(name, greeting=\"你好\"):\n    \"\"\"返回问候语\"\"\"\n    return f\"{greeting}，{name}\"\n\n"
                        "print(greet(\"小明\"))          # 你好，小明\n"
                        "print(greet(\"小红\", greeting=\"早上好\"))  # 早上好，小红\n```\n\n"
                        "`return` 可返回多个值（实际是元组）；没有 `return` 的函数返回 `None`。"
                    ),
                },
                {
                    "title": "模块导入",
                    "body_md": (
                        "模块是组织的代码文件，用 `import` 引入后即可使用其中的函数与常量。标准库提供了海量现成工具。\n\n"
                        "```python\nimport math\nimport random\nfrom datetime import datetime\n\n"
                        "print(math.sqrt(16))                 # 4.0\n"
                        "print(random.randint(1, 6))          # 1~6 随机整数\n"
                        "print(datetime.now().strftime(\"%Y-%m-%d\"))\n```\n\n"
                        "`from module import name` 只导入指定名称；别名 `import math as m` 可缩短调用路径。"
                    ),
                },
            ],
            "test": {
                "title": "函数测验",
                "description_md": "实现函数 `square(n)` 返回 `n` 的平方，读取 n 后输出结果。",
                "start_code": "# 在此编写代码\ndef square(n):\n    pass\n\nn = int(input())\nprint(square(n))\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "平方计算",
                        "input": "7",
                        "expected_output": "49",
                        "description": "7 的平方应为 49",
                        "hint": "返回 n * n",
                    },
                    {
                        "type": "code_io",
                        "name": "零值",
                        "input": "0",
                        "expected_output": "0",
                        "description": "0 的平方为 0",
                        "hint": "边界情况",
                    },
                ],
            },
        },
        {
            "key": "ch4",
            "title": "字符串与列表",
            "description": "掌握最常用的两种序列类型及其方法。",
            "sections": [
                {
                    "title": "字符串操作",
                    "body_md": (
                        "字符串是不可变序列，支持切片、拼接与丰富的方法：\n\n"
                        "```python\ns = \"Hello, Python\"\nprint(s.lower())        # hello, python\n"
                        "print(s.split(\",\"))    # ['Hello', ' Python']\n"
                        "print(s.strip())        # 去掉首尾空白\n"
                        "print(s.startswith(\"He\"))  # True\n```\n\n"
                        "切片 `s[start:end:step]` 可截取子串，如 `s[7:]` 取 `Python`，`s[::-1]` 反转字符串。"
                    ),
                },
                {
                    "title": "列表方法",
                    "body_md": (
                        "列表是可变的，支持增删改查与排序：\n\n"
                        "```python\nnums = [3, 1, 2]\nnums.append(4)      # [3, 1, 2, 4]\n"
                        "nums.insert(0, 0)   # [0, 3, 1, 2, 4]\nnums.sort()         # [0, 1, 2, 3, 4]\n"
                        "nums.remove(3)      # 删除第一个 3\nprint(len(nums))    # 长度\n```\n\n"
                        "列表推导式 `[x * 2 for x in nums if x > 1]` 可一行完成筛选与变换。"
                    ),
                },
            ],
            "test": {
                "title": "字符串与列表测验",
                "description_md": "读取一行由空格分隔的整数，输出其中最大的数。",
                "start_code": "# 在此编写代码\nline = input()\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "常规输入",
                        "input": "3 9 5 1",
                        "expected_output": "9",
                        "description": "最大数应为 9",
                        "hint": "split 后用 max()",
                    },
                    {
                        "type": "code_io",
                        "name": "负数输入",
                        "input": "-5 -2 -8",
                        "expected_output": "-2",
                        "description": "最大数应为 -2",
                        "hint": "注意负数",
                    },
                ],
            },
        },
        {
            "key": "ch5",
            "title": "综合实战",
            "description": "综合运用所学语法完成两个小项目。",
            "sections": [
                {
                    "title": "猜数字游戏",
                    "body_md": (
                        "把分支、循环、随机数组合起来：程序在 1~100 间随机选数，玩家反复猜测，程序提示大了或小了，"
                        "猜中后显示次数。\n\n"
                        "```python\nimport random\nanswer = random.randint(1, 100)\ntimes = 0\nwhile True:\n    guess = int(input(\"猜一个 1~100 的数：\"))\n    times += 1\n"
                        "    if guess > answer:\n        print(\"大了\")\n    elif guess < answer:\n        print(\"小了\")\n"
                        "    else:\n        print(f\"猜中！共用了 {times} 次\")\n        break\n```"
                    ),
                },
                {
                    "title": "简易记账本",
                    "body_md": (
                        "用列表保存收支记录，循环展示菜单，按用户选择执行操作：\n\n"
                        "```python\nrecords = []\nwhile True:\n    cmd = input(\"1 记一笔 2 查看 0 退出：\")\n"
                        "    if cmd == \"1\":\n        records.append(float(input(\"金额：\")))\n"
                        "    elif cmd == \"2\":\n        print(f\"结余：{sum(records):.2f}\")\n"
                        "    elif cmd == \"0\":\n        break\n```\n\n"
                        "`sum()` 求和、f-string 的 `:.2f` 控制小数位，这些细节让程序更像真实应用。"
                    ),
                },
            ],
            "test": {
                "title": "实战测验",
                "description_md": "读取一个整数 n，输出 1×1 到 n×n 的乘法表（每行一个算式）。",
                "start_code": "# 在此编写代码\nn = int(input())\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "小规模",
                        "input": "3",
                        "expected_output": "1*1=1\n2*2=4\n3*3=9",
                        "description": "输出 1 到 3 的平方算式",
                        "hint": "for 循环逐行输出",
                    },
                    {
                        "type": "code_io",
                        "name": "单行",
                        "input": "1",
                        "expected_output": "1*1=1",
                        "description": "只有一行",
                        "hint": "边界情况",
                    },
                ],
            },
        },
    ],
    "knowledge_graph": {
        "nodes": [
            {"data": {"id": "ch1", "label": "Python 环境与基础语法", "type": "chapter"}},
            {"data": {"id": "ch1_s1", "label": "变量与数据类型", "type": "knowledge"}},
            {"data": {"id": "ch1_s2", "label": "输入与输出", "type": "knowledge"}},
            {"data": {"id": "ch2", "label": "条件与循环", "type": "chapter"}},
            {"data": {"id": "ch2_s1", "label": "条件分支", "type": "knowledge"}},
            {"data": {"id": "ch2_s2", "label": "循环", "type": "knowledge"}},
            {"data": {"id": "ch3", "label": "函数与模块", "type": "chapter"}},
            {"data": {"id": "ch3_s1", "label": "函数定义", "type": "knowledge"}},
            {"data": {"id": "ch3_s2", "label": "模块导入", "type": "knowledge"}},
            {"data": {"id": "ch4", "label": "字符串与列表", "type": "chapter"}},
            {"data": {"id": "ch4_s1", "label": "字符串操作", "type": "knowledge"}},
            {"data": {"id": "ch4_s2", "label": "列表方法", "type": "knowledge"}},
            {"data": {"id": "ch5", "label": "综合实战", "type": "chapter"}},
            {"data": {"id": "ch5_s1", "label": "猜数字游戏", "type": "knowledge"}},
            {"data": {"id": "ch5_s2", "label": "简易记账本", "type": "knowledge"}},
        ],
        "edges": [
            {"data": {"source": "ch1", "target": "ch1_s1"}},
            {"data": {"source": "ch1", "target": "ch1_s2"}},
            {"data": {"source": "ch1", "target": "ch2"}},
            {"data": {"source": "ch2", "target": "ch2_s1"}},
            {"data": {"source": "ch2", "target": "ch2_s2"}},
            {"data": {"source": "ch2", "target": "ch3"}},
            {"data": {"source": "ch3", "target": "ch3_s1"}},
            {"data": {"source": "ch3", "target": "ch3_s2"}},
            {"data": {"source": "ch3", "target": "ch4"}},
            {"data": {"source": "ch4", "target": "ch4_s1"}},
            {"data": {"source": "ch4", "target": "ch4_s2"}},
            {"data": {"source": "ch4", "target": "ch5"}},
            {"data": {"source": "ch5", "target": "ch5_s1"}},
            {"data": {"source": "ch5", "target": "ch5_s2"}},
            {"data": {"source": "ch1_s2", "target": "ch2_s1"}},
            {"data": {"source": "ch2_s2", "target": "ch3_s1"}},
            {"data": {"source": "ch4_s1", "target": "ch5_s2"}},
        ],
    },
}

# ---------------------------------------------------------------- cpp-basic

_CPP_BASIC: Dict[str, Any] = {
    "title": "C++ 编程基础",
    "description": "从程序结构到函数，循序渐进掌握 C++ 核心语法与标准库。",
    "course_type": "code",
    "allowed_runtimes": ["cpp"],
    "chapters": [
        {
            "key": "ch1",
            "title": "C++ 环境与基础语法",
            "description": "认识 C++ 程序结构、变量与数据类型。",
            "sections": [
                {
                    "title": "程序结构",
                    "body_md": (
                        "一个最小的 C++ 程序：`#include <iostream>` 引入输入输出流头文件，`main` 是程序入口，"
                        "`std::cout` 输出内容，`return 0` 表示正常结束。\n\n"
                        "```cpp\n#include <iostream>\n\nint main() {\n    std::cout << \"Hello, C++!\" << std::endl;\n"
                        "    return 0;\n}\n```\n\n"
                        "每条语句以分号结尾；用 `using namespace std;` 可省略 `std::` 前缀（小工程常用，工程上更推荐显式写出）。"
                    ),
                },
                {
                    "title": "变量与数据类型",
                    "body_md": (
                        "C++ 是静态类型语言，变量必须先声明类型再使用。基础类型包括整数 `int`、浮点 `double`、"
                        "字符 `char`、布尔 `bool`。\n\n"
                        "```cpp\nint age = 18;\ndouble price = 9.9;\nchar grade = 'A';\nbool is_ok = true;\n```\n\n"
                        "`auto` 可让编译器自动推导类型；`const` 声明不可修改的常量。"
                    ),
                },
            ],
            "test": {
                "title": "基础语法测验",
                "description_md": "读取一个整数，输出它的两倍。",
                "start_code": "#include <iostream>\n\nint main() {\n    int n;\n    std::cin >> n;\n    // 在此编写输出逻辑\n    return 0;\n}\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "输出两倍值",
                        "input": "21",
                        "expected_output": "42",
                        "description": "输入 21 应输出 42",
                        "hint": "cout << n * 2",
                    },
                    {
                        "type": "code_io",
                        "name": "再次验证",
                        "input": "-3",
                        "expected_output": "-6",
                        "description": "输入 -3 应输出 -6",
                        "hint": "注意负数",
                    },
                ],
            },
        },
        {
            "key": "ch2",
            "title": "输入输出与运算符",
            "description": "掌握标准输入输出与常用运算符。",
            "sections": [
                {
                    "title": "标准输入输出",
                    "body_md": (
                        "`std::cin >>` 从键盘读入数据，`std::cout <<` 输出数据。多个输入用空格或换行分隔，"
                        "`std::endl` 或 `\\n` 换行。\n\n"
                        "```cpp\n#include <iostream>\nint main() {\n    int a, b;\n"
                        "    std::cin >> a >> b;\n    std::cout << a + b << std::endl;\n    return 0;\n}\n```"
                    ),
                },
                {
                    "title": "运算符",
                    "body_md": (
                        "算术运算符 `+ - * / %`；`/` 对整数做整除，`%` 取余数。比较运算符返回布尔值，"
                        "逻辑运算符 `&&`（与）、`||`（或）、`!`（非）。\n\n"
                        "```cpp\nint x = 7;\nbool even = (x % 2 == 0);   // false\n"
                        "int q = 7 / 2;               // 3，整数除法\n"
                        "double r = 7.0 / 2;          // 3.5\n```\n\n"
                        "注意整数除法会丢弃小数，需要浮点结果时至少让一个操作数是浮点类型。"
                    ),
                },
            ],
            "test": {
                "title": "输入输出测验",
                "description_md": "读取两个整数，输出它们的和。",
                "start_code": "#include <iostream>\n\nint main() {\n    int a, b;\n    std::cin >> a >> b;\n    // 在此编写输出逻辑\n    return 0;\n}\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "求和",
                        "input": "3 5",
                        "expected_output": "8",
                        "description": "3 + 5 应为 8",
                        "hint": "cout << a + b",
                    },
                    {
                        "type": "code_io",
                        "name": "负数求和",
                        "input": "-1 1",
                        "expected_output": "0",
                        "description": "-1 + 1 应为 0",
                        "hint": "边界情况",
                    },
                ],
            },
        },
        {
            "key": "ch3",
            "title": "条件与循环",
            "description": "用 if/switch 与 for/while 控制流程。",
            "sections": [
                {
                    "title": "条件分支",
                    "body_md": (
                        "`if / else if / else` 按条件选择分支；`switch` 适合对整数值做多路分发。\n\n"
                        "```cpp\nint score;\nstd::cin >> score;\nif (score >= 90) {\n    std::cout << \"优秀\";\n"
                        "} else if (score >= 60) {\n    std::cout << \"及格\";\n} else {\n    std::cout << \"不及格\";\n}\n```\n\n"
                        "条件表达式通常放在括号内；花括号内的多行语句构成一个代码块。"
                    ),
                },
                {
                    "title": "循环",
                    "body_md": (
                        "`for` 适合已知次数的循环，`while` 适合条件驱动。\n\n"
                        "```cpp\nint total = 0;\nfor (int i = 1; i <= 100; i++) {\n    total += i;\n}\n"
                        "std::cout << total << std::endl;  // 5050\n\n"
                        "int n = 5;\nwhile (n > 0) {\n    std::cout << n--;\n}\n```\n\n"
                        "`break` 跳出循环，`continue` 跳过本轮；注意 `for` 的三个部分（初始化/条件/步进）用分号分隔。"
                    ),
                },
            ],
            "test": {
                "title": "条件循环测验",
                "description_md": "读取正整数 n，输出 1 到 n 的和。",
                "start_code": "#include <iostream>\n\nint main() {\n    int n;\n    std::cin >> n;\n    // 在此编写输出逻辑\n    return 0;\n}\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "前 100 项和",
                        "input": "100",
                        "expected_output": "5050",
                        "description": "1 到 100 的和应为 5050",
                        "hint": "for 循环累加",
                    },
                    {
                        "type": "code_io",
                        "name": "单元素",
                        "input": "1",
                        "expected_output": "1",
                        "description": "1 到 1 的和为 1",
                        "hint": "边界情况",
                    },
                ],
            },
        },
        {
            "key": "ch4",
            "title": "数组与字符串",
            "description": "用数组与 string 处理批量数据与文本。",
            "sections": [
                {
                    "title": "数组",
                    "body_md": (
                        "数组是同类型元素的连续存储。声明时指定大小，下标从 0 开始。\n\n"
                        "```cpp\nint scores[5] = {90, 85, 78, 92, 88};\nint sum = 0;\n"
                        "for (int i = 0; i < 5; i++) {\n    sum += scores[i];\n}\n"
                        "double avg = sum / 5.0;\n```\n\n"
                        "数组下标越界是未定义行为，务必保证下标在 `0 ~ 大小-1` 范围内。"
                    ),
                },
                {
                    "title": "string 字符串",
                    "body_md": (
                        "标准库的 `std::string` 提供字符串的便捷操作：拼接、取长度、子串、查找。\n\n"
                        "```cpp\n#include <string>\nstd::string s = \"hello\";\n"
                        "s += \" world\";                 // 拼接\nstd::cout << s.size();        // 11\n"
                        "std::string sub = s.substr(6); // \"world\"\n"
                        "size_t pos = s.find(\"lo\");     // 3\n```\n\n"
                        "用 `std::getline(std::cin, s)` 读取带空格的整行输入。"
                    ),
                },
            ],
            "test": {
                "title": "数组测验",
                "description_md": "读取 n 和 n 个整数，输出其中的最大值。",
                "start_code": "#include <iostream>\n\nint main() {\n    int n;\n    std::cin >> n;\n    // 在此编写代码\n    return 0;\n}\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "常规输入",
                        "input": "4\n3 9 5 1",
                        "expected_output": "9",
                        "description": "最大数应为 9",
                        "hint": "逐元素比较更新最大值",
                    },
                    {
                        "type": "code_io",
                        "name": "单元素",
                        "input": "1\n7",
                        "expected_output": "7",
                        "description": "只有一个元素时输出它本身",
                        "hint": "边界情况",
                    },
                ],
            },
        },
        {
            "key": "ch5",
            "title": "函数",
            "description": "用函数组织代码、实现复用。",
            "sections": [
                {
                    "title": "函数定义与调用",
                    "body_md": (
                        "函数把一段逻辑封装起来，可反复调用。声明包含返回类型、函数名、参数列表与函数体。\n\n"
                        "```cpp\nint max2(int a, int b) {\n    return a > b ? a : b;\n}\n\n"
                        "int main() {\n    std::cout << max2(3, 5) << std::endl;  // 5\n    return 0;\n}\n```\n\n"
                        "函数先声明后使用（或把定义放在调用之前）；返回类型为 `void` 表示不返回任何值。"
                    ),
                },
                {
                    "title": "参数与返回值",
                    "body_md": (
                        "参数默认按值传递（拷贝一份）；需要修改实参时用引用 `int&`。`const` 修饰的引用可避免拷贝同时保护数据。\n\n"
                        "```cpp\nvoid add_one(int& x) {\n    x += 1;\n}\n\n"
                        "int main() {\n    int v = 10;\n    add_one(v);\n    std::cout << v << std::endl;  // 11\n"
                        "    return 0;\n}\n```\n\n"
                        "重载：同名函数可以用不同的参数列表并存，编译器按实参匹配调用。"
                    ),
                },
            ],
            "test": {
                "title": "函数测验",
                "description_md": "实现函数 `square(int n)` 返回 `n` 的平方，读取 n 后输出结果。",
                "start_code": "#include <iostream>\n\nint square(int n) {\n    // 在此编写实现\n}\n\nint main() {\n    int n;\n    std::cin >> n;\n    std::cout << square(n) << std::endl;\n    return 0;\n}\n",
                "checkpoints": [
                    {
                        "type": "code_io",
                        "name": "平方计算",
                        "input": "7",
                        "expected_output": "49",
                        "description": "7 的平方应为 49",
                        "hint": "return n * n;",
                    },
                    {
                        "type": "code_io",
                        "name": "零值",
                        "input": "0",
                        "expected_output": "0",
                        "description": "0 的平方为 0",
                        "hint": "边界情况",
                    },
                ],
            },
        },
    ],
    "knowledge_graph": {
        "nodes": [
            {"data": {"id": "ch1", "label": "C++ 环境与基础语法", "type": "chapter"}},
            {"data": {"id": "ch1_s1", "label": "程序结构", "type": "knowledge"}},
            {"data": {"id": "ch1_s2", "label": "变量与数据类型", "type": "knowledge"}},
            {"data": {"id": "ch2", "label": "输入输出与运算符", "type": "chapter"}},
            {"data": {"id": "ch2_s1", "label": "标准输入输出", "type": "knowledge"}},
            {"data": {"id": "ch2_s2", "label": "运算符", "type": "knowledge"}},
            {"data": {"id": "ch3", "label": "条件与循环", "type": "chapter"}},
            {"data": {"id": "ch3_s1", "label": "条件分支", "type": "knowledge"}},
            {"data": {"id": "ch3_s2", "label": "循环", "type": "knowledge"}},
            {"data": {"id": "ch4", "label": "数组与字符串", "type": "chapter"}},
            {"data": {"id": "ch4_s1", "label": "数组", "type": "knowledge"}},
            {"data": {"id": "ch4_s2", "label": "string 字符串", "type": "knowledge"}},
            {"data": {"id": "ch5", "label": "函数", "type": "chapter"}},
            {"data": {"id": "ch5_s1", "label": "函数定义与调用", "type": "knowledge"}},
            {"data": {"id": "ch5_s2", "label": "参数与返回值", "type": "knowledge"}},
        ],
        "edges": [
            {"data": {"source": "ch1", "target": "ch1_s1"}},
            {"data": {"source": "ch1", "target": "ch1_s2"}},
            {"data": {"source": "ch1", "target": "ch2"}},
            {"data": {"source": "ch2", "target": "ch2_s1"}},
            {"data": {"source": "ch2", "target": "ch2_s2"}},
            {"data": {"source": "ch2", "target": "ch3"}},
            {"data": {"source": "ch3", "target": "ch3_s1"}},
            {"data": {"source": "ch3", "target": "ch3_s2"}},
            {"data": {"source": "ch3", "target": "ch4"}},
            {"data": {"source": "ch4", "target": "ch4_s1"}},
            {"data": {"source": "ch4", "target": "ch4_s2"}},
            {"data": {"source": "ch4", "target": "ch5"}},
            {"data": {"source": "ch5", "target": "ch5_s1"}},
            {"data": {"source": "ch5", "target": "ch5_s2"}},
            {"data": {"source": "ch1_s2", "target": "ch2_s1"}},
            {"data": {"source": "ch2_s2", "target": "ch3_s1"}},
            {"data": {"source": "ch4_s2", "target": "ch5_s1"}},
        ],
    },
}

# 模板 id → 内置课程内容
_COURSES: Dict[str, Dict[str, Any]] = {
    "web-frontend": _WEB_FRONTEND,
    "python-basic": _PYTHON_BASIC,
    "cpp-basic": _CPP_BASIC,
}


def get_course(template_id: str) -> Dict[str, Any]:
    """按模板 id 取内置课程内容；不存在返回空 dict。"""
    return _COURSES.get(template_id) or {}


def list_courses() -> Dict[str, Dict[str, Any]]:
    """全部内置课程（测试/调试用）。"""
    return dict(_COURSES)
