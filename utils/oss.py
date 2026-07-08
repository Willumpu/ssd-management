"""
阿里云 OSS 上传工具
用法：
    from utils.oss import upload_log_to_oss
    url = upload_log_to_oss(file_obj, 'abnormal/logs/xxx.txt')
"""
import oss2
from django.conf import settings


def get_oss_bucket():
    """获取 OSS Bucket 实例"""
    cfg = settings.ALIBABA_OSS
    auth = oss2.Auth(cfg['ACCESS_KEY_ID'], cfg['ACCESS_KEY_SECRET'])
    return oss2.Bucket(auth, cfg['ENDPOINT'], cfg['BUCKET_NAME'])


def upload_log_to_oss(file_obj, filename):
    """
    上传日志文件到 OSS
    :param file_obj: 文件对象（request.FILES 中的文件）
    :param filename: OSS 上的目标文件名（建议带路径前缀）
    :return: 文件的公共访问 URL
    """
    bucket = get_oss_bucket()
    path = f'logs/{filename}'
    # 上传文件
    bucket.put_object(path, file_obj.read())
    # 返回公共访问 URL（Bucket 需要关闭"阻止公共访问"）
    cfg = settings.ALIBABA_OSS
    return f"https://{cfg['BUCKET_NAME']}.{cfg['ENDPOINT']}/{path}"


def delete_log_from_oss(filename):
    """
    从 OSS 删除日志文件
    :param filename: OSS 上的文件名（含路径前缀）
    """
    bucket = get_oss_bucket()
    path = f'logs/{filename}'
    bucket.delete_object(path)


def get_signed_url(path, expiration=3600):
    """
    生成带签名的临时访问 URL（私有 Bucket 用）
    :param path: OSS 上的文件路径（含 'logs/' 前缀）
    :param expiration: 有效期（秒），默认 1 小时
    :return: 签名后的 URL
    """
    bucket = get_oss_bucket()
    return bucket.sign_url('GET', path, expiration)
