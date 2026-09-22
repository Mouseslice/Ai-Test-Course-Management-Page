# backend/tests/test_knowledge_graph_endpoints.py
import sys
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open
import json
from dotenv import load_dotenv
from fastapi import HTTPException

# 手动加载项目根目录下的 .env 文件
load_dotenv(Path(__file__).parent.parent.parent / ".env")
# 将 backend 目录添加到 sys.path 中
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)

from app.main import app
from app.core.config import settings
from app.schemas.knowledge_graph import KnowledgeGraph
from app.schemas.response import StandardResponse
from app.api.endpoints.knowledge_graph import _knowledge_graph_cache

client = TestClient(app)

# 准备测试用的知识图谱数据
TEST_KNOWLEDGE_GRAPH_DATA = {
    "nodes": [
        {"data": {"id": "chapter1", "label": "测试模块1","type": "chapter"}},
        {"data": {"id": "node1", "label": "测试节点1", "type": "knowledge" }}
    ],
    "edges": [
        {"data": {"source": "chapter1", "target": "node1"}}
    ],
    "dependent_edges": [
        {"data": {"source": "chapter1", "target": "node1"}}
    ]
}

class TestKnowledgeGraphEndpoints:
    """测试知识图谱相关接口"""

    def setup_method(self):
        """在每个测试方法前执行，清除缓存"""
        global _knowledge_graph_cache
        _knowledge_graph_cache = None

    def test_get_knowledge_graph_success(self, tmp_path):
        """测试成功获取知识图谱"""
        # 创建临时测试文件
        test_file = tmp_path / "knowledge_graph.json"
        test_file.write_text(json.dumps(TEST_KNOWLEDGE_GRAPH_DATA), encoding="utf-8")

        with patch("app.api.endpoints.knowledge_graph.GRAPH_FILE_PATH", str(test_file)):
            response = client.get(f"{settings.API_V1_STR}/knowledge-graph")
            
            print("Response status:", response.status_code)
            print("Response body:", response.text)
            
            assert response.status_code == 200
            response_data = response.json()
            
            # 验证 StandardResponse 结构
            assert "code" in response_data
            assert "message" in response_data
            assert "data" in response_data
            
            # 验证知识图谱数据结构
            graph_data = response_data["data"]
            assert "nodes" in graph_data
            assert "edges" in graph_data
            assert "dependent_edges" in graph_data
            assert len(graph_data["nodes"]) == 2
            assert len(graph_data["edges"]) == 1
            assert len(graph_data["dependent_edges"]) == 1

    def test_get_knowledge_graph_file_not_found(self, tmp_path):
        """测试文件不存在时返回空数据"""
        global _knowledge_graph_cache
        _knowledge_graph_cache = None
        
        non_existent_file = tmp_path / "nonexistent.json"
        
        with patch("app.api.endpoints.knowledge_graph.GRAPH_FILE_PATH", str(non_existent_file)):
            response = client.get(f"{settings.API_V1_STR}/knowledge-graph")
            
            # 验证返回了空数据
            response_data = response.json()
            assert "data" in response_data
            assert not response_data["data"].get("nodes")  # 空节点列表

    def test_get_knowledge_graph_invalid_json(self, tmp_path):
        """测试无效JSON时返回空数据"""
        global _knowledge_graph_cache
        _knowledge_graph_cache = None
        
        test_file = tmp_path / "knowledge_graph.json"
        test_file.write_text("invalid json", encoding="utf-8")
        
        with patch("app.api.endpoints.knowledge_graph.GRAPH_FILE_PATH", str(test_file)):
            response = client.get(f"{settings.API_V1_STR}/knowledge-graph")
            
            # 验证返回了空数据或错误信息
            response_data = response.json()
            assert "data" in response_data
            if response_data["data"].get("nodes"):
                assert response_data["data"]["nodes"][0]["data"]["id"] == "default_node"
            else:
                assert not response_data["data"].get("nodes")
                
    def test_api_response_format(self, tmp_path):
        """详细测试API返回的数据格式"""
        # 1. 准备测试数据
        test_data = {
            "nodes": [
                {"data": {"id": "chapter1", "label": "模块一", "type": "chapter", "difficulty": 1}},
                {"data": {"id": "node1", "label": "节点1", "type": "knowledge", "difficulty": 2}}
            ],
            "edges": [
                {"data": {"source": "chapter1", "target": "node1", "edge_type": "hierarchy"}}
            ],
            "dependent_edges": [
                {"data": {"source": "chapter1", "target": "node1", "edge_type": "dependency"}}
            ]
        }
        
        # 2. 创建临时测试文件
        test_file = tmp_path / "knowledge_graph.json"
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        with patch("app.api.endpoints.knowledge_graph.GRAPH_FILE_PATH", str(test_file)):
            response = client.get(f"{settings.API_V1_STR}/knowledge-graph")
            
            # 3. 验证基本响应结构
            assert response.status_code == 200
            response_data = response.json()
            
            # 4. 检查StandardResponse结构
            assert set(response_data.keys()) == {"code", "message", "data"}
            assert response_data["code"] == 200
            assert response_data["message"] == "success"
            
            # 5. 检查KnowledgeGraph数据结构
            graph_data = response_data["data"]
            assert isinstance(graph_data, dict)
            assert set(graph_data.keys()) == {"nodes", "edges", "dependent_edges", "metadata"}
            
            # 6. 详细检查节点结构
            assert isinstance(graph_data["nodes"], list)
            for node in graph_data["nodes"]:
                assert set(node.keys()) == {"data"}
                node_data = node["data"]
                assert set(node_data.keys()) == {"id", "label", "type", "description", "difficulty"}
                assert isinstance(node_data["id"], str)
                assert isinstance(node_data["label"], str)
                assert node_data["type"] in ["chapter", "knowledge", None]  # 允许为None
                assert node_data["description"] is None or isinstance(node_data["description"], str)
                assert node_data["difficulty"] is None or isinstance(node_data["difficulty"], int)
            
            # 7. 详细检查边结构
            for edge_type in ["edges", "dependent_edges"]:
                assert isinstance(graph_data[edge_type], list)
                for edge in graph_data[edge_type]:
                    assert set(edge.keys()) == {"data"}
                    edge_data = edge["data"]
                    assert set(edge_data.keys()) == {"source", "target", "edge_type", "weight", "label"}
                    assert isinstance(edge_data["source"], str)
                    assert isinstance(edge_data["target"], str)
                    assert edge_data["edge_type"] in ["hierarchy", "dependency", "prerequisite", None]
                    assert edge_data["weight"] is None or isinstance(edge_data["weight"], float)
                    assert edge_data["label"] is None or isinstance(edge_data["label"], str)
            
            # 8. 检查metadata
            assert graph_data["metadata"] is None or isinstance(graph_data["metadata"], dict)
            
            # 9. 打印完整的响应结构供参考
            print("\n完整的API响应结构:")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
    def test_knowledge_graph_response_structure(self, tmp_path):
        """测试返回的知识图谱数据结构符合预期"""
        # 创建临时测试文件
        test_file = tmp_path / "knowledge_graph.json"
        test_file.write_text(json.dumps(TEST_KNOWLEDGE_GRAPH_DATA), encoding="utf-8")

        with patch("app.api.endpoints.knowledge_graph.GRAPH_FILE_PATH", str(test_file)):
            response = client.get(f"{settings.API_V1_STR}/knowledge-graph")
            assert response.status_code == 200
            
            # 验证 StandardResponse 结构
            try:
                StandardResponse[KnowledgeGraph](**response.json())
            except Exception as e:
                pytest.fail(f"返回的数据不符合StandardResponse[KnowledgeGraph]模型: {str(e)}")