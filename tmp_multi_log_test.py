import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ssd_management.settings')
django.setup()
from django.test import Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from fae.models import User, Customer
from abnormal.models import AbnormalSampleGroup, AbnormalSample, AbnormalLogFile

user = User.objects.first()
customer = Customer.objects.first()
client = Client()
client.force_login(user)

group = AbnormalSampleGroup.objects.create(customer=customer, total_count=2, created_by=user, abnormal_description='test')
s1 = AbnormalSample.objects.create(customer=customer, group=group, created_by=user, abnormal_description='d')
s2 = AbnormalSample.objects.create(customer=customer, group=group, created_by=user, abnormal_description='d')
print('samples', s1.pk, s2.pk)

files = [
    SimpleUploadedFile('a.log', b'log1'),
    SimpleUploadedFile('b.log', b'log2'),
    SimpleUploadedFile('c.log', b'log3'),
]
resp = client.post(reverse('abnormal:group_batch_upload_log', args=[group.pk]), {
    'sample_for_0': s1.pk,
    'log_type_for_0': 'fw_running',
    'sample_for_1': s1.pk,
    'log_type_for_1': 'fw_nlog',
    'sample_for_2': s2.pk,
    'log_type_for_2': 'fw_info',
}, files={'log_files': files}, follow=True)
print('status', resp.status_code)
logs = AbnormalLogFile.objects.filter(abnormal_sample__group=group)
print('log files', logs.count())
for lf in logs:
    print(lf.filename, lf.log_type, lf.abnormal_sample.pk)
