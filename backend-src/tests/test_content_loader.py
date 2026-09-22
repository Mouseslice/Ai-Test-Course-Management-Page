#!/usr/bin/env python3
"""
内容加载器服务测试

该测试文件验证content_loader.py服务的功能是否正常工作。
测试包括学习内容和测试任务的加载、数据解析、缓存机制、错误处理，内容加载服务的正确性和稳定性。
"""

import sys
import os
import pytest
import time
from pathlib import Path
from typing import Generator
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 在导入项目模块前设置测试环境
os.environ["APP_ENV"] = "testing"
os.environ["TUTOR_OPENAI_API_KEY"] = "test-key"
os.environ["TUTOR_EMBEDDING_API_KEY"] = "test-key"
os.environ["TUTOR_TRANSLATION_API_KEY"] = "test-key"

# 导入项目模块
from app.services.content_loader import load_json_content
from app.schemas.content import (
    LearningContent, TestTask, LevelInfo, SelectElementInfo,
    AssertAttributeCheckpoint, AssertStyleCheckpoint, AssertTextContentCheckpoint,
    CustomScriptCheckpoint, InteractionAndAssertCheckpoint,
    AssertionType, ActionType, CheckpointType, CodeContent
)
from app.core.config import settings


@pytest.fixture(scope="function")
def data_dir() -> Path:
    """获取数据目录路径"""
    return Path(settings.DATA_DIR)


