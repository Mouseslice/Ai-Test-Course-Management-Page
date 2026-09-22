import pytest
from unittest.mock import MagicMock, patch

# 将 backend 目录添加到 sys.path 中
import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)

from app.services.user_state_service import UserStateService, StudentProfile
from app.schemas.participant import ParticipantCreate
from app.schemas.behavior import BehaviorEvent, EventType

# --- 模拟依赖 ---

@pytest.fixture
def mock_db_session():
    """创建一个模拟的 SQLAlchemy Session 对象。"""
    return MagicMock()

@pytest.fixture
def mock_crud_participant():
    """创建一个模拟的 participant CRUD 对象。"""
    return MagicMock()

# --- 测试用例 ---

class TestUserStateService:
    """针对 UserStateService 的单元测试套件。"""

    @patch('app.crud.crud_participant.participant')
    @patch('app.services.user_state_service.UserStateService._recover_from_history_with_snapshot')
    def test_get_or_create_profile_new_user(self, mock_recover, mock_crud_participant_patch, mock_db_session):
        """
        测试用例1: 首次访问，成功创建一个新用户。
        """
        # 1. 准备
        # 配置 mock crud，使其在 get 时返回 None，表示用户不存在
        mock_crud_participant_patch.get.return_value = None
        # 配置 create 方法返回一个模拟的 participant 对象
        mock_participant = MagicMock()
        mock_participant.id = "new_user_123"
        mock_crud_participant_patch.create.return_value = mock_participant

        # 同样需要 patch BehaviorInterpreterService，因为 UserStateService 在初始化时会导入它
        with patch('app.services.behavior_interpreter_service.BehaviorInterpreterService', MagicMock()):
            service = UserStateService()
        
        participant_id = "new_user_123"
        
        # 配置 mock，使其在被调用时设置缓存
        def mock_recover_side_effect(participant_id, db):
            service._state_cache[participant_id] = StudentProfile(participant_id, is_new_user=True)
        mock_recover.side_effect = mock_recover_side_effect
        
        # 2. 执行
        profile, is_new_user = service.get_or_create_profile(participant_id, db=mock_db_session)
        
        # 3. 断言
        assert is_new_user is True
        assert isinstance(profile, StudentProfile)
        assert profile.participant_id == participant_id
        assert profile.is_new_user is True
        
        # 验证数据库交互
        # 应该先尝试获取用户
        mock_crud_participant_patch.get.assert_called_once_with(mock_db_session, obj_id=participant_id)
        # 因为用户不存在，所以应该调用 create
        mock_crud_participant_patch.create.assert_called_once()
        # 检查传递给 create 的参数是否正确
        created_obj = mock_crud_participant_patch.create.call_args[1]['obj_in']
        assert isinstance(created_obj, ParticipantCreate)
        assert created_obj.id == participant_id
        
        # 验证核心逻辑：新用户也会调用状态恢复方法
        mock_recover.assert_called_once_with(participant_id, mock_db_session)
        
        # 验证缓存
        # 用户的 profile 应该被缓存在 _state_cache 中
        assert participant_id in service._state_cache
        assert service._state_cache[participant_id] is profile

    @patch('app.crud.crud_participant.participant')
    @patch('app.services.user_state_service.UserStateService._recover_from_history_with_snapshot')
    def test_get_or_create_profile_existing_user_cache_miss(self, mock_recover, mock_crud_participant_patch, mock_db_session):
        """
        测试用例2: 已存在的用户首次访问（缓存未命中），触发状态恢复。
        """
        # 1. 准备
        participant_id = "existing_user_456"
        
        # 模拟数据库中存在该用户
        mock_participant = MagicMock()
        mock_participant.id = participant_id
        mock_crud_participant_patch.get.return_value = mock_participant
        
        with patch('app.services.behavior_interpreter_service.BehaviorInterpreterService', MagicMock()):
            service = UserStateService()
            
        # 配置 mock，使其在被调用时设置缓存
        def mock_recover_side_effect(participant_id, db):
            service._state_cache[participant_id] = StudentProfile(participant_id, is_new_user=False)
        mock_recover.side_effect = mock_recover_side_effect
            
        # 2. 执行
        profile, is_new_user = service.get_or_create_profile(participant_id, db=mock_db_session)
        
        # 3. 断言
        assert is_new_user is False
        assert profile.participant_id == participant_id
        
        # 验证数据库交互
        # 应该尝试获取用户，且不会再创建
        mock_crud_participant_patch.get.assert_called_once_with(mock_db_session, obj_id=participant_id)
        mock_crud_participant_patch.create.assert_not_called()
        
        # 验证核心逻辑：状态恢复方法被调用
        mock_recover.assert_called_once_with(participant_id, mock_db_session)
        
        # 验证缓存
        assert participant_id in service._state_cache

    @patch('app.crud.crud_participant.participant')
    @patch('app.services.user_state_service.UserStateService._recover_from_history_with_snapshot')
    def test_get_or_create_profile_existing_user_cache_hit(self, mock_recover, mock_crud_participant_patch, mock_db_session):
        """
        测试用例3: 已存在的用户再次访问（缓存命中），不应触发数据库或恢复操作。
        """
        # 1. 准备
        participant_id = "cached_user_789"
        
        with patch('app.services.behavior_interpreter_service.BehaviorInterpreterService', MagicMock()):
            service = UserStateService()
        
        # 手动在缓存中放入一个该用户的 profile
        cached_profile = StudentProfile(participant_id, is_new_user=False)
        service._state_cache[participant_id] = cached_profile
        
        # 2. 执行
        profile, is_new_user = service.get_or_create_profile(participant_id, db=mock_db_session)
        
        # 3. 断言
        assert is_new_user is False # 因为缓存中存在，所以不是新用户
        # 返回的 profile 应该是缓存中的同一个对象实例
        assert profile is cached_profile
        
        # 验证核心逻辑：因为缓存命中，不应该有任何数据库或恢复操作
        mock_crud_participant_patch.get.assert_not_called()
        mock_crud_participant_patch.create.assert_not_called()
        mock_recover.assert_not_called()

    @patch('app.services.user_state_service.crud_event')
    @patch('app.services.behavior_interpreter_service.BehaviorInterpreterService')
    def test_recovery_from_snapshot(self, mock_interpreter_class, mock_crud_event, mock_db_session):
        """
        测试用例4: 详细测试状态恢复流程 - 从快照恢复。
        """
        # 1. 准备
        participant_id = "user_with_snapshot"

        # mock_interpreter_class 是 BehaviorInterpreterService 类的 mock
        # 当 UserStateService 初始化时，self.interpreter 会被设置为这个类的实例
        mock_interpreter_instance = mock_interpreter_class.return_value

        # 模拟一个最新的快照
        mock_snapshot = MagicMock()
        mock_snapshot.event_data = {
            "participant_id": participant_id,
            "bkt_model": {
                "topic1": {"mastery_prob": 0.8}
            }
        }
        mock_snapshot.timestamp = "2023-01-01T12:00:00Z"
        mock_crud_event.get_latest_snapshot.return_value = mock_snapshot

        # 模拟快照之后的事件
        mock_event_after = MagicMock()
        mock_crud_event.get_after_timestamp.return_value = [mock_event_after]

        # 模拟 BehaviorEvent.model_validate
        with patch('app.schemas.behavior.BehaviorEvent.model_validate', side_effect=lambda x: x):
            with patch('app.services.behavior_interpreter_service.behavior_interpreter_service') as mock_behavior_interpreter_service:
                service = UserStateService()
                service._recover_from_history_with_snapshot(participant_id, db=mock_db_session)

                # 验证解释器的实例方法被调用
                mock_behavior_interpreter_service.interpret_event.assert_called_once()

        # 3. 断言
        mock_crud_event.get_latest_snapshot.assert_called_once_with(mock_db_session, participant_id=participant_id)
        mock_crud_event.get_after_timestamp.assert_called_once_with(mock_db_session, participant_id=participant_id, timestamp=mock_snapshot.timestamp)
        
        profile = service._state_cache[participant_id]
        assert profile.bkt_model["topic1"].get_mastery_prob() == 0.8

    @patch('app.services.user_state_service.crud_event')
    @patch('app.services.behavior_interpreter_service.BehaviorInterpreterService')
    def test_recovery_from_scratch(self, mock_interpreter_class, mock_crud_event, mock_db_session):
        """
        测试用例5: 详细测试状态恢复流程 - 无快照，从零开始恢复。
        """
        # 1. 准备
        participant_id = "user_without_snapshot"
        mock_interpreter_instance = mock_interpreter_class.return_value

        # 模拟没有快照
        mock_crud_event.get_latest_snapshot.return_value = None

        # 模拟有3个历史事件
        mock_events = [MagicMock() for _ in range(3)]
        mock_crud_event.get_by_participant.return_value = mock_events

        # 模拟 BehaviorEvent.model_validate
        with patch('app.schemas.behavior.BehaviorEvent.model_validate', side_effect=lambda x: x):
            with patch('app.services.behavior_interpreter_service.behavior_interpreter_service') as mock_behavior_interpreter_service:
                service = UserStateService()
                service._recover_from_history_with_snapshot(participant_id, db=mock_db_session)

                # 验证解释器的实例方法被调用
                assert mock_behavior_interpreter_service.interpret_event.call_count == 3

        # 3. 断言
        mock_crud_event.get_latest_snapshot.assert_called_once_with(mock_db_session, participant_id=participant_id)
        mock_crud_event.get_by_participant.assert_called_once_with(mock_db_session, participant_id=participant_id)

    @patch('app.services.user_state_service.BKTModel')
    def test_update_bkt_on_submission(self, mock_bkt_model_class):
        """
        测试用例6: 验证 BKT 模型是否在提交测试后被正确更新。
        """
        # 1. 准备
        participant_id = "bkt_user"
        topic_id = "loops"
        
        # 模拟 BKTModel 实例和它的 update 方法
        mock_bkt_instance = MagicMock()
        mock_bkt_instance.update.return_value = 0.75 # 模拟更新后的掌握度
        # 当 BKTModel 类被实例化时，返回我们的模拟实例
        mock_bkt_model_class.return_value = mock_bkt_instance
        
        with patch('app.services.behavior_interpreter_service.BehaviorInterpreterService', MagicMock()):
            service = UserStateService()
        
        # 确保用户 profile 已存在于缓存中
        service.get_or_create_profile(participant_id, db=None) # 在此测试中我们不关心数据库
        
        # 2. 执行
        # 模拟一次正确的提交
        mastery_prob = service.update_bkt_on_submission(participant_id, topic_id, is_correct=True)
        
        # 3. 断言
        assert mastery_prob == 0.75
        
        # 验证 BKTModel 是否被正确地实例化（如果之前不存在）和调用
        profile = service._state_cache[participant_id]
        assert topic_id in profile.bkt_model
        # 验证 update 方法被以正确的参数调用
        mock_bkt_instance.update.assert_called_once_with(True)
        
        # 再次调用，验证模型会复用而不是新建
        mock_bkt_instance.update.return_value = 0.85
        mastery_prob_2 = service.update_bkt_on_submission(participant_id, topic_id, is_correct=True)
        assert mastery_prob_2 == 0.85
        # 确保 BKTModel 类没有被再次实例化
        mock_bkt_model_class.assert_called_once()
        # 确保 update 方法被调用了两次
        assert mock_bkt_instance.update.call_count == 2

    @patch('app.services.behavior_interpreter_service.BehaviorInterpreterService', MagicMock())
    def test_handle_event(self, mock_db_session):
        """
        测试 handle_event 方法，验证事件处理和快照创建流程。
        """
        # 1. 准备
        service = UserStateService()
        participant_id = "test_user_123"
        
        # 创建一个测试提交事件
        event = BehaviorEvent(
            participant_id=participant_id,
            event_type=EventType.TEST_SUBMISSION,
            event_data={"topic_id": "loops", "code": {"html": "", "css": "", "js": ""}}
        )
        
        # 2. 执行
        with patch('app.services.behavior_interpreter_service.behavior_interpreter_service') as mock_behavior_interpreter_service:
            service.handle_event(event, db=mock_db_session)
        
        # 3. 断言
        # 验证行为解释器被调用
        mock_behavior_interpreter_service.interpret_event.assert_called_once()
        
        # 验证快照检查被调用
        # 注意：这里我们不直接测试 _maybe_create_snapshot 的内部逻辑，
        # 而是验证 handle_event 的整体行为

    @patch('app.services.user_state_service.crud_event')
    @patch('app.services.behavior_interpreter_service.BehaviorInterpreterService', MagicMock())
    def test_maybe_create_snapshot_and_cleanup(self, mock_crud_event, mock_db_session):
        """
        测试快照创建和清理功能。
        """
        # 1. 准备
        service = UserStateService()
        participant_id = "snapshot_user_456"
        
        # 在缓存中创建一个用户档案
        profile = StudentProfile(participant_id, is_new_user=False)
        service._state_cache[participant_id] = profile
        
        # 配置模拟对象的返回值
        mock_crud_event.get_latest_snapshot.return_value = None
        mock_crud_event.get_count_by_participant.return_value = 5  # 超过阈值
        
        # 2. 执行
        service.maybe_create_snapshot(participant_id, db=mock_db_session)
        
        # 3. 断言
        # 验证创建快照的方法被调用
        mock_crud_event.create_from_behavior.assert_called_once()
        
        # 验证清理旧快照的方法被调用
        mock_crud_event.get_all_snapshots.assert_called_once()

    @patch('app.services.user_state_service.crud_event')
    @patch('app.services.behavior_interpreter_service.BehaviorInterpreterService', MagicMock())
    def test_recovery_edge_cases(self, mock_crud_event, mock_db_session):
        """
        测试状态恢复的边界情况。
        """
        # 1. 准备
        service = UserStateService()
        participant_id = "edge_case_user"
        
        # 测试从零开始恢复但没有历史事件的情况
        mock_crud_event.get_latest_snapshot.return_value = None
        mock_crud_event.get_by_participant.return_value = []  # 没有历史事件
        
        # 2. 执行
        service._recover_from_history_with_snapshot(participant_id, db=mock_db_session)
        
        # 3. 断言
        # 验证创建了新的用户档案
        assert participant_id in service._state_cache
        assert service._state_cache[participant_id].is_new_user is True

    def test_bkt_model_serialization(self):
        """
        测试 BKT 模型的序列化和反序列化。
        """
        # 1. 准备
        participant_id = "serialization_user"
        profile = StudentProfile(participant_id)
        
        # 添加一个 BKT 模型
        from app.models.bkt import BKTModel
        bkt_model = BKTModel()
        bkt_model.update(True)  # 更新模型状态
        profile.bkt_model["topic1"] = bkt_model
        
        # 2. 执行
        # 序列化
        serialized = profile.to_dict()
        
        # 反序列化
        deserialized_profile = StudentProfile.from_dict(serialized)
        
        # 3. 断言
        assert deserialized_profile.participant_id == participant_id
        assert "topic1" in deserialized_profile.bkt_model
        assert isinstance(deserialized_profile.bkt_model["topic1"], BKTModel)
        # 验证掌握概率被正确恢复
        assert deserialized_profile.bkt_model["topic1"].get_mastery_prob() == bkt_model.get_mastery_prob()
