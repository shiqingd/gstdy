# Generated by Django 2.2.2 on 2020-01-30 01:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('framework', '0007_remotev2'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='external',
            field=models.BooleanField(default=False),
        ),
    ]
