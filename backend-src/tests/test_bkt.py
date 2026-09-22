import pytest
import sys
import os
import json

# 获取项目根目录路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 添加backend目录到Python路径
backend_path = os.path.join(project_root, 'backend')
sys.path.insert(0, backend_path)

from app.models.bkt import BKTModel

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "bkt_test_cases.json")

# 验证路径是否存在
if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(
        f"测试数据文件未找到，预期路径: {DATA_FILE}\n"
        f"当前工作目录: {os.getcwd()}"
    )
class TestBKTModel:
    def test_default_initialization(self):
        """测试默认参数初始化"""
        model = BKTModel()
        assert model.p_init == 0.2
        assert model.get_mastery_prob() == 0.2

    def test_custom_initialization(self):
        """测试自定义参数初始化"""
        params = {
            'p_init': 0.5,
            'p_transit': 0.3,
            'p_slip': 0.05,
            'p_guess': 0.25
        }
        model = BKTModel(params)
        assert model.p_init == 0.5
        assert model.p_transit == 0.3
        assert model.p_slip == 0.05
        assert model.p_guess == 0.25
        assert model.get_mastery_prob() == 0.5

    def test_update_correct_answer(self):
        """测试答对题后掌握概率上升"""
        model = BKTModel({'p_init': 0.2, 'p_transit': 0.15, 'p_slip': 0.1, 'p_guess': 0.2})
        old_prob = model.get_mastery_prob()
        new_prob = model.update(is_correct=True)
        assert new_prob > old_prob
        assert 0 <= new_prob <= 1

    def test_update_wrong_answer(self):
        """测试答错题后掌握概率下降"""
        model = BKTModel({'p_init': 0.8, 'p_transit': 0.15, 'p_slip': 0.1, 'p_guess': 0.2})
        old_prob = model.get_mastery_prob()
        new_prob = model.update(is_correct=False)
        assert new_prob < old_prob
        assert 0 <= new_prob <= 1

    def test_update_probability_bounds(self):
        """测试概率边界值（不能超过[0,1]）"""
        model = BKTModel({'p_init': 1.0, 'p_transit': 0.5, 'p_slip': 0.0, 'p_guess': 0.0})
        prob = model.update(is_correct=True)
        assert 0.0 <= prob <= 1.0

        model = BKTModel({'p_init': 0.0, 'p_transit': 0.0, 'p_slip': 1.0, 'p_guess': 0.0})
        prob = model.update(is_correct=False)
        assert 0.0 <= prob <= 1.0

    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        model = BKTModel({'p_init': 0.3, 'p_transit': 0.2, 'p_slip': 0.05, 'p_guess': 0.25})
        model.update(True)  # 更新一次状态
        data = model.to_dict()
        assert isinstance(data, dict)
        new_model = BKTModel.from_dict(data)
        assert new_model.to_dict() == data

    def test_str_representation(self):
        """测试 __str__ 方法输出格式"""
        model = BKTModel()
        assert "BKTModel" in str(model)
        assert "mastery_prob" in str(model)

    @pytest.mark.parametrize("answers", [
        [True, True, False, True],
        [False, False, True, True],
        [True, False, True, False]
    ])
    def test_update_sequence(self, answers):
        """测试一组答题序列的掌握概率变化"""
        model = BKTModel()
        probs = []
        for ans in answers:
            probs.append(model.update(ans))
        assert all(0.0 <= p <= 1.0 for p in probs)

    def test_update_with_zero_observation_prob(self):
        """测试当观测概率为0时的更新，确保不会除以零"""
        # 场景1: 答错时，一个已完全掌握知识点（掌握概率为1）的学生，
        # 在一个“不可能失误”（p_slip=0）的模型中答错了。
        # 此时 P(答错|掌握) = p_slip = 0， P(答错|未掌握)无关紧要。
        # 观测概率 p_obs = 1.0 * 0.0 + (1-1.0) * ... = 0
        model1 = BKTModel({'p_init': 1.0, 'p_transit': 0.1, 'p_slip': 0.0, 'p_guess': 0.2})
        try:
            new_prob1 = model1.update(is_correct=False)
            assert 0 <= new_prob1 <= 1, "概率应在有效范围内"
        except ZeroDivisionError:
            pytest.fail("BKTModel.update() 触发了 ZeroDivisionError")

        # 场景2: 答对时，一个完全未掌握知识点（掌握概率为0）的学生，
        # 在一个“不可能猜对”（p_guess=0）的模型中答对了。
        # 此时 P(答对|未掌握) = p_guess = 0, P(答对|掌握)无关紧要。
        # 观测概率 p_obs = 0.0 * ... + (1-0.0) * 0.0 = 0
        # (注：根据之前的分析，答对时p_obs很难为0，但为了完备性可以构建一个类似的场景)
        # 实际中，更可能触发的是答错的情况。
        model2 = BKTModel({'p_init': 0.0, 'p_transit': 0.1, 'p_slip': 0.1, 'p_guess': 0.0})
        # 模拟一种罕见情况：一个掌握概率极低的用户，在不可能猜对的情况下答对了
        model2.mastery_prob = 0.0 # 强制设置
        try:
            # 这种情况更理论化，但仍可测试保护逻辑
            # P(答对|掌握) * P(掌握) = (1-p_slip) * 0 = 0
            # P(答对|未掌握) * P(未掌握) = p_guess * 1 = 0 * 1 = 0
            # p_obs = 0
            new_prob2 = model2.update(is_correct=True)
            assert 0 <= new_prob2 <= 1
        except ZeroDivisionError:
            pytest.fail("BKTModel.update() 触发了 ZeroDivisionError")

    def test_from_dict_with_missing_params(self):
        """测试 from_dict 在缺少参数时能否正确使用默认值"""
        # 场景1: 缺少 'p_transit' 和 'p_guess'
        data_missing_some = {
            'p_init': 0.3,
            'p_slip': 0.15,
            'mastery_prob': 0.35
        }
        model1 = BKTModel.from_dict(data_missing_some)
        assert model1.p_init == 0.3
        assert model1.p_slip == 0.15
        assert model1.mastery_prob == 0.35
        # 验证缺失的参数是否从 DEFAULT_PARAMS 回退
        assert model1.p_transit == BKTModel.DEFAULT_PARAMS['p_transit']
        assert model1.p_guess == BKTModel.DEFAULT_PARAMS['p_guess']

        # 场景2: 缺少 'mastery_prob'，应回退到 'p_init'
        data_missing_mastery = {
            'p_init': 0.4,
            'p_transit': 0.1,
            'p_slip': 0.2,
            'p_guess': 0.3
        }
        model2 = BKTModel.from_dict(data_missing_mastery)
        assert model2.mastery_prob == model2.p_init
        assert model2.mastery_prob == 0.4



class TestBKTModelDataDriven:
    """从数据文件读取测试用例"""
    @pytest.mark.parametrize("case", json.load(open(DATA_FILE)))
    def test_cases_from_file(self, case):
        print(f"\nTesting Case: {case['params']}")
        model = BKTModel(case["params"])
        
        for i, ans in enumerate(case["answers"], 1):
            prob = model.update(ans)
            print(f"  Step {i}: {'✓' if ans else '✗'} → mastery={prob:.3f}")
        
        mastery = model.get_mastery_prob()
        low, high = case["expected_range"]
        print(f"  Final: {mastery:.3f} (expected {low}-{high})")
        
        assert low <= mastery <= high
