"""课程生成引擎（coursegen 的 Python 复现，本地生成模式）。

分层（自底向上）：
  - state.py      确定性状态机（唯一真相来源）
  - errors.py     领域异常
  - repository.py 仓储（crud 之上、harness 之下，自管会话）
  - harness.py    确定性 harness：状态机、预算门、评审门、事件流
  - template_content.py 模板内置内容库（章节语料/测试题/知识图谱）
  - local_generator.py  本地生成器（学习路径 + 模板 → course.json）
  - publish.py    发布器（终审不变量 + 契约校验 + 平台写入）
  - driver.py     驱动：唯一决定何时停（本地生成 / 租约）

生成链路已本地化：不再调用 LLM，秒级完成、结果可复现。

对外使用入口：
  driver.Driver(...).drive(job_uid)          —— Celery 主循环
  endpoints 通过 repository.SQLRepository 直连状态与草稿
"""
