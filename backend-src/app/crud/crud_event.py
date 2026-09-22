from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
from app.crud.base_improved import CRUDBaseImproved, SortDirection
from app.models.event import EventLog
from app.schemas.behavior import BehaviorEvent

class CRUDEvent(CRUDBaseImproved[EventLog, BehaviorEvent, BehaviorEvent]):
    def get_by_participant(self, db: Session, *, participant_id: str) -> List[EventLog]:
        """获取指定参与者的所有事件日志，按时间戳排序。
        
        Args:
            db: 数据库会话
            participant_id: 参与者ID
            
        Returns:
            List[EventLog]: 按时间戳排序的事件日志列表
        """
        return self.get_multi(
            db, 
            filter_conditions={"participant_id": participant_id},
            sort_by="timestamp"
        )

    def get_latest_snapshot(self, db: Session, *, participant_id: str) -> Optional[EventLog]:
        """获取指定参与者的最新状态快照。
        
        Args:
            db: 数据库会话
            participant_id: 参与者ID
            
        Returns:
            Optional[EventLog]: 最新的状态快照，如果不存在则返回None
        """
        results = self.get_multi(
            db,
            filter_conditions={
                "participant_id": participant_id,
                "event_type": "state_snapshot"
            },
            sort_by=[("timestamp", SortDirection.DESC)],
            limit=1
        )
        return results[0] if results else None

    def get_after_timestamp(self, db: Session, *, participant_id: str, timestamp: datetime) -> List[EventLog]:
        """获取指定参与者在指定时间戳之后的所有事件日志。
        
        Args:
            db: 数据库会话
            participant_id: 参与者ID
            timestamp: 时间戳
            
        Returns:
            List[EventLog]: 指定时间戳之后的事件日志列表
        """
        return self.get_multi(
            db,
            filter_conditions={
                "participant_id": participant_id,
                "timestamp": {"gt": timestamp}
            },
            sort_by="timestamp"
        )

    def get_count_after_timestamp(self, db: Session, *, participant_id: str, timestamp: datetime) -> int:
        """获取指定参与者在指定时间戳之后的事件日志数量。
        
        Args:
            db: 数据库会话
            participant_id: 参与者ID
            timestamp: 时间戳
            
        Returns:
            int: 事件日志数量
        """
        return self.get_count(
            db,
            filter_conditions={
                "participant_id": participant_id,
                "timestamp": {"gt": timestamp}
            }
        )
        
    def get_count_by_participant(self, db: Session, *, participant_id: str) -> int:
        """获取指定参与者的所有事件日志数量。
        
        Args:
            db: 数据库会话
            participant_id: 参与者ID
            
        Returns:
            int: 事件日志数量
        """
        return self.get_count(
            db,
            filter_conditions={"participant_id": participant_id}
        )

    def get_all_snapshots(self, db: Session, *, participant_id: str) -> List[EventLog]:
        """获取指定参与者的所有状态快照，按时间戳升序排列。
        
        Args:
            db: 数据库会话
            participant_id: 参与者ID
            
        Returns:
            List[EventLog]: 按时间戳升序排列的状态快照列表
        """
        return self.get_multi(
            db,
            filter_conditions={
                "participant_id": participant_id,
                "event_type": "state_snapshot"
            },
            sort_by=[("timestamp", SortDirection.ASC)]
        )

    def create_from_behavior(self, db: Session, *, obj_in: BehaviorEvent) -> EventLog:
        """根据行为事件创建事件日志记录。
        
        Args:
            db: 数据库会话
            obj_in: 行为事件数据
            
        Returns:
            EventLog: 创建的事件日志记录
        """
        return self.create(db, obj_in=obj_in)

event = CRUDEvent(EventLog)
