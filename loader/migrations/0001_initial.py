# Generated by Django 3.2.3 on 2021-05-31 11:52

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FrozenResource',
            fields=[
                ('hash', models.CharField(max_length=100, primary_key=True, serialize=False)),
                ('data', models.JSONField(default=dict)),
                ('parent', models.ManyToManyField(related_name='_loader_frozenresource_parent_+', to='loader.FrozenResource')),
            ],
        ),
    ]
