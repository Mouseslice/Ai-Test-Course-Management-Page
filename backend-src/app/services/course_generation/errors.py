"""coursegen 领域异常定义。

对应 Go 侧 coursegen 包里的哨兵错误。异常集中在 errors 模块，便于调用方用
except 精确捕获而不用猜错误字符串。
"""


class CourseGenError(Exception):
    """coursegen 领域异常的基类。"""


class JobNotFoundError(CourseGenError):
    """job 不存在或已被软删。"""


class ReviewNotFoundError(CourseGenError):
    """评审不存在。"""


class WorkspaceFileNotFoundError(CourseGenError):
    """工作区里没有这个路径的草稿。"""


class StaleStatusError(CourseGenError):
    """job 状态在读到与写回之间被别人改了。

    不是故障，是并发下的正常结局：两个执行者同时想推进同一个 job，只有一个能改到行。
    调用方应当重新读一次状态再决定，而不是重试同一个写。
    """


class ForbiddenError(CourseGenError):
    """这个 job 不属于当前用户。"""


class BudgetExhaustedError(CourseGenError):
    """token 预算用尽（可重试：工作区还在，加预算后可继续）。"""


class DesignReviewRequiredError(CourseGenError):
    """预算已越过设计检查点但还没有任何 approved 评审。

    不是失败，是暂停：harness 停止派发 episode，等 agent 发起评审、教师裁决之后继续。
    """


class FinalReviewStaleError(CourseGenError):
    """终审之后工作区又被改过，那次终审已作废。"""


class PublishContractError(CourseGenError):
    """工作区里的产物不符合发布契约。

    与「发布失败」分开：契约不符要作为观察喂回 agent 让它自己改，而不是打回人工。
    """


class AlreadyRunningError(CourseGenError):
    """这个 job 已经有一条驱动在跑了（幂等跳过，不排队不报错）。"""


class IterationLimitError(CourseGenError):
    """agent 回合撞上轮次上限。planner 层不是失败；worker 层是真的没做完。"""
