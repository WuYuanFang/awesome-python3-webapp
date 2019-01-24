#!/Users/wuyuanfang/Kevin/Work/Python/PythonEnv/AwesomeEnv/bin python3
# -*- coding: utf-8 -*-

__author__ = 'Kevin'

# import orm
# import asyncio
# from models import User, Blog, Comment

# async def test(loop):
#     await orm.create_pool(loop=loop, user='root', password='Yuanfang1!', db='awesome')
#     u = User(name='Test', email='test@icloud.com', passwd='123456', image='about:blank')
#     await u.save()

# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(test(loop))
#     print('Test finished.')
#     loop.close()

import time 
 
print(time.time())
print(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