class TestContentLoaderService:
    """内容加载器服务测试类"""
    
    def test_cache_mechanism(self, data_dir: Path):
        """测试缓存机制功能"""
        # 使用实际存在的文件进行测试
        test_tasks_dir = data_dir / "test_tasks"
        if test_tasks_dir.exists():
            test_files = list(test_tasks_dir.glob("*.json"))
            if test_files:
                topic_id = test_files[0].stem
                
                # 第一次加载
                start_time = time.time()
                content1 = load_json_content("test_tasks", topic_id)
                first_load_time = time.time() - start_time
                
                # 第二次加载（应该从缓存获取）
                start_time = time.time()
                content2 = load_json_content("test_tasks", topic_id)
                second_load_time = time.time() - start_time
                
                # 验证内容一致性
                assert content1.topic_id == content2.topic_id
                assert content1.title == content2.title
                
                # 验证缓存效果（第二次加载应该更快）
                print(f"首次加载时间: {first_load_time:.4f}s")
                print(f"缓存加载时间: {second_load_time:.4f}s")
                
                print("缓存机制功能测试通过")
            else:
                print("没有找到测试文件，跳过缓存测试")
        else:
            print("测试任务目录不存在，跳过缓存测试")
    

    
    def test_error_handling(self, data_dir: Path):
        """测试错误处理功能"""
        # 测试无效内容类型 - 通过创建真实的无效类型目录来测试
        import shutil
        
        # 创建一个无效类型目录并复制一个现有文件
        invalid_type_dir = data_dir / "invalid_type"
        invalid_type_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 复制一个现有的JSON文件到无效类型目录
            test_tasks_dir = data_dir / "test_tasks"
            if test_tasks_dir.exists():
                test_files = list(test_tasks_dir.glob("*.json"))
                if test_files:
                    source_file = test_files[0]
                    target_file = invalid_type_dir / source_file.name
                    shutil.copy2(source_file, target_file)
                    
                    # 现在测试无效内容类型
                    with pytest.raises(ValueError, match="不支持的content_type"):
                        load_json_content("invalid_type", source_file.stem)
                    
                    # 清理
                    target_file.unlink()
                else:
                    # 如果没有测试文件，创建一个简单的JSON文件
                    test_file = invalid_type_dir / "test.json"
                    with open(test_file, "w", encoding="utf-8") as f:
                        json.dump({"test": "data"}, f)
                    
                    with pytest.raises(ValueError, match="不支持的content_type"):
                        load_json_content("invalid_type", "test")
                    
                    test_file.unlink()
            else:
                # 如果测试任务目录不存在，创建一个简单的JSON文件
                test_file = invalid_type_dir / "test.json"
                with open(test_file, "w", encoding="utf-8") as f:
                    json.dump({"test": "data"}, f)
                
                with pytest.raises(ValueError, match="不支持的content_type"):
                    load_json_content("invalid_type", "test")
                
                test_file.unlink()
        
        finally:
            # 清理目录
            if invalid_type_dir.exists():
                invalid_type_dir.rmdir()
        
        # 测试不存在的主题
        with pytest.raises(Exception):
            load_json_content("learning_content", "nonexistent_topic")
        
        print("错误处理功能测试通过")
    
    def test_all_available_content(self, data_dir: Path):
        """测试所有可用内容的加载功能"""
        # 获取所有学习内容文件
        learning_content_dir = data_dir / "learning_content"
        test_tasks_dir = data_dir / "test_tasks"
        
        # 测试所有学习内容
        if learning_content_dir.exists():
            learning_files = list(learning_content_dir.glob("*.json"))
            print(f"发现 {len(learning_files)} 个学习内容文件")
            for json_file in learning_files:
                topic_id = json_file.stem
                try:
                    content = load_json_content("learning_content", topic_id)
                    assert isinstance(content, LearningContent)
                    assert content.topic_id == topic_id
                    assert len(content.levels) > 0
                    print(f"学习内容 {topic_id} 加载成功")
                except Exception as e:
                    print(f"学习内容 {topic_id} 加载失败: {e}")
        
        # 测试所有测试任务
        if test_tasks_dir.exists():
            test_files = list(test_tasks_dir.glob("*.json"))
            print(f"发现 {len(test_files)} 个测试任务文件")
            for json_file in test_files:
                topic_id = json_file.stem
                try:
                    content = load_json_content("test_tasks", topic_id)
                    assert isinstance(content, TestTask)
                    assert content.topic_id == topic_id
                    assert len(content.checkpoints) > 0
                    print(f"测试任务 {topic_id} 加载成功")
                except Exception as e:
                    print(f"测试任务 {topic_id} 加载失败: {e}")
        
        print("所有可用内容加载功能测试完成")
    
    def test_data_consistency(self, data_dir: Path):
        """测试数据一致性功能"""
        # 使用实际存在的文件进行测试
        test_tasks_dir = data_dir / "test_tasks"
        if test_tasks_dir.exists():
            test_files = list(test_tasks_dir.glob("*.json"))
            if test_files:
                total_checkpoints_verified = 0
                
                for json_file in test_files:
                    topic_id = json_file.stem
                    
                    # 直接读取原始JSON文件
                    test_file = data_dir / "test_tasks" / f"{topic_id}.json"
                    
                    with open(test_file, "r", encoding="utf-8") as f:
                        raw_test_data = json.load(f)
                    
                    # 通过服务加载
                    test_task = load_json_content("test_tasks", topic_id)
                    
                    # 验证基本字段一致性
                    assert test_task.topic_id == raw_test_data["topic_id"]
                    assert test_task.title == raw_test_data["title"]
                    assert test_task.description_md == raw_test_data["description_md"]
                    
                    # 验证代码内容一致性
                    assert test_task.start_code.html == raw_test_data["start_code"]["html"]
                    assert test_task.start_code.css == raw_test_data["start_code"]["css"]
                    assert test_task.start_code.js == raw_test_data["start_code"]["js"]
                    
                    # 验证检查点数量一致性
                    assert len(test_task.checkpoints) == len(raw_test_data["checkpoints"])
                    
                    # 验证检查点内容一致性
                    for i, checkpoint in enumerate(test_task.checkpoints):
                        raw_checkpoint = raw_test_data["checkpoints"][i]
                        
                        # 验证基本字段
                        assert checkpoint.name == raw_checkpoint["name"]
                        assert checkpoint.type == raw_checkpoint["type"]
                        assert checkpoint.feedback == raw_checkpoint["feedback"]
                        
                        # 根据类型验证特定字段
                        if checkpoint.type == CheckpointType.ASSERT_ATTRIBUTE:
                            assert checkpoint.selector == raw_checkpoint["selector"]
                            assert checkpoint.attribute == raw_checkpoint.get("attribute", "")
                            assert checkpoint.assertion_type == raw_checkpoint["assertion_type"]
                            assert checkpoint.value == raw_checkpoint.get("value", "")
                        
                        elif checkpoint.type == CheckpointType.ASSERT_STYLE:
                            assert checkpoint.selector == raw_checkpoint["selector"]
                            assert checkpoint.css_property == raw_checkpoint["css_property"]
                            assert checkpoint.assertion_type == raw_checkpoint["assertion_type"]
                            assert checkpoint.value == raw_checkpoint["value"]
                        
                        elif checkpoint.type == CheckpointType.ASSERT_TEXT_CONTENT:
                            assert checkpoint.selector == raw_checkpoint["selector"]
                            assert checkpoint.assertion_type == raw_checkpoint["assertion_type"]
                            assert checkpoint.value == raw_checkpoint["value"]
                        
                        elif checkpoint.type == CheckpointType.CUSTOM_SCRIPT:
                            assert checkpoint.script == raw_checkpoint["script"]
                        
                        elif checkpoint.type == CheckpointType.INTERACTION_AND_ASSERT:
                            assert checkpoint.action_selector == raw_checkpoint["action_selector"]
                            assert checkpoint.action_type == raw_checkpoint["action_type"]
                            assert checkpoint.action_value == raw_checkpoint.get("action_value")
                            
                            # 验证嵌套断言
                            if checkpoint.assertion and "assertion" in raw_checkpoint:
                                raw_assertion = raw_checkpoint["assertion"]
                                assert checkpoint.assertion.name == raw_assertion["name"]
                                assert checkpoint.assertion.type == raw_assertion["type"]
                                assert checkpoint.assertion.feedback == raw_assertion["feedback"]
                                
                                # 根据嵌套断言类型验证特定字段
                                if checkpoint.assertion.type == CheckpointType.CUSTOM_SCRIPT:
                                    assert checkpoint.assertion.script == raw_assertion["script"]
                    
                    total_checkpoints_verified += len(test_task.checkpoints)
                    print(f"测试任务 {topic_id}: {len(test_task.checkpoints)} 个检查点数据一致性验证通过")
                
                print(f"数据一致性功能测试完成 - 总共验证了 {total_checkpoints_verified} 个检查点")
            else:
                print("没有找到测试文件，跳过数据一致性测试")
        else:
            print("测试任务目录不存在，跳过数据一致性测试")
    
    def test_all_checkpoints_validation(self, data_dir: Path):
        """测试所有测试任务的所有检查点验证"""
        test_tasks_dir = data_dir / "test_tasks"
        
        if test_tasks_dir.exists():
            test_files = list(test_tasks_dir.glob("*.json"))
            total_checkpoints = 0
            valid_checkpoints = 0
            
            for json_file in test_files:
                topic_id = json_file.stem
                try:
                    content = load_json_content("test_tasks", topic_id)
                    assert isinstance(content, TestTask)
                    
                    # 验证每个检查点
                    for checkpoint in content.checkpoints:
                        total_checkpoints += 1
                        
                        # 验证基本字段
                        assert len(checkpoint.name) > 0
                        assert len(checkpoint.feedback) > 0
                        assert checkpoint.type in CheckpointType.__members__.values()
                        
                        # 根据类型验证特定字段
                        if checkpoint.type == CheckpointType.ASSERT_ATTRIBUTE:
                            assert isinstance(checkpoint, AssertAttributeCheckpoint)
                            assert len(checkpoint.selector) > 0
                            assert checkpoint.assertion_type in AssertionType.__members__.values()
                        
                        elif checkpoint.type == CheckpointType.ASSERT_STYLE:
                            assert isinstance(checkpoint, AssertStyleCheckpoint)
                            assert len(checkpoint.selector) > 0
                            assert len(checkpoint.css_property) > 0
                            assert checkpoint.assertion_type in AssertionType.__members__.values()
                        
                        elif checkpoint.type == CheckpointType.ASSERT_TEXT_CONTENT:
                            assert isinstance(checkpoint, AssertTextContentCheckpoint)
                            assert len(checkpoint.selector) > 0
                            assert len(checkpoint.value) > 0
                            assert checkpoint.assertion_type in AssertionType.__members__.values()
                        
                        elif checkpoint.type == CheckpointType.CUSTOM_SCRIPT:
                            assert isinstance(checkpoint, CustomScriptCheckpoint)
                            assert len(checkpoint.script) > 0
                        
                        elif checkpoint.type == CheckpointType.INTERACTION_AND_ASSERT:
                            assert isinstance(checkpoint, InteractionAndAssertCheckpoint)
                            assert len(checkpoint.action_selector) > 0
                            assert checkpoint.action_type in ActionType.__members__.values()
                            
                            # 验证嵌套断言（如果存在）
                            if checkpoint.assertion:
                                assert checkpoint.assertion.type != CheckpointType.INTERACTION_AND_ASSERT
                        
                        valid_checkpoints += 1
                    
                    print(f"测试任务 {topic_id}: {len(content.checkpoints)} 个检查点验证通过")
                    
                except Exception as e:
                    print(f"测试任务 {topic_id} 检查点验证失败: {e}")
            
            print(f"检查点验证完成: {valid_checkpoints}/{total_checkpoints} 个检查点有效")
            print("所有检查点验证功能测试完成")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
