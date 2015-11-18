import json, requests
from django.db import models
from django.core.cache import cache
from django.conf import settings

from wagtail.wagtailcore.models import Page, Orderable
from wagtail.wagtailcore.fields import RichTextField
from wagtail.wagtailadmin.edit_handlers import FieldPanel, InlinePanel
from wagtail.wagtailimages.models import Image
from wagtail.wagtailimages.edit_handlers import ImageChooserPanel
from wagtail.wagtailsearch import index

from modelcluster.fields import ParentalKey


class ProjectPage(Orderable, Page):
    STATUSES = (
        ('discovery', 'Discovery'),
        ('alpha', 'Alpha'),
        ('beta', 'Beta'),
        ('live', 'LIVE')
    )
    short_description = models.TextField()
    full_description = RichTextField(blank=True)
    image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    status = models.CharField(max_length=20, choices=STATUSES, default='discovery')
    piwik_id = models.IntegerField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.title:
            if self.project:
                self.title = self.project.name
        return super().save(*args, **kwargs)

    search_fields = Page.search_fields + (
        index.SearchField('short_description'),
        index.SearchField('full_description'),
    )

    content_panels = Page.content_panels + [
        FieldPanel('status'),
        FieldPanel('short_description'),
        FieldPanel('full_description'),
        ImageChooserPanel('image'),
        FieldPanel('piwik_id'),
        InlinePanel('kpis', label="Key performance indicators"),
        InlinePanel('roles', label="Roles"),
        InlinePanel('links', label="Links"),
    ]

    def piwik_data(self):
        data = cache.get('piwik_' + self.title)
        if not data:
            response = requests.get(
                'https://analytics.hel.ninja/piwik/?idSite=' +
                str(self.piwik_id) +
                '&module=API&period=day&date=today&method=API.get&format=json&token_auth=' +
                settings.PIWIK_API_TOKEN)
            if response.status_code == 200:
                data = response.json()
                cache.add('piwik_' + self.title, data, 3600)
        return data


class ProjectRoleType(Orderable, models.Model):
    name = models.CharField(max_length=50)

    def __lt__(self, other):
        if self.sort_order is None:
            return True
        if other.sort_order is None:
            return False
        return int(self.sort_order).__lt__(int(other.sort_order))

    def __str__(self):
        return self.name


class ProjectRole(models.Model):
    TYPES = (
        ('service_manager', 'Service manager'),
        ('tech', 'Tech lead'),
    )
    project = ParentalKey('projects.ProjectPage', related_name='roles')
    type = models.ForeignKey(ProjectRoleType, related_name='roles')
    person = ParentalKey('aboutus.PersonPage', related_name='roles')

    def __str__(self):
        return "%s as %s for %s" % (self.person, self.type, self.project.title)

    class Meta:
        ordering = ('type',)


class ProjectKPI(models.Model):
    project = ParentalKey('projects.ProjectPage', related_name='kpis')
    name = models.CharField(max_length=20)
    description = models.CharField(max_length=200, null=True, blank=True)
    value = models.CharField(max_length=200)


class ProjectLink(models.Model):
    TYPES = (
        ('main', 'Main'),
        ('github', 'GitHub'),
    )

    project = ParentalKey('projects.ProjectPage', related_name='links')
    type = models.CharField(max_length=20, choices=TYPES)
    public = models.BooleanField(default=True)
    description = models.CharField(max_length=200, null=True, blank=True)
    url = models.URLField()

    def __str__(self):
        return "{0} / {1}".format(str(self.project), self.type)


class ProjectIndexPage(Page):
    subpage_types = ['projects.ProjectPage']

    def projects(self):
        return ProjectPage.objects.live()

    def top_projects(self):
        return self.projects()[:5]
