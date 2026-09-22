from app.crud.base import CRUDBase
from app.models.survey_result import SurveyResult
from app.schemas.survey import SurveyResultCreate, SurveyResultUpdate


class CRUDSurveyResult(CRUDBase[SurveyResult, SurveyResultCreate, SurveyResultUpdate]):
    pass


# 实例化并暴露给 API 层使用
survey_result = CRUDSurveyResult(SurveyResult)