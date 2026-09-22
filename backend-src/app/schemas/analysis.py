"""教师端学情分析 DTO（camelCase，与教师端请求/响应契约一致）。"""

from typing import List, Optional

from pydantic import BaseModel


class CourseBriefVO(BaseModel):
    """课程概要（学情分析的课程维度）。"""

    courseId: int
    courseCode: str
    title: str
    studentCount: int = 0
    knowledgeCount: int = 0


class MasteryBucketVO(BaseModel):
    """掌握度分布区间（如 0-0.2 表示 mastery_prob 落在 [0, 0.2)）。"""

    bucket: str
    count: int = 0


class WeakTopicVO(BaseModel):
    """薄弱知识点（按平均掌握度升序取 Top N）。"""

    topicId: str
    avgMastery: float
    studentCount: int = 0


class StudentProgressVO(BaseModel):
    """学生进度排行项（完成知识点数 / 课程知识点总数）。"""

    participantId: str
    completedCount: int = 0
    totalCount: int = 0
    progressRate: float = 0.0


class ActivityPointVO(BaseModel):
    """活跃度趋势点（按天）。"""

    date: str
    count: int = 0


class SubmissionStatsVO(BaseModel):
    """代码提交统计（提交次数 / 参与学生数）。"""

    submissionCount: int = 0
    studentCount: int = 0


class CourseAnalysisSummaryVO(BaseModel):
    """课程学情分析总览（按课程维度聚合全部指标）。"""

    course: CourseBriefVO
    masteryDistribution: List[MasteryBucketVO] = []
    avgMastery: Optional[float] = None
    weakTopics: List[WeakTopicVO] = []
    studentProgress: List[StudentProgressVO] = []
    activityTrend: List[ActivityPointVO] = []
    submissionStats: SubmissionStatsVO = SubmissionStatsVO()
