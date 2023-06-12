from django.contrib import admin
from . import models
from django.utils.safestring import mark_safe
from django.contrib import messages
from mptt.admin import MPTTModelAdmin, DraggableMPTTAdmin
from django.contrib.auth.models import User
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django.contrib.admin import SimpleListFilter
from .models import UserModel
from django.db.models import Q
from more_itertools import flatten
from functools import partial

# Register your models here.

class TaskmgrAdminSite(admin.AdminSite):
    site_header = "任务管理"
    site_title = "任务管理"
    index_title = "欢迎使用任务管理"

    def get_app_list(self, request):
        model_order = {
            models.StateModel: 1,
            models.CatalogModel: 2,
            models.TaskModel: 3,
            models.ArchivedTaskModel: 4
        }
        app_list = super().get_app_list(request)
        for app in app_list:
            if app['name'] == '任务管理':
                app['models'] = sorted(app['models'], key=lambda x: model_order.get(x['model'], 100))
        return app_list

site = TaskmgrAdminSite(name='taskmgr.admin')

def mark(state, modeladmin, request, queryset):
    """ """
    for obj in queryset:
        obj.state = state
        obj.save()

def archived(modeladmin, request, queryset):
    for task in queryset:
        qs = task.get_descendants(include_self=True)
        qs.update(archived=True)

def unarchived(modeladmin, request, queryset):
    for task in queryset:
        qs = task.get_descendants(include_self=True)
        qs.update(archived=False)

class UserAdmin(admin.ModelAdmin):
    """ Just for search use. """
    search_fields = ['full_name', 'phone']
    def get_model_perms(self, request):
        """ Return empty perms dict thus hiding the model from admin index.  """
        return {}
site.register(UserModel, UserAdmin)


class TaskInlineAdmin(admin.TabularInline):
    """ """
    autocomplete_fields = ['principal']
    fields = ['icon', 'name', 'principal', 'weight', 'start_time', 'end_time']
    model =  models.TaskModel
    extra = 0

class TaskResource(resources.ModelResource):
    class Meta:
        model = models.TaskModel

class CurrentUserFilter(SimpleListFilter):
    """ """
    title = '范围'
    parameter_name = '范围'

    def lookups(self, request, model_admin):
        """ """
        return [('me', '我'), ('all', '全部')]

    def queryset(self, request, queryset):
        """ """
        if self.value() == 'me':
            return queryset.filter(principal=request.user)
        return queryset

class PricipalFilter(SimpleListFilter):
    """ """
    title = '负责人'
    parameter_name = '负责人'

    def lookups(self, request, model_admin):
        """ """
        principal_list = set([t.principal for t in model_admin.model.objects.all()])
        return [(p.id, str(p)) for p in principal_list if p] + [('None', '<空>')]

    def queryset(self, request, queryset):
        """ """
        if self.value() is None: return queryset
        key = None if self.value() == 'None' else self.value()
        return queryset.filter(principal__id=key)


def get_children(tasks, level=0):
    """ """
    if level == 0: return [task for task in tasks]
    return list(flatten([get_children(list(task.get_children()), level-1) for task in tasks])) + tasks

class CatalogFilter(SimpleListFilter):
    """ """
    title = '工作区'
    parameter_name = '工作区'

    def lookups(self, request, model_admin):
        """ """
        qs = models.CatalogModel.objects.filter(create_user=request.user)
        return [(catalog_model.id, catalog_model.name) for catalog_model in qs]

    def queryset(self, request, queryset):
        if self.value() is None: return queryset
        catalog_model = models.CatalogModel.objects.get(id=self.value())
        tasks = []
        for item in catalog_model.catalogitemmodel_set.all():
            tasks.append(get_children([item.task], item.level))
        return queryset.filter(pk__in=[task.id for task in flatten(tasks)])

class BaseTaskAdmin(DraggableMPTTAdmin, ImportExportModelAdmin):
    """ """
    inlines = [TaskInlineAdmin]
    search_fields = ['name', 'principal__full_name', 'principal__phone']
    autocomplete_fields = ['principal', 'parent']
    list_display = ['tree_actions', 'indented_title', 'principal', 'weight', 'get_completeness', 'get_timeline', 'get_state']
    list_filter = [CurrentUserFilter, PricipalFilter, CatalogFilter]
    fieldsets = ((
        '任务信息', {'fields': (
                (('name', 'icon')),
                'parent', 'desc', 'principal',
                (('weight')),
                (('start_time', 'end_time'))
    )}),)
    def get_completeness(self, obj):
        return f'{obj.completeness() * 100: .0f}%'
    get_completeness.__name__ = '完成度'

    def get_state(self, obj):
        if not obj.is_leaf_node():
            if obj.completeness() == 1:
                return '🏅'
            else: return '...'
        # return '🍅' if obj.done else '⚪️'
        return obj.state
    get_state.allow_tags = True
    get_state.__name__ = '状态'

    def get_timeline(self, obj):
        if obj.timeline() is None:
            return '-'
        return f'{obj.timeline() * 100: .0f}%'
    get_timeline.__name__ = '时间进度'

    resource_classes = [TaskResource]

class TaskAdmin(BaseTaskAdmin):
    """ """
    def get_actions(self, request):
        """ """
        actions = {}
        for state_model in models.StateModel.objects.filter(in_actions=True):
            action_name = f'标记为{state_model.icon}{state_model.name}'
            actions[action_name] = (partial(mark, state_model), action_name, action_name)
        action_name = '归档🗜'
        actions[action_name] = (archived, action_name, action_name)
        return actions

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(archived=False)

site.register(models.TaskModel, TaskAdmin)

class ArchivedTaskAdmin(BaseTaskAdmin):
    """ """
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(archived=True)

    def get_actions(self, request):
        actions = {}
        action_name = '恢复 🗃'
        actions[action_name] = (unarchived, action_name, action_name)
        actions.update(super().get_actions(request))
        return actions

site.register(models.ArchivedTaskModel, ArchivedTaskAdmin)

class CatalogItemAdmin(admin.TabularInline):
    """ """
    fields = ['task', 'level']
    autocomplete_fields = ['task']
    model =  models.CatalogItemModel
    extra = 0

class CatalogAdmin(admin.ModelAdmin):
    """ """
    fields = ['name', 'ord']
    list_display = ['name', 'ord']
    inlines = [CatalogItemAdmin]

    def save_model(self, request, obj, form, change):
        obj.create_user = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(create_user=request.user)

site.register(models.CatalogModel, CatalogAdmin)

class StateAdmin(admin.ModelAdmin):
    """ """
    fields = ['icon', 'name', 'pct', 'ord', 'in_actions']
    list_display = ['icon', 'name', 'pct', 'ord', 'in_actions']
site.register(models.StateModel, StateAdmin)
