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

files = [
    SimpleUploadedFile('x.log', b'log1'),
    SimpleUploadedFile('y.log', b'log2'),
]
# dict style
resp = client.post(reverse('abnormal:group_batch_upload_log', args=[group.pk]), {
    'log_type': 'fw_running',
    'sample_for_0': s1.pk,
    'sample_for_1': s2.pk,
}, files={'log_files': files}, follow=True)
print('dict style count', AbnormalLogFile.objects.filter(abnormal_sample__group=group).count())
