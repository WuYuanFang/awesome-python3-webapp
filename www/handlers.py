#!/Users/wuyuanfang/Kevin/Work/Python/PythonEnv/AwesomeEnv/bin python3
# -*- coding: utf-8 -*-

__author__ = 'Kevin'

'url handlers'

import markdown2
from aiohttp import web
import re, time, json, logging, hashlib, base64, asyncio
from coroweb import get, post
from models import User, Comment, Blog, next_id
from config import configs
from apis import APIValueError, APIResourceNotFoundError, APIError, APIPermissionError, Page

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHAI = re.compile(r'[0-9a-f]{40}$')

#判断用户是否有权限
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def get_page_index(page_str):
	p = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p

#将user装成cookie接口
def user2cookie(user, max_age):
	'''
	Generate cookie str by user
	'''
	expire = str(int(time.time()+max_age))
	s = '{}-{}-{}-{}'.format(user.id, user.passwd, expire, _COOKIE_KEY)
	L = [user.id, expire, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

#将cookie转成user接口
@asyncio.coroutine
def cookie2user(cookie_str):
	'''
	Parse cookie and load user if cookie is valid
	'''
	if not cookie_str:
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid, expire, sha1 = L
		#验证cookie时间是否过期
		if int(expire) < time.time():
			return None
		user = yield from User.find(uid)
		if user is None:
			return None
		s = '{}-{}-{}-{}'.format(uid, user.passwd, expire, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('invalid sha1')
			return None
		user.passwd = '******'
		return user
	except Exception as e:
		logging.exception(e)
		return None

#首页请求接口
@get('/')
async def index(request, *, page='1'):
    pageIndex = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    page = Page(num)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs
    }
	# cookie_str = request.cookies.get(COOKIE_NAME)
	# user = None
	# if cookie_str:
	# 	L = cookie_str.split('-')
	# 	if len(L) == 3:
	# 		uid, expire, sha1 = L
	# 		# 验证cookie时间是否过期
	# 		if int(expire) > time.time():
	# 			user = await User.find(uid)
	# 			user.passwd = '******'
	# return {
	# 	'__template__': 'blogs.html',
	# 	'blogs': blogs,
	# 	'__user__':user
	# }

@get('/blog/{id}')
async def get_blog(id):
	blog = await Blog.find(id)
	comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)
	return {
		'__template__': 'blog.html',
		'blog': blog,
		'comment': comments
	}

@get('/api/users')
async def api_get_users():
	users = await User.findAll(orderBy='created_at')
	for u in users:
		u.passwd = '******'
	return dict(user=users)

@get('/register')
async def register():
	return {
		'__template__': 'register.html'
	}

@get('/manage/blogs/create')
def createBlog():
	return {
		'__template__': 'manage_blog_edit.html',
		'id': '',
		'action': '/api/blogs'
	}

@get('/manage/blogs/edit')
def editBlog(*, id):
	return {
		'__template__': 'manage_blog_edit.html',
		'id': id,
		'action': '/api/blogs'
	}

@get('/manage/blogs')
def manage_blogs(*, page='1'):
	page = get_page_index(page)
	return {
		'__template__': 'manage_blog.html',
		'page_index': page
	}

@get('/signin')
async def signin():
	return {
		'__template__': 'signin.html'
	}

#用户登录接口
@post('/api/authenticate')
async def authenticate(*, email, passwd):
	if not email:
		raise APIValueError('email', 'Invalid email')
	if not passwd:
		raise APIValueError('passwd', 'Invalid passwd')
	users = await User.findAll('email=?', email)
	if len(users) == 0:
		raise APIValueError('emial', 'Email not exist')
	user = users[0]
	#check passwd
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd', 'Invalid passwd')
	#authenticate ok ,set Cookie
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r

#退出登录接口
@get('/signout')
async def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
	logging.info('user signed out')
	return r

#注册用户接口
@post('/api/users')
async def api_register_user(*, email, name, passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHAI.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=?', email)
	if len(users) > 0:
		raise APIError('register:failed', 'email', 'Email is already in use.')
	uid = next_id()
	sha1_passwd = '{}:{}'.format(uid, passwd)
	user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='https://baike.baidu.com/pic/苹果公司/304038/0/203fb80e7bec54e75b4e27ddb2389b504ec26a56?fr=lemma&ct=single#aid=0&pic=f31fbe096b63f624436c103e8444ebf81a4ca3dd')
	await User.save(user)
	#make session cookie
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r

@get('/api/blogs')
async def api_blogs(*, page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, blog=())
	blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, blogs=blogs)


@get('/api/blogs/{id}')
async def api_get_blog(*, id):
	blog = await Blog.find(id)
	return blog

@post('/api/blogs')
async def api_create_blog(request, * , name, summary, content):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty.')
	blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
	await blog.save()
	return blog

@post('/api/blogs/{id}/delete')
async def api_blogs_delete(request, *, id):
	check_admin(request)
	blog = await Blog.find(id)
	await blog.remove()
	return dict(id=id)




