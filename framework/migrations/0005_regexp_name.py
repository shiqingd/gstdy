# Generated by Django 2.2.2 on 2019-07-03 17:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('framework', '0004_configpath'),
    ]

    operations = [
        migrations.AddField(
            model_name='regexp',
            name='name',
            field=models.CharField(default='---', max_length=255),
        ),
    ]
