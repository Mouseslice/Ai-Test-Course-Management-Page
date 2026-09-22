"""教师端判题预览 DTO（对接 teacher-frontend/src/api/system/judge-api.ts）。

与教师端其他接口约定一致：
  - 字段名使用 camelCase（judge-api.ts 契约）；
  - 成功响应统一 StandardResponse(code=0)。

使用场景：内容生成器的测试题编辑组件（TestQuestionForm.vue）在保存前
调用 POST /api/submission/previews 做"本地判题预览"（不创建提交记录）。
"""
from typing import List, Optional

from pydantic import BaseModel


class CodeBundlePayload(BaseModel):
    """Web 前端三件套：html / css / js。"""
    html: str = ""
    css: str = ""
    js: str = ""


class PreviewCheckpointParam(BaseModel):
    """教师端检查点参数（扁平结构，全部可选，由 TestQuestionForm 表单构造）。

    注意：教师端为扁平结构，与后端学生端检查点模型（schemas/content.py 的
    BaseCheckpoint 系列）不兼容，端点内需做适配转换后再交给沙箱评测。

    支持 interaction_and_assert 的嵌套断言：当 type 为 interaction_and_assert 时，
    可通过 assertion 携带完整的嵌套断言（复用本模型结构，递归）；
    未提供时由后端按携带字段（script / css_property / attribute）推断嵌套种类。
    """
    name: str = ""
    type: str = ""
    selector: str = ""
    assertion_type: Optional[str] = None
    value: Optional[str] = None
    css_property: Optional[str] = None
    attribute: Optional[str] = None
    script: Optional[str] = None
    feedback: Optional[str] = None
    action_selector: Optional[str] = None
    action_type: Optional[str] = None
    action_value: Optional[str] = None
    assertion: Optional["PreviewCheckpointParam"] = None


# 解析断言字段的前向引用（interaction_and_assert 的 assertion 复用本模型）
PreviewCheckpointParam.model_rebuild()


class PreviewTestCaseParam(BaseModel):
    """代码题测试用例：{ input, expected }。"""
    input: str = ""
    expected: str = ""


class PreviewJudgeRequest(BaseModel):
    """判题预览请求（二选一）：

    - Web 模式：codeBundle + checkpoints；
    - 代码题模式：languageMode + code + testCases。
    """
    codeBundle: Optional[CodeBundlePayload] = None
    checkpoints: Optional[List[PreviewCheckpointParam]] = None
    languageMode: Optional[str] = None
    code: Optional[str] = None
    testCases: Optional[List[PreviewTestCaseParam]] = None


class PreviewTestCaseResultItem(BaseModel):
    """单个检查点 / 测试用例的判题结果（对齐 TestCaseResultItem）。"""
    index: int = 0
    status: str = ""
    executionTime: int = 0
    memoryUsed: int = 0
    expected: Optional[str] = None
    actual: Optional[str] = None


class PreviewErrorInfo(BaseModel):
    """错误信息（对齐 JudgeResponseVO.errorInfo，占位保证契约完整）。"""
    errorType: str = ""
    lineNumber: Optional[int] = None
    columnNumber: Optional[int] = None
    message: str = ""
    stackTrace: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    failedTestCaseIndex: Optional[int] = None


class PreviewMetrics(BaseModel):
    """判题耗时指标（毫秒，对齐 JudgeResponseVO.metrics）。"""
    executionTime: int = 0
    memoryUsed: int = 0
    compileTime: int = 0
    totalTime: int = 0


class PreviewJudgeResponse(BaseModel):
    """判题预览响应（对齐 JudgeResponseVO）。"""
    status: str = "success"
    success: bool = False
    score: int = 0
    passedCount: int = 0
    totalCount: int = 0
    errorInfo: Optional[PreviewErrorInfo] = None
    metrics: Optional[PreviewMetrics] = None
    testCaseResults: Optional[List[PreviewTestCaseResultItem]] = None
    message: Optional[str] = None
