from typing import List
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.user_progress import UserProgress
from app.schemas.user_progress import UserProgressCreate, UserProgressUpdate

class CRUDProgress(CRUDBase[UserProgress, UserProgressCreate, UserProgressUpdate]):
    def get_completed_topics_by_user(self, db: Session, *, participant_id: str) -> List[str]:
        """
        查询指定用户已完成的 topic_id 列表
        """
        progress_records = self.get_multi(
            db, 
            filter_conditions={"participant_id": participant_id}
        )
        return [record.topic_id for record in progress_records]

# 实例化并暴露给 API 层使用
progress = CRUDProgress(UserProgress)
