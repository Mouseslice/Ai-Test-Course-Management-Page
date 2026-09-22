from pydantic import BaseModel
from typing import Dict, Any, Optional


class SurveyResultBase(BaseModel):
    """问卷结果基础模型"""
    participant_id: str
    survey_type: str
    answers: Dict[str, Any]


class SurveyResultCreate(SurveyResultBase):
    """创建问卷结果模型"""
    pass


class SurveyResultUpdate(SurveyResultBase):
    """更新问卷结果模型"""
    pass


class SurveyResultInDBBase(SurveyResultBase):
    """数据库基础问卷结果模型"""
    id: int
    submitted_at: Optional[str] = None

    class Config:
        from_attributes = True


class SurveyResult(SurveyResultInDBBase):
    """问卷结果模型"""
    pass


class SurveyResultInDB(SurveyResultInDBBase):
    """数据库问卷结果模型"""
    pass