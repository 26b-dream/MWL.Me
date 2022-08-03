# Generated by Django 4.0.6 on 2022-08-03 06:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0018_importque_note'),
    ]

    operations = [
        migrations.AlterField(
            model_name='anime',
            name='average_episode_duration',
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='anime',
            name='background',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='anime',
            name='main_picture_large',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='anime',
            name='popularity',
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='anime',
            name='source',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='anime',
            name='synopsis',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='manga',
            name='background',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='manga',
            name='main_picture_large',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='manga',
            name='popularity',
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='manga',
            name='synopsis',
            field=models.TextField(null=True),
        ),
        migrations.DeleteModel(
            name='MangaStudios',
        ),
    ]
