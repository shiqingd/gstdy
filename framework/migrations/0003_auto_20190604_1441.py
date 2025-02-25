# Generated by Django 2.2 on 2019-06-04 21:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('framework', '0002_branchtemplate_kernel'),
    ]

    operations = [
        migrations.AddField(
            model_name='configdir',
            name='release',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='framework.Release'),
        ),
        migrations.AlterUniqueTogether(
            name='configdir',
            unique_together={('kernel', 'cpu', 'release')},
        ),
    ]
