from django.db import models
# from portal.models import UserModel
from django.conf import settings
from settings import TaskmgrUserModel as UserModel
from django.core.validators import MaxValueValidator, MinValueValidator
from datetime import datetime
from django.contrib import auth
# Create your models here.

from django.db import models
from mptt.models import MPTTModel, TreeForeignKey

TASK_ICONS = [
    ('📦', '📦'), ('💼', '💼'), ('📒', '📒'), ('📌', '📌'), ('🎁', '🎁'), ('💻', '💻'),
    ('🎈', '🎈'), ('🔖', '🔖'), ('🗳', '🗳'), ('🔔', '🔔'), ('🪛', '🪛'), ('🚀', '🚀'),
]

class StateModel(models.Model):
    """ """
    icon = models.CharField('图标', max_length=50, default='')
    name = models.CharField('名称', max_length=50)
    pct = models.FloatField('完成度', validators=[MaxValueValidator(1), MinValueValidator(0)])
    ord = models.IntegerField('排序号', default=0)
    in_actions = models.BooleanField('动作列表', default=False)

    class Meta:
        verbose_name = '🔖 状态'
        verbose_name_plural = '🔖 状态'
        ordering = ['ord']

    def __str__(self):
        return f'{self.icon} {self.name}'


class ArchivedTaskModel(MPTTModel):
    """ """
    name = models.CharField('名称', max_length=256)
    icon = models.CharField('图标', max_length=50, choices=TASK_ICONS, default='📦')
    desc = models.TextField('说明', null=True, blank=True)
    principal = models.ForeignKey(UserModel, verbose_name='负责人', on_delete=models.SET_NULL, null=True, blank=True)
    weight = models.IntegerField('权重', default=1, validators=[MaxValueValidator(100), MinValueValidator(1)])
    start_time = models.DateField('开始时间', null=True, blank=True)
    end_time = models.DateField('结束时间', null=True, blank=True)
    # done = models.BooleanField('完成', default=False)
    state = models.ForeignKey(StateModel, verbose_name='状态', on_delete=models.SET_NULL, null=True)
    finish_time = models.DateField('完成时间', null=True, blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    archived = models.BooleanField('归档', default=False)

    class MPTTMeta:
        order_insertion_by = ['id']

    def __str__(self):
        """ """
        return f'{self.icon} [{self.id}]. {self.name}'

    class Meta:
        verbose_name = '🗜 已归档'
        verbose_name_plural = '🗜 已归档'

    def completeness(self):
        """ """
        if self.is_leaf_node():
            if self.state is None:
                return .0
            return float(self.state.pct)
        total_weghts = sum([c.weight for c in self.children.all()])
        return sum([c.completeness() * c.weight for c in self.children.all()]) / total_weghts

    def timeline(self):
        if (self.start_time is None) or (self.end_time is None):
            return None
        start_time = datetime(self.start_time.year, self.start_time.month, self.start_time.day)
        end_time = datetime(self.end_time.year, self.end_time.month, self.end_time.day, 23, 59, 59)
        current_time = datetime.now()
        if current_time > end_time:
            current_time = end_time
        return (current_time - start_time) / (end_time - start_time)


class TaskModel(ArchivedTaskModel):
    """ """
    class Meta:
        proxy = True
        verbose_name = '🗃 任务'
        verbose_name_plural = '🗃 任务'


class CatalogModel(models.Model):
    """ """
    name = models.CharField('名称', max_length=256)
    ord = models.IntegerField('排序', default=0)
    create_user = models.ForeignKey(auth.models.User, verbose_name='创建用户', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = '📝 工作区'
        verbose_name_plural = '📝 工作区'

    def __str__(self):
        """ """
        return self.name

class CatalogItemModel(models.Model):
    """ """
    catalog = models.ForeignKey(CatalogModel, verbose_name='目录', on_delete=models.CASCADE)
    task = models.ForeignKey(TaskModel, verbose_name='任务', on_delete=models.CASCADE)
    level = models.IntegerField('包含层级', validators=[MaxValueValidator(100), MinValueValidator(-1)], default=0)

    def __str__(self):
        """ """
        return f'{ self.task.name }({ self.level })'

    class Meta:
        verbose_name = '目录项'
        verbose_name_plural = '目录项'
