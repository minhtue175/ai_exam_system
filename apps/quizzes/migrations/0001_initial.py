

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.TextField()),
                ('options', models.JSONField()),
                ('correct_answer', models.IntegerField()),
                ('explanation', models.TextField(blank=True, null=True)),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'db_table': 'questions',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='UserQuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('answers', models.JSONField(blank=True, default=dict)),
                ('total_questions', models.IntegerField(default=0)),
                ('correct_answers', models.IntegerField(default=0)),
                ('score', models.DecimalField(decimal_places=2, default=0.0, max_digits=5)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'user_quiz_attempts',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=255)),
                ('num_questions', models.IntegerField()),
                ('difficulty', models.CharField(choices=[('basic', 'Cơ Bản'), ('advanced', 'Nâng Cao')], default='basic', max_length=20)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quizzes', to='documents.document')),
            ],
            options={
                'verbose_name_plural': 'Quizzes',
                'db_table': 'quizzes',
                'ordering': ['-created_at'],
            },
        ),
    ]
