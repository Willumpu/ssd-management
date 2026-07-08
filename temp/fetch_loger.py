import urllib3, requests, re, json, sys
urllib3.disable_warnings()
base = 'https://tilipa.zlsam.com/loger/'

# 获取首页
r = requests.get(base, verify=False, timeout=15)
text = r.text
print('=== 首页前2000字符 ===')
print(text[:2000])
print('\n=== 提取资源链接 ===')
js = re.findall(r'src="(./static/js/[^"]+)"', text)
css = re.findall(r'href="(./static/css/[^"]+)"', text)
print('JS:', js)
print('CSS:', css)

# 尝试获取主 JS
for js_file in js:
    url = base.rstrip('/') + '/' + js_file.lstrip('./')
    try:
        jr = requests.get(url, verify=False, timeout=15)
        print(f'\n=== {js_file} 前3000字符 ===')
        print(jr.text[:3000])
    except Exception as e:
        print(f'获取 {js_file} 失败: {e}')
